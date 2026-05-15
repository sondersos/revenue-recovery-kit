from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Ensure the runtime URL uses the asyncpg driver.
_async_url = (
    settings.DATABASE_URL
    .replace("postgresql+psycopg://", "postgresql+asyncpg://")
    .replace("postgresql://", "postgresql+asyncpg://")
)

engine = create_async_engine(_async_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and closes it afterwards."""
    async with AsyncSessionLocal() as session:
        yield session
