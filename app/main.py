import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.deps import SessionDep
from app.routers import auth, tasks

log = logging.getLogger("app.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    weak_key = settings.secret_key == "change-me" or len(settings.secret_key) < 32
    if settings.environment == "production" and weak_key:
        raise RuntimeError("SECRET_KEY must be set to a random string of 32+ characters")
    if weak_key:
        log.warning("SECRET_KEY is weak or default; do not use this configuration in production")
    yield
    await engine.dispose()


app = FastAPI(title="Tasks API", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/health", tags=["service"])
async def health(session: SessionDep):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, detail={"status": "error", "db": "down"}) from None
    return {"status": "ok", "db": "ok"}
