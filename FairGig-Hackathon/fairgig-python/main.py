# main.py - Auth & Earnings Service (Port 8000)
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FairGig Auth & Earnings Service")

# CORS for Tayyab's frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DATABASE SETUP (SQLite)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fairgig.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# DATABASE MODELS
# ==========================================
class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    city = Column(String, default="Lahore")
    platform = Column(String, nullable=False)
    role = Column(String, default="worker")
    total_earnings = Column(Float, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Earning(Base):
    __tablename__ = "earnings"
    
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    platform = Column(String, nullable=False)
    date = Column(String, nullable=False)
    hours = Column(Float, nullable=True)
    gross = Column(Float, nullable=True)
    deductions = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==========================================
# PASSWORD & JWT SETUP
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class WorkerRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    city: str = "Lahore"
    platform: str

class WorkerLogin(BaseModel):
    email: EmailStr
    password: str

class EarningsCreate(BaseModel):
    amount: float
    platform: str
    date: str
    hours: Optional[float] = None
    gross: Optional[float] = None
    deductions: Optional[float] = None

# ==========================================
# DEPENDENCIES
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/health")
async def health():
    return {"status": "OK", "service": "Auth & Earnings", "port": 8000}

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(worker: WorkerRegister, db: Session = Depends(get_db)):
    existing = db.query(Worker).filter(Worker.email == worker.email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    
    new_worker = Worker(
        name=worker.name,
        email=worker.email,
        password=hash_password(worker.password),
        phone=worker.phone,
        city=worker.city,
        platform=worker.platform
    )
    db.add(new_worker)
    db.commit()
    db.refresh(new_worker)
    
    token = create_token({"sub": worker.email, "worker_id": new_worker.id})
    
    return {
        "success": True,
        "message": "Worker registered",
        "worker_id": new_worker.id,
        "token": token
    }

@app.post("/api/auth/login")
async def login(login: WorkerLogin, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.email == login.email).first()
    if not worker or not verify_password(login.password, worker.password):
        raise HTTPException(401, "Invalid credentials")
    
    token = create_token({"sub": worker.email, "worker_id": worker.id})
    
    return {
        "success": True,
        "token": token,
        "worker_id": worker.id,
        "name": worker.name,
        "role": worker.role
    }

@app.post("/api/earnings")
async def add_earnings(earning: EarningsCreate, worker_id: int, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(404, "Worker not found")
    
    new_earning = Earning(
        worker_id=worker_id,
        amount=earning.amount,
        platform=earning.platform,
        date=earning.date,
        hours=earning.hours,
        gross=earning.gross,
        deductions=earning.deductions
    )
    db.add(new_earning)
    worker.total_earnings += earning.amount
    db.commit()
    
    return {"success": True, "message": "Earnings added", "earning_id": new_earning.id}

@app.get("/api/earnings/{user_id}")
async def get_earnings(user_id: int, db: Session = Depends(get_db)):
    earnings = db.query(Earning).filter(Earning.worker_id == user_id).order_by(Earning.date.desc()).all()
    
    return {
        "success": True,
        "count": len(earnings),
        "earnings": [
            {
                "id": e.id,
                "amount": e.amount,
                "platform": e.platform,
                "date": e.date,
                "hours": e.hours,
                "gross": e.gross,
                "deductions": e.deductions
            }
            for e in earnings
        ]
    }

@app.get("/api/earnings/city-median")
async def get_city_median(city: str = "Lahore", db: Session = Depends(get_db)):
    workers = db.query(Worker).filter(Worker.city == city, Worker.role == "worker").all()
    worker_ids = [w.id for w in workers]
    
    if not worker_ids:
        return {"success": True, "city": city, "median": 0, "message": "No workers found"}
    
    earnings = db.query(Earning).filter(Earning.worker_id.in_(worker_ids)).all()
    
    if not earnings:
        return {"success": True, "city": city, "median": 0, "message": "No earnings data"}
    
    amounts = sorted([e.amount for e in earnings])
    mid = len(amounts) // 2
    
    if len(amounts) % 2 == 0:
        median = (amounts[mid - 1] + amounts[mid]) / 2
    else:
        median = amounts[mid]
    
    return {
        "success": True,
        "city": city,
        "median": round(median, 2),
        "total_workers": len(workers),
        "total_earnings": len(earnings)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)