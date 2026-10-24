"""Фикстуры. Тесты с БД идут на настоящем PostgreSQL (TEST_DATABASE_URL).
Чистые тесты (test_utils, test_schemas) фикстур БД не запрашивают и работают без неё.
"""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://tasks:tasks@localhost:5434/tasks_test"
)
# до первого импорта app.*: настройки читаются один раз при импорте
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-0123456789abcdef")

ROOT = Path(__file__).resolve().parent.parent


def _ensure_database() -> None:
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    url = make_url(TEST_DB_URL)

    async def go() -> None:
        admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
        await admin.dispose()

    asyncio.run(go())


@pytest.fixture(scope="session")
def migrated_database():
    """Создаёт тестовую БД (если её нет) и накатывает миграции с нуля: заодно тестирует их."""
    from alembic import command
    from alembic.config import Config

    _ensure_database()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def engine(migrated_database):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tasks RESTART IDENTITY CASCADE"))
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    from httpx import ASGITransport, AsyncClient

    from app.database import get_session
    from app.main import app

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
