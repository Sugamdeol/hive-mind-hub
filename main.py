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

from database import SessionLocal, engine, Base, init_db, DATABASE_URL
from models import Agent, Task, Project

# Create database tables with error handling
db_initialized = init_db()
if not db_initialized:
    print("WARNING: Database initialization failed. Some features may not work.")

def hash_password(password: str) -> str:
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_main_bot():
    """Create main_bot admin agent on startup if not exists"""
    db = SessionLocal()
    try:
        # Check if main_bot exists
        main_bot = db.query(Agent).filter(Agent.name == "main_bot").first()
        if not main_bot:
            # Get password from env or use default
            password = os.getenv("MAIN_BOT_PASSWORD", "admin123")
            main_bot = Agent(
                name="main_bot",
                password_hash=hash_password(password),
                is_main_bot=True,
                capabilities=["admin", "all"],
                status="online",
                last_seen=datetime.utcnow()
            )
            db.add(main_bot)
            db.commit()
            print(f"✅ Created main_bot agent with password: {password}")
        else:
            # Ensure is_main_bot flag is set
            if not main_bot.is_main_bot:
                main_bot.is_main_bot = True
                db.commit()
                print("✅ Updated main_bot to admin status")
    except Exception as e:
        print(f"⚠️ Error creating main_bot: {e}")
    finally:
        db.close()

