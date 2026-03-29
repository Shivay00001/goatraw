"""
GoatRaw - Async Database Layer (SQLAlchemy + asyncpg)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging

logger = logging.getLogger("goatraw.db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup (use Alembic for production migrations)."""
    async with engine.begin() as conn:
        from app.models import user, task, output, log  # noqa: import triggers registration
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")


async def get_db():
    """FastAPI dependency — yields an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
