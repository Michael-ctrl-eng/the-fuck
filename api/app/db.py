from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine(settings: Settings) -> AsyncEngine:
    url = settings.effective_database_url
    kwargs: dict = {"echo": False, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # SQLite dev/test fallback: single file, WAL, serialized writes.
        path = Path(url.split("///", 1)[1])
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        kwargs.update(
            connect_args={"check_same_thread": False},
        )
    else:
        kwargs.update(pool_size=10, max_overflow=20)
    return create_async_engine(url, **kwargs)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _factory


async def init_db(settings: Settings | None = None) -> None:
    """Create tables for SQLite dev/test mode.

    PostgreSQL production deployments use Alembic migrations
    (api/alembic) run by the container entrypoint.
    """
    settings = settings or get_settings()
    engine = get_engine()
    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Dev convenience: an existing sandbox DB may predate schema
            # additions. Backfill missing columns so stale dev DBs don't
            # break the running app (production uses Alembic, not this).
            await _backfill_missing_columns(conn)


async def _backfill_missing_columns(conn) -> None:
    from sqlalchemy import inspect, text

    from . import models

    def _backfill(sync_conn) -> None:
        inspector = inspect(sync_conn)
        existing = {
            t: {c["name"] for c in inspector.get_columns(t)}
            for t in inspector.get_table_names()
        }
        for table in models.Base.metadata.sorted_tables:
            if table.name not in existing:
                continue
            missing = [c for c in table.columns if c.name not in existing[table.name]]
            if not missing:
                continue
            dialect = sync_conn.dialect
            for col in missing:
                col_type = col.type.compile(dialect=dialect)
                sync_conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}')
                )

    await conn.run_sync(_backfill)


async def dispose_db() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None
