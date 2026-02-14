"""
Hive Mind Central Hub - Database Configuration
SQLAlchemy database connection and session management
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from environment or use SQLite as fallback
DATABASE_URL = os.environ.get("DATABASE_URL")
RENDER = os.environ.get("RENDER", "false").lower() == "true"

# DEBUG: Print what we're actually getting
print(f"DEBUG DATABASE_URL from env: {DATABASE_URL}")
print(f"DEBUG RENDER from env: {os.environ.get('RENDER', 'NOT SET')}")
print(f"DEBUG RENDER parsed: {RENDER}")

if DATABASE_URL:
    # Use PostgreSQL (Render provides this)
    if DATABASE_URL.startswith("postgres://"):
        # SQLAlchemy requires postgresql:// not postgres://
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    logger.info(f"Using PostgreSQL database: {DATABASE_URL[:20]}...")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # SQLite for local development
    # On Render, use in-memory database (ephemeral filesystem)
    if RENDER:
        DATABASE_URL = "sqlite:///:memory:"
        print(f"DEBUG: Using in-memory SQLite")
        logger.info(f"Using in-memory SQLite (Render ephemeral)")
    else:
        DATABASE_PATH = "/tmp/hive_mind.db"
        DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
        print(f"DEBUG: Using file SQLite at {DATABASE_PATH}")
        logger.info(f"Using SQLite file: {DATABASE_PATH}")
    
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Required for SQLite
    )

print(f"DEBUG FINAL DATABASE_URL: {DATABASE_URL}")

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection test passed")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False