app = FastAPI(
    title="Hive Mind Central Hub",
    description="Control center for distributed nanobot agents",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and create main_bot on startup"""
    print("Starting up Hive Mind Hub...")
    
    # Initialize database
    success = init_db()
    if success:
        print("Database ready")
    else:
        print("WARNING: Database initialization failed")
    
    # Create main_bot admin
    create_main_bot()

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
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
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
    agent_name: Optional[str] = None  # None = broadcast to all
    task_type: str
    command: str
    description: Optional[str] = None

class ProjectCreate(BaseModel):
    name: str
    description: str
    tasks: List[dict] = []

class HeartbeatData(BaseModel):
    status: str = "online"
    current_task: Optional[str] = None

class TaskResult(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None

# Helper functions
def create_token(agent_name: str) -> str:
    """Create JWT token for agent"""
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": agent_name,
        "exp": expire,
        "type": "agent"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials) -> str:
    """Verify JWT token and return agent name"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_agent(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> Agent:
    """Get current authenticated agent"""
    agent_name = verify_token(credentials)
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")
    return agent

# Public endpoints
@app.get("/")
def root():
    return {
        "name": "Hive Mind Central Hub",
        "version": "1.0.0",
        "endpoints": {
            "dashboard": "/dashboard",
            "register": "/agent/register",
            "login": "/agent/login",
            "poll": "/agent/poll",
            "admin": "/admin/*"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/debug/db")
def debug_db():
    """Debug database status"""
    import os
    try:
        db = SessionLocal()
        agent_count = db.query(Agent).count()
        db.close()
        db_type = "postgresql" if "postgresql" in DATABASE_URL else "sqlite"
        return {
            "database": "connected",
            "type": db_type,
            "database_url": DATABASE_URL,
            "render_env": os.environ.get("RENDER", "not set"),
            "agents_table": "exists",
            "agent_count": agent_count
        }
    except Exception as e:
        import traceback
        return {
            "database": "error", 
            "error": str(e), 
            "traceback": traceback.format_exc(),
            "database_url": DATABASE_URL,
            "render_env": os.environ.get("RENDER", "not set")
        }

@app.post("/agent/register")
def register_agent(agent_data: AgentRegister, db: Session = Depends(get_db)):
    """Register a new agent"""
    import traceback
    try:
        print(f"DEBUG: Registration attempt for {agent_data.name}")
        print(f"DEBUG: Capabilities: {agent_data.capabilities}")
        
        # Check if agent exists
        existing = db.query(Agent).filter(Agent.name == agent_data.name).first()
        if existing:
            print(f"DEBUG: Agent {agent_data.name} already exists")
            raise HTTPException(status_code=400, detail="Agent name already exists")
        
        # Create new agent
        print(f"DEBUG: Creating new agent object")
        agent = Agent(
            name=agent_data.name,
            password_hash=hash_password(agent_data.password),
            capabilities=",".join(agent_data.capabilities) if agent_data.capabilities else "",
            is_main_bot=False,
            status="offline"
        )
        print(f"DEBUG: Agent object created, adding to session")
        db.add(agent)
        print(f"DEBUG: Committing to database")
        db.commit()
        print(f"DEBUG: Refreshing agent")
        db.refresh(agent)
        print(f"DEBUG: Registration successful")
        
        return {
            "message": "Agent registered successfully",
            "agent_name": agent.name,
            "is_main_bot": agent.is_main_bot
        }
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Registration failed: {e}")
        print(error_trace)
        # Return detailed error for debugging
        return {
            "error": str(e),
            "traceback": error_trace,
            "detail": f"Registration failed: {str(e)}"
        }

@app.post("/agent/login")
def login_agent(login_data: AgentLogin, db: Session = Depends(get_db)):
    """Login agent and get token"""
    try:
        agent = db.query(Agent).filter(Agent.name == login_data.name).first()
        if not agent or agent.password_hash != hash_password(login_data.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Update last seen
        agent.last_seen = datetime.utcnow()
        agent.status = "online"
        db.commit()
        
        # Create token
        token = create_token(agent.name)
        
        # Convert capabilities string to list
        caps = agent.capabilities.split(",") if agent.capabilities else []
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "agent_name": agent.name,
            "is_main_bot": agent.is_main_bot,
            "capabilities": caps
        }
    except Exception as e:
        import traceback
        print(f"Login error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/agent/heartbeat")
def agent_heartbeat(
    heartbeat: HeartbeatData,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Agent heartbeat - update status"""
    agent.status = heartbeat.status
    agent.last_seen = datetime.utcnow()
    if heartbeat.current_task:
        agent.current_task = heartbeat.current_task
    db.commit()
    return {"message": "Heartbeat received"}

@app.get("/agent/poll")
def poll_tasks(agent: Agent = Depends(get_current_agent), db: Session = Depends(get_db)):
    """Poll for assigned tasks"""
    # Get pending tasks for this agent
    tasks = db.query(Task).filter(
        Task.assigned_to == agent.name,
        Task.status == "pending"
    ).all()
    
    # Also get broadcast tasks
    broadcast_tasks = db.query(Task).filter(
        Task.assigned_to == None,
        Task.status == "pending"
    ).all()
    
    all_tasks = tasks + broadcast_tasks
    
    return {
        "tasks": [
            {
                "id": task.id,
                "type": task.task_type,
                "command": task.command,
                "description": task.description,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
            for task in all_tasks
        ]
    }

@app.post("/agent/task/{task_id}/complete")
def complete_task(
    task_id: int,
    result: TaskResult,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """Mark task as complete with result"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = "completed" if result.success else "failed"
    task.result = result.result
    task.error = result.error
    task.completed_at = datetime.utcnow()
    task.completed_by = agent.name
    db.commit()
    
    return {"message": "Task result recorded"}

# Admin endpoints (main bot only)
def require_admin(agent: Agent = Depends(get_current_agent)):
    """Require admin (main_bot) privileges"""
    if not agent.is_main_bot:
        raise HTTPException(status_code=403, detail="Admin access required")
    return agent

@app.get("/admin/agents")
def list_agents(admin: Agent = Depends(require_admin), db: Session = Depends(get_db)):
    """List all registered agents"""
    agents = db.query(Agent).all()
    return {
        "agents": [
            {
                "name": a.name,
                "status": a.status,
                "capabilities": a.capabilities,
                "is_main_bot": a.is_main_bot,
                "last_seen": a.last_seen.isoformat() if a.last_seen else None,
                "current_task": a.current_task
            }
            for a in agents
        ]
    }

@app.post("/admin/task/assign")
def assign_task(
    task_data: TaskCreate,
    admin: Agent = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Assign task to specific agent or broadcast"""
    task = Task(
        task_type=task_data.task_type,
        command=task_data.command,
        description=task_data.description,
        assigned_to=task_data.agent_name,  # None = broadcast
        status="pending",
        created_by=admin.name
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "message": "Task assigned" if task_data.agent_name else "Task broadcast to all agents",
        "task_id": task.id
    }

@app.get("/admin/tasks")
def list_tasks(admin: Agent = Depends(require_admin), db: Session = Depends(get_db)):
    """List all tasks"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return {
        "tasks": [
            {
                "id": t.id,
                "type": t.task_type,
                "command": t.command,
                "description": t.description,
                "assigned_to": t.assigned_to,
                "status": t.status,
                "created_by": t.created_by,
                "completed_by": t.completed_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "result": t.result,
                "error": t.error
            }
            for t in tasks
        ]
    }

@app.post("/admin/project/create")
def create_project(
    project_data: ProjectCreate,
    admin: Agent = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new project with tasks"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        created_by=admin.name,
        status="active"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Add tasks if provided
    for task_dict in project_data.tasks:
        task = Task(
            task_type=task_dict.get("type", "exec"),
            command=task_dict.get("command", ""),
            description=task_dict.get("description"),
            assigned_to=task_dict.get("agent_name"),
            project_id=project.id,
            status="pending",
            created_by=admin.name
        )
        db.add(task)
    
    db.commit()
    
    return {
        "message": "Project created",
        "project_id": project.id,
        "tasks_count": len(project_data.tasks)
    }

@app.get("/admin/projects")
def list_projects(admin: Agent = Depends(require_admin), db: Session = Depends(get_db)):
    """List all projects"""
    projects = db.query(Project).all()
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "created_by": p.created_by,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in projects
        ]
    }

@app.post("/admin/broadcast")
def broadcast_message(
    message: str,
    admin: Agent = Depends(require_admin)
):
    """Broadcast message to all agents"""
    # This would integrate with your notification system
    return {"message": "Broadcast sent", "content": message, "from": admin.name}

@app.get("/admin/stats")
def get_stats(admin: Agent = Depends(require_admin), db: Session = Depends(get_db)):
    """Get system statistics"""
    total_agents = db.query(Agent).count()
    online_agents = db.query(Agent).filter(Agent.status == "online").count()
    total_tasks = db.query(Task).count()
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    
    return {
        "agents": {
            "total": total_agents,
            "online": online_agents,
            "offline": total_agents - online_agents
        },
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "completed": completed_tasks,
            "failed": total_tasks - pending_tasks - completed_tasks
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
