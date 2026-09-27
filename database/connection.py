import os
import logging
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables from flight-price-index/.env or parent .env
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("apix.database")

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/apix_db")
ALLOW_SQLITE_FALLBACK = os.getenv("ALLOW_SQLITE_FALLBACK", "true").lower() in ("true", "1", "yes")

_engine = None
_SessionLocal = None

def get_engine():
    """
    Initializes and returns the SQLAlchemy engine.
    Tries PostgreSQL first; falls back to SQLite if PostgreSQL is unreachable and fallback is enabled.
    """
    global _engine
    if _engine is not None:
        return _engine

    target_url = DATABASE_URL
    try:
        engine = create_engine(
            target_url,
            pool_pre_ping=True,
            echo=False
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Connected to database successfully: {target_url.split('@')[-1] if '@' in target_url else target_url}")
        _engine = engine
        return _engine
    except Exception as e:
        if ALLOW_SQLITE_FALLBACK:
            sqlite_db_path = base_dir / "apix_local.db"
            fallback_url = f"sqlite:///{sqlite_db_path}"
            logger.warning(
                f"PostgreSQL connection to {DATABASE_URL} failed ({e}). "
                f"Falling back to local SQLite database at {sqlite_db_path}"
            )
            _engine = create_engine(
                fallback_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
                echo=False
            )
            return _engine
        else:
            logger.error(f"Failed to connect to database at {DATABASE_URL}: {e}")
            raise e

def get_session_maker():
    """Returns a configured sessionmaker bound to the active engine."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal

def get_db() -> Generator[Session, None, None]:
    """Context-friendly generator for obtaining a database session."""
    session_factory = get_session_maker()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
