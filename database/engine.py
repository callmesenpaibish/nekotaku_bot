"""database/engine.py — Async SQLAlchemy engine and session factory."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from config import DATABASE_URL as _DATABASE_URL

# Remap sync PostgreSQL URLs to async-compatible ones and strip unsupported params
def _prepare_db_url(url: str):
    connect_args = {}
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sslmode = query_params.pop("sslmode", [None])[0]
        if sslmode in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = True
        new_query = urlencode({k: v[0] for k, v in query_params.items()})
        url = urlunparse(parsed._replace(query=new_query))
    return url, connect_args

DATABASE_URL, _pg_connect_args = _prepare_db_url(_DATABASE_URL)

# Ensure SQLite data directory exists
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.split("///")[-1]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    _connect_args = {"check_same_thread": False}
else:
    _connect_args = _pg_connect_args

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
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
