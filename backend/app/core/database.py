from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Ensure the runtime URL uses the asyncpg driver.
# asyncpg uses ?ssl=require; psycopg uses ?sslmode=require — normalise here.
_async_url = (
    settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    .replace("postgresql://", "postgresql+asyncpg://")
    .replace("sslmode=require", "ssl=require")
)

# Supabase transaction pooler (pgbouncer in transaction mode) does not
# support prepared statements. Setting statement_cache_size=0 disables
# them so asyncpg falls back to simple queries — safe for all targets.
_connect_args: dict = {"statement_cache_size": 0}

engine = create_async_engine(_async_url, echo=False, connect_args=_connect_args)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and closes it afterwards."""
    async with AsyncSessionLocal() as session:
        yield session
