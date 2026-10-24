from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.database import Base


async def test_models_match_migrations(engine):
    """Если модель изменили, а миграцию забыли, тест покажет расхождение."""

    def diff(sync_connection):
        context = MigrationContext.configure(sync_connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)

    async with engine.connect() as connection:
        differences = await connection.run_sync(diff)
    assert differences == []
