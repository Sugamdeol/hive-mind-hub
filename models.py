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
    capabilities = Column(Text, default="")  # Comma-separated list
    is_main_bot = Column(Boolean, default=False)
    
    # Relationships - tasks assigned to this agent
    tasks = relationship("Task", foreign_keys="Task.agent_id", back_populates="assigned_agent")
    # Tasks created by this agent
    created_tasks = relationship("Task", foreign_keys="Task.created_by", back_populates="creator")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    command = Column(Text, nullable=False)  # The actual command to execute
    status = Column(String(20), default="pending")  # pending, assigned, completed, failed
    result = Column(Text, default="")  # Task result/output
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    assigned_agent = relationship("Agent", foreign_keys=[agent_id], back_populates="tasks")
    creator = relationship("Agent", foreign_keys=[created_by], back_populates="created_tasks")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="active")  # active, completed, archived
    tasks_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
