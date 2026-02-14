"""
Hive Mind Central Hub - Database Configuration
SQLAlchemy database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment or use SQLite as fallback
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Use PostgreSQL (Render provides this)
    if DATABASE_URL.startswith("postgres://"):
        # SQLAlchemy requires postgresql:// not postgres://
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(DATABASE_URL)
else:
    # SQLite for local development
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hub.db")
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Required for SQLite
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()
