import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings


# -------------------------------------------------------------
# ✅ Database Configuration
# Automatically adapts to SQLite (local) or PostgreSQL (production)
# -------------------------------------------------------------

DATABASE_URL = settings.DATABASE_URL

# Ensure SQLite URLs use async driver
if DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

# Create async SQLAlchemy engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # Set True for SQL debug logs
    future=True,
    pool_pre_ping=True,  # Detect broken connections
)

# Session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Declarative Base class for ORM models
Base = declarative_base()


# -------------------------------------------------------------
# Dependency Injection for FastAPI routes
# -------------------------------------------------------------
async def get_db():
    """
    Dependency that provides a database session per request.
    Closes the session automatically after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
