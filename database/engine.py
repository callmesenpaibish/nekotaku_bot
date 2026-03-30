"""database/engine.py — Async SQLAlchemy engine and session factory."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

# Ensure SQLite data directory exists
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.split("///")[-1]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables on startup."""
    from database.models import (  # noqa: F401 — import to register models
        GroupSettings, UserWarning, UserInfraction,
        AllowedAdmin, ActionLog,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
