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

if DATABASE_URL:
    # Use PostgreSQL (Render provides this)
    if DATABASE_URL.startswith("postgres://"):
        # SQLAlchemy requires postgresql:// not postgres://
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    logger.info(f"Using PostgreSQL database")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # SQLite for local development / Render
    DATABASE_PATH = "/tmp/hive_mind.db"
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    logger.info(f"Using SQLite database: {DATABASE_PATH}")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Required for SQLite
    )

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
