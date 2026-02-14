"""
Hive Mind Central Hub - Database Models
SQLAlchemy models for agents, tasks, and projects
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    status = Column(String(20), default="offline")  # online, offline, busy
    last_seen = Column(DateTime, default=datetime.utcnow)
    capabilities = Column(Text, default="")  # Comma-separated list, converted to/from list in code
    is_main_bot = Column(Boolean, default=False)
    current_task = Column(String(200), nullable=True)  # Current task description

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(50), nullable=False)  # spawn, exec, write_file, etc.
    command = Column(Text, nullable=False)  # The actual command to execute
    description = Column(Text, nullable=True)
    assigned_to = Column(String(100), nullable=True)  # Agent name, None = broadcast
    created_by = Column(String(100), nullable=True)  # Agent name who created it
    status = Column(String(20), default="pending")  # pending, completed, failed
    result = Column(Text, nullable=True)  # Task result/output
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(100), nullable=True)  # Agent who completed it
    project_id = Column(Integer, nullable=True)  # Optional project ID

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="active")  # active, completed, archived
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
