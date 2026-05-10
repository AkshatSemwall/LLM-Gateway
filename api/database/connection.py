import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event

from .models import Base

logger = logging.getLogger(__name__)

# Defaults to the workspace boundary
DB_PATH = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///autopilot.db")

# Async execution bound config
engine = create_async_engine(
    DB_PATH,
    echo=False,  # Set to True for SQL query debugging
    future=True
)

# Enforce WAL mode on sqlite explicitly for read/write multiplexing concurrent capability
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DB_PATH.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA cache_size=-64000;")  # 64MB Cache
        cursor.close()

# Session factory wrapper
AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db():
    """Initializes schema locally if none exist. Migrations (Alembic) handle updates."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized with WAL multiplexing mode active.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema block: {e}")

async def get_session() -> AsyncSession:
    """Dependency injection target for FastAPI routers."""
    async with AsyncSessionFactory() as session:
        yield session # type: ignore
