"""
Database connection management for PostgreSQL.

Note: Database is OPTIONAL for the simple supervisor pattern.
The supervisor can run without a database - it's only needed for
session persistence and memory features.
"""
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import settings

# SQLAlchemy Base
Base = declarative_base()

# Global engine and session maker
engine: Optional[AsyncEngine] = None
async_session_maker: Optional[async_sessionmaker] = None

# Connection pool for raw asyncpg queries (for pgvector operations)
pg_pool: Optional[asyncpg.Pool] = None

# Track if database is available
db_available: bool = False


async def init_db() -> None:
    """Initialize database engine and connection pool.

    This is OPTIONAL - the supervisor can run without a database.
    If connection fails, we log a warning but continue.
    """
    global engine, async_session_maker, pg_pool, db_available

    try:
        # SQLAlchemy async engine
        engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        # Session maker
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Raw asyncpg pool for vector operations
        pg_pool = await asyncpg.create_pool(
            settings.database_url.replace("+asyncpg", ""),
            min_size=5,
            max_size=20,
            command_timeout=60,
        )

        db_available = True
        print(f"✓ Database initialized: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")

    except Exception as e:
        db_available = False
        print(f"⚠ Database not available (optional): {e}")
        print("  The supervisor will run without database features (session persistence, memory).")


async def close_db() -> None:
    """Close database connections."""
    global engine, pg_pool

    if engine:
        await engine.dispose()
        print("✓ Database engine disposed")

    if pg_pool:
        await pg_pool.close()
        print("✓ Database pool closed")


@asynccontextmanager
async def get_session():
    """Get async database session."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """Dependency for FastAPI routes to get database session."""
    async with get_session() as session:
        yield session


@asynccontextmanager
async def get_pg_connection():
    """Get raw asyncpg connection for vector operations."""
    if pg_pool is None:
        raise RuntimeError("Connection pool not initialized. Call init_db() first.")

    async with pg_pool.acquire() as connection:
        yield connection


async def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        if pg_pool is None:
            return False

        async with pg_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        print(f"✗ Database health check failed: {e}")
        return False


async def ensure_pgvector_extension() -> None:
    """Ensure pgvector extension is installed.

    This is OPTIONAL - if database is not available, we skip this.
    """
    if not db_available:
        print("⚠ Skipping pgvector extension (database not available)")
        return

    try:
        async with get_pg_connection() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            print("✓ pgvector extension ensured")
    except Exception as e:
        print(f"⚠ Failed to create pgvector extension (optional): {e}")
