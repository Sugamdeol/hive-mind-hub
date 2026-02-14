"""
Hive Mind Central Hub - FastAPI Application
Main nanobot control center for distributed agent management
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import uvicorn
import jwt
import hashlib
import secrets
import os

from database import SessionLocal, engine, Base
from models import Agent, Task, Project

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hive Mind Central Hub",
    description="Control center for distributed nanobot agents",
    version="1.0.0"
)

# CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve dashboard static files (in same directory for deployment)
dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard")
if os.path.exists(dashboard_path):
    app.mount("/static", StaticFiles(directory=dashboard_path), name="static")

@app.get("/dashboard")
def serve_dashboard():
    """Serve the Hive Mind web dashboard"""
    dashboard_file = os.path.join(dashboard_path, "index.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    raise HTTPException(status_code=404, detail="Dashboard not found")

security = HTTPBearer()

# Configuration
SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for request/response
class AgentRegister(BaseModel):
    name: str
    password: str
    capabilities: List[str] = []

class AgentLogin(BaseModel):
    name: str
    password: str

class TaskCreate(BaseModel):
    title: str
    description: str
    command: str
    agent_id: Optional[int] = None
    broadcast: bool = False

class TaskResult(BaseModel):
    task_id: int
    result: str
    success: bool = True

class Heartbeat(BaseModel):
    agent_id: int

class ProjectCreate(BaseModel):
    name: str
    description: str

class ProjectDivide(BaseModel):
    project_id: int
    tasks: List[dict]

# Helper functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Agent endpoints
@app.post("/agent/register")
def register_agent(agent_data: AgentRegister, db: Session = Depends(get_db)):
    # Check if agent name exists
    existing = db.query(Agent).filter(Agent.name == agent_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent name already exists")
    
    # Create new agent
    new_agent = Agent(
        name=agent_data.name,
        password_hash=hash_password(agent_data.password),
        capabilities=",".join(agent_data.capabilities),
        status="offline",
        is_main_bot=False
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    
    return {
        "success": True,
        "agent_id": new_agent.id,
        "message": f"Agent '{agent_data.name}' registered successfully"
    }

@app.post("/agent/login")
def login_agent(login_data: AgentLogin, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.name == login_data.name).first()
    if not agent or agent.password_hash != hash_password(login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update status
    agent.status = "online"
    agent.last_seen = datetime.utcnow()
    db.commit()
    
    # Create token
    token = create_access_token({
        "agent_id": agent.id,
        "name": agent.name,
        "is_main_bot": agent.is_main_bot
    })
    
    return {
        "success": True,
        "token": token,
        "agent_id": agent.id,
        "is_main_bot": agent.is_main_bot
    }

@app.get("/agent/poll-tasks")
def poll_tasks(payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    agent_id = payload.get("agent_id")
    
    # Get pending tasks for this agent
    tasks = db.query(Task).filter(
        Task.agent_id == agent_id,
        Task.status == "pending"
    ).all()
    
    # Also get broadcast tasks not yet assigned
    broadcast_tasks = db.query(Task).filter(
        Task.agent_id == None,
        Task.status == "pending"
    ).all()
    
    all_tasks = tasks + broadcast_tasks
    
    # Mark broadcast tasks as assigned to this agent
    for task in broadcast_tasks:
        task.agent_id = agent_id
        task.status = "assigned"
    db.commit()
    
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "command": t.command,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in all_tasks
        ]
    }

@app.post("/agent/report-result")
def report_result(result: TaskResult, payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == result.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.result = result.result
    task.status = "completed" if result.success else "failed"
    task.completed_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Result recorded"}

@app.post("/agent/heartbeat")
def heartbeat(hb: Heartbeat, payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == hb.agent_id).first()
    if agent:
        agent.last_seen = datetime.utcnow()
        if agent.status != "busy":
            agent.status = "online"
        db.commit()
    
    return {"success": True}

# Admin endpoints (main bot only)
@app.get("/admin/agents")
def list_agents(payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    agents = db.query(Agent).all()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "status": a.status,
                "capabilities": a.capabilities.split(",") if a.capabilities else [],
                "last_seen": a.last_seen.isoformat() if a.last_seen else None,
                "is_main_bot": a.is_main_bot
            }
            for a in agents
        ]
    }

@app.post("/admin/task/assign")
def assign_task(task_data: TaskCreate, payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        command=task_data.command,
        agent_id=None if task_data.broadcast else task_data.agent_id,
        status="pending",
        created_by=payload.get("agent_id"),
        created_at=datetime.utcnow()
    )
    db.add(new_task)
    db.commit()
    
    return {
        "success": True,
        "task_id": new_task.id,
        "message": "Task created successfully"
    }

@app.get("/admin/tasks")
def list_tasks(status: Optional[str] = None, payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    
    tasks = query.order_by(Task.created_at.desc()).all()
    
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "command": t.command,
                "status": t.status,
                "agent_id": t.agent_id,
                "result": t.result,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ]
    }

@app.post("/admin/project/create")
def create_project(project_data: ProjectCreate, payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        status="active",
        tasks_count=0,
        completed_count=0
    )
    db.add(new_project)
    db.commit()
    
    return {
        "success": True,
        "project_id": new_project.id,
        "message": "Project created successfully"
    }

@app.get("/admin/projects")
def list_projects(payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    projects = db.query(Project).all()
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "tasks_count": p.tasks_count,
                "completed_count": p.completed_count,
                "progress": (p.completed_count / p.tasks_count * 100) if p.tasks_count > 0 else 0
            }
            for p in projects
        ]
    }

@app.get("/admin/stats")
def get_stats(payload: dict = Depends(verify_token), db: Session = Depends(get_db)):
    if not payload.get("is_main_bot"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Calculate stats
    total_agents = db.query(Agent).count()
    online_agents = db.query(Agent).filter(Agent.status == "online").count()
    busy_agents = db.query(Agent).filter(Agent.status == "busy").count()
    
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    completed_today = db.query(Task).filter(
        Task.status == "completed",
        Task.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
    ).count()
    
    return {
        "total_agents": total_agents,
        "online_agents": online_agents,
        "busy_agents": busy_agents,
        "offline_agents": total_agents - online_agents - busy_agents,
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "completed_today": completed_today,
        "active_projects": db.query(Project).filter(Project.status == "active").count()
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {
        "name": "Hive Mind Central Hub",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "agent": "/agent/*",
            "admin": "/admin/*"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
