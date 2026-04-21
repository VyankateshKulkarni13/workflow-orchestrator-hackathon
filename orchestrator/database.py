import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Resolve .env from the project root reliably, regardless of working directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://orchestrator:password@localhost:5434/orchestrator_db"
)

# Single connection pool shared across the entire app lifetime
engine = create_async_engine(DATABASE_URL, echo=False)

# Session factory — creates one AsyncSession per request
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Parent class for all ORM models (WorkflowTemplate, WorkflowExecution, TaskExecution)
Base = declarative_base()


async def get_db():
    """
    FastAPI dependency — yields a fresh DB session per request.
    Automatically closes the session when the request is done.
    Usage in routers:  db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """
    Called once on app startup.
    Creates all tables in Postgres based on the ORM models if they don't exist.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
