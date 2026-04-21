# main.py - Auth & Earnings Service (Port 8000)
# WITH FULL ROLE-BASED ACCESS CONTROL

from fastapi import FastAPI, HTTPException, status, Depends, Header, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
import csv
import io


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
# CREATE UPLOADS FOLDER
# ==========================================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    role = Column(String, default="worker")  # worker, advocate, admin
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
    screenshot = Column(String, nullable=True)
    verified = Column(String, default="pending")  # pending, approved, flagged
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    flag_reason = Column(String, nullable=True)
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
# DEPENDENCIES
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_worker(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract worker_id from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        worker_id = payload.get("worker_id")
        
        if not worker_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            raise HTTPException(status_code=401, detail="Worker not found")
        
        if not worker.is_active:
            raise HTTPException(status_code=401, detail="Account is deactivated")
        
        return worker
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================
def require_role(allowed_roles: List[str]):
    """Middleware to check if user has required role"""
    def role_checker(current_worker: Worker = Depends(get_current_worker)):
        if current_worker.role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_worker.role}"
            )
        return current_worker.id
    return role_checker

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

class VerificationAction(BaseModel):
    verified_by: str = "advocate"
    flag_reason: Optional[str] = None

class RoleUpdate(BaseModel):
    role: str  # worker, advocate, admin

class EarningsUpdate(BaseModel):
    amount: Optional[float] = None
    platform: Optional[str] = None
    date: Optional[str] = None
    hours: Optional[float] = None
    gross: Optional[float] = None
    deductions: Optional[float] = None


# ==========================================
# PUBLIC API ENDPOINTS (No Auth Required)
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
        platform=worker.platform,
        role="worker"  # Default role
    )
    db.add(new_worker)
    db.commit()
    db.refresh(new_worker)
    
    token = create_token({"sub": worker.email, "worker_id": new_worker.id})
    
    return {
        "success": True,
        "message": "Worker registered",
        "worker_id": new_worker.id,
        "role": new_worker.role,
        "token": token
    }

@app.post("/api/auth/login")
async def login(login: WorkerLogin, db: Session = Depends(get_db)):
    worker = db.query(Worker).filter(Worker.email == login.email).first()
    if not worker or not verify_password(login.password, worker.password):
        raise HTTPException(401, "Invalid credentials")
    
    if not worker.is_active:
        raise HTTPException(401, "Account is deactivated")
    
    token = create_token({"sub": worker.email, "worker_id": worker.id})
    
    return {
        "success": True,
        "token": token,
        "worker_id": worker.id,
        "name": worker.name,
        "role": worker.role
    }
@app.put("/api/earnings/{earning_id}")
async def update_earning(
    earning_id: int,
    update_data: EarningsUpdate,
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    """Update an existing earning record (Worker can update their own, Advocate/Admin can update any)"""
    
    # Find the earning
    earning = db.query(Earning).filter(Earning.id == earning_id).first()
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    # Check permission
    if current_worker.role == "worker" and earning.worker_id != current_worker.id:
        raise HTTPException(403, "You can only update your own earnings")
    
    # Calculate old amount for total_earnings adjustment
    old_amount = earning.amount
    
    # Update fields if provided
    if update_data.amount is not None:
        earning.amount = update_data.amount
    if update_data.platform is not None:
        earning.platform = update_data.platform
    if update_data.date is not None:
        earning.date = update_data.date
    if update_data.hours is not None:
        earning.hours = update_data.hours
    if update_data.gross is not None:
        earning.gross = update_data.gross
    if update_data.deductions is not None:
        earning.deductions = update_data.deductions
    
    # Reset verification status if amount changed
    if update_data.amount is not None and update_data.amount != old_amount:
        earning.verified = "pending"
        earning.verified_by = None
        earning.verified_at = None
    
    # Update worker's total earnings
    worker = db.query(Worker).filter(Worker.id == earning.worker_id).first()
    if worker and update_data.amount is not None:
        worker.total_earnings = worker.total_earnings - old_amount + update_data.amount
    
    db.commit()
    db.refresh(earning)
    
    return {
        "success": True,
        "message": "Earning updated successfully",
        "earning": {
            "id": earning.id,
            "amount": earning.amount,
            "platform": earning.platform,
            "date": earning.date,
            "hours": earning.hours,
            "gross": earning.gross,
            "deductions": earning.deductions,
            "verified": earning.verified
        }
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
# ==========================================
# DELETE EARNINGS ENDPOINT
# ==========================================

@app.delete("/api/earnings/{earning_id}")
async def delete_earning(
    earning_id: int,
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    """Delete an earning record (Worker can delete their own, Advocate/Admin can delete any)"""
    
    # Find the earning
    earning = db.query(Earning).filter(Earning.id == earning_id).first()
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    # Check permission
    if current_worker.role == "worker" and earning.worker_id != current_worker.id:
        raise HTTPException(403, "You can only delete your own earnings")
    
    # Update worker's total earnings
    worker = db.query(Worker).filter(Worker.id == earning.worker_id).first()
    if worker:
        worker.total_earnings -= earning.amount
    
    # Delete the earning
    db.delete(earning)
    db.commit()
    
    return {
        "success": True,
        "message": "Earning deleted successfully",
        "earning_id": earning_id
    }
    # ==========================================
# PLATFORM COMMISSION TRACKER
# ==========================================

@app.get("/api/analytics/platform-commissions")
async def get_platform_commissions(
    platform: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Track platform commission rates over time"""
    
    query = db.query(Earning).filter(Earning.gross.isnot(None), Earning.deductions.isnot(None))
    
    if platform:
        query = query.filter(Earning.platform == platform)
    if start_date:
        query = query.filter(Earning.date >= start_date)
    if end_date:
        query = query.filter(Earning.date <= end_date)
    
    earnings = query.all()
    
    # Calculate commission percentage for each earning
    commission_data = []
    platform_stats = {}
    
    for earning in earnings:
        if earning.gross > 0:
            commission_percent = (earning.deductions / earning.gross) * 100
        else:
            commission_percent = 0
        
        commission_data.append({
            "platform": earning.platform,
            "date": earning.date,
            "commission_percent": round(commission_percent, 2),
            "gross": earning.gross,
            "deductions": earning.deductions
        })
        
        # Aggregate by platform
        if earning.platform not in platform_stats:
            platform_stats[earning.platform] = {
                "total_commissions": 0,
                "total_gross": 0,
                "count": 0
            }
        platform_stats[earning.platform]["total_commissions"] += earning.deductions
        platform_stats[earning.platform]["total_gross"] += earning.gross
        platform_stats[earning.platform]["count"] += 1
    
    # Calculate average commission per platform
    platform_averages = {}
    for plat, stats in platform_stats.items():
        if stats["total_gross"] > 0:
            platform_averages[plat] = round((stats["total_commissions"] / stats["total_gross"]) * 100, 2)
        else:
            platform_averages[plat] = 0
    
    return {
        "success": True,
        "platform_averages": platform_averages,
        "trend_data": commission_data[-50:],  # Last 50 records for trend
        "total_records": len(commission_data)
    }
    # ==========================================
# WEEKLY/MONTHLY EARNINGS TRENDS
# ==========================================

from calendar import monthrange

@app.get("/api/analytics/earnings-trends")
async def get_earnings_trends(
    period: str = "weekly",  # weekly, monthly
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    """Get worker's earnings trends by week or month"""
    
    earnings = db.query(Earning).filter(Earning.worker_id == current_worker.id).all()
    
    if period == "weekly":
        # Group by week
        trends = {}
        for earning in earnings:
            # Parse date
            earning_date = datetime.strptime(earning.date, "%Y-%m-%d")
            # Get week number and year
            week_key = f"{earning_date.year}-W{earning_date.isocalendar()[1]}"
            
            if week_key not in trends:
                trends[week_key] = {
                    "week": week_key,
                    "total_earnings": 0,
                    "total_hours": 0,
                    "count": 0
                }
            trends[week_key]["total_earnings"] += earning.amount
            trends[week_key]["total_hours"] += earning.hours or 0
            trends[week_key]["count"] += 1
        
        # Calculate hourly rates
        for week in trends.values():
            if week["total_hours"] > 0:
                week["hourly_rate"] = round(week["total_earnings"] / week["total_hours"], 2)
            else:
                week["hourly_rate"] = 0
        
        return {
            "success": True,
            "period": "weekly",
            "trends": list(trends.values())
        }
    
    elif period == "monthly":
        # Group by month
        trends = {}
        for earning in earnings:
            # Parse date
            earning_date = datetime.strptime(earning.date, "%Y-%m-%d")
            month_key = f"{earning_date.year}-{earning_date.month:02d}"
            
            if month_key not in trends:
                trends[month_key] = {
                    "month": month_key,
                    "total_earnings": 0,
                    "total_hours": 0,
                    "count": 0
                }
            trends[month_key]["total_earnings"] += earning.amount
            trends[month_key]["total_hours"] += earning.hours or 0
            trends[month_key]["count"] += 1
        
        # Calculate hourly rates
        for month in trends.values():
            if month["total_hours"] > 0:
                month["hourly_rate"] = round(month["total_earnings"] / month["total_hours"], 2)
            else:
                month["hourly_rate"] = 0
        
        return {
            "success": True,
            "period": "monthly",
            "trends": list(trends.values())
        }
    
    else:
        raise HTTPException(400, "Period must be 'weekly' or 'monthly'")
        # ==========================================
# EFFECTIVE HOURLY RATE TRACKER
# ==========================================

@app.get("/api/analytics/hourly-rate")
async def get_hourly_rate_trend(
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    """Track effective hourly rate over time"""
    
    earnings = db.query(Earning).filter(
        Earning.worker_id == current_worker.id,
        Earning.hours.isnot(None),
        Earning.hours > 0
    ).order_by(Earning.date.asc()).all()
    
    hourly_rates = []
    for earning in earnings:
        hourly_rate = earning.amount / earning.hours
        hourly_rates.append({
            "date": earning.date,
            "hourly_rate": round(hourly_rate, 2),
            "amount": earning.amount,
            "hours": earning.hours,
            "platform": earning.platform
        })
    
    # Calculate average hourly rate
    if hourly_rates:
        avg_hourly_rate = sum(h["hourly_rate"] for h in hourly_rates) / len(hourly_rates)
    else:
        avg_hourly_rate = 0
    
    return {
        "success": True,
        "average_hourly_rate": round(avg_hourly_rate, 2),
        "trend": hourly_rates[-30:],  # Last 30 records
        "total_shifts": len(hourly_rates)
    }
# ==========================================
# WORKER-ONLY API ENDPOINTS (Role: worker)
# ==========================================

@app.get("/api/auth/profile")
async def get_profile(
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    return {
        "success": True,
        "worker": {
            "id": current_worker.id,
            "name": current_worker.name,
            "email": current_worker.email,
            "phone": current_worker.phone,
            "city": current_worker.city,
            "platform": current_worker.platform,
            "role": current_worker.role,
            "total_earnings": current_worker.total_earnings,
            "is_active": current_worker.is_active,
            "created_at": current_worker.created_at
        }
    }

@app.post("/api/earnings")
async def add_earnings(
    amount: float = Form(...),
    platform: str = Form(...),
    date: str = Form(...),
    hours: Optional[float] = Form(None),
    gross: Optional[float] = Form(None),
    deductions: Optional[float] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    # Only workers can add earnings
    if current_worker.role != "worker":
        raise HTTPException(403, "Only workers can add earnings")
    
    # Save screenshot if uploaded
    screenshot_filename = None
    if screenshot:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"worker_{current_worker.id}_{timestamp}_{screenshot.filename}"
        file_path = os.path.join(UPLOAD_DIR, screenshot_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(screenshot.file, buffer)
    
    new_earning = Earning(
        worker_id=current_worker.id,
        amount=amount,
        platform=platform,
        date=date,
        hours=hours,
        gross=gross,
        deductions=deductions,
        screenshot=screenshot_filename,
        verified="pending"
    )
    db.add(new_earning)
    current_worker.total_earnings += amount
    db.commit()
    db.refresh(new_earning)
    
    return {
        "success": True, 
        "message": "Earnings added successfully",
        "earning_id": new_earning.id,
        "screenshot": screenshot_filename,
        "verified": new_earning.verified
    }

@app.get("/api/earnings/me")
async def get_my_earnings(
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    earnings = db.query(Earning).filter(Earning.worker_id == current_worker.id).order_by(Earning.date.desc()).all()
    
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
                "deductions": e.deductions,
                "screenshot": e.screenshot,
                "verified": e.verified
            }
            for e in earnings
        ]
    }

# ==========================================
# ADVOCATE & ADMIN API ENDPOINTS
# ==========================================

@app.get("/api/earnings/{user_id}")
async def get_earnings_by_user(
    user_id: int, 
    current_worker_id: int = Depends(require_role(["advocate", "admin"])),
    db: Session = Depends(get_db)
):
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
                "deductions": e.deductions,
                "screenshot": e.screenshot,
                "verified": e.verified
            }
            for e in earnings
        ]
    }

@app.get("/api/verification/queue")
async def get_verification_queue(
    current_worker_id: int = Depends(require_role(["advocate", "admin"])),
    db: Session = Depends(get_db)
):
    pending_earnings = db.query(Earning).filter(Earning.verified == "pending").order_by(Earning.created_at.desc()).all()
    
    result = []
    for earning in pending_earnings:
        worker = db.query(Worker).filter(Worker.id == earning.worker_id).first()
        result.append({
            "id": earning.id,
            "worker": {
                "id": worker.id,
                "name": worker.name,
                "email": worker.email,
                "platform": worker.platform
            },
            "amount": earning.amount,
            "platform": earning.platform,
            "date": earning.date,
            "hours": earning.hours,
            "gross": earning.gross,
            "deductions": earning.deductions,
            "screenshot": earning.screenshot,
            "verified": earning.verified,
            "created_at": earning.created_at
        })
    
    return {
        "success": True,
        "count": len(result),
        "queue": result
    }

@app.get("/api/screenshot/{filename}")
async def get_screenshot(
    filename: str,
    current_worker_id: int = Depends(require_role(["advocate", "admin"]))
):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(404, "Screenshot not found")

@app.put("/api/verification/{earning_id}/approve")
async def approve_earning(
    earning_id: int,
    action: VerificationAction,
    current_worker_id: int = Depends(require_role(["advocate", "admin"])),
    db: Session = Depends(get_db)
):
    earning = db.query(Earning).filter(Earning.id == earning_id).first()
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    earning.verified = "approved"
    earning.verified_by = action.verified_by
    earning.verified_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "Earning approved successfully",
        "earning_id": earning.id,
        "verified": earning.verified
    }

@app.put("/api/verification/{earning_id}/flag")
async def flag_earning(
    earning_id: int,
    action: VerificationAction,
    current_worker_id: int = Depends(require_role(["advocate", "admin"])),
    db: Session = Depends(get_db)
):
    earning = db.query(Earning).filter(Earning.id == earning_id).first()
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    earning.verified = "flagged"
    earning.verified_by = action.verified_by
    earning.verified_at = datetime.utcnow()
    earning.flag_reason = action.flag_reason or "Suspicious activity detected"
    db.commit()
    
    return {
        "success": True,
        "message": "Earning flagged for review",
        "earning_id": earning.id,
        "verified": earning.verified,
        "flag_reason": earning.flag_reason
    }

# ==========================================
# ADMIN-ONLY API ENDPOINTS
# ==========================================

@app.get("/api/admin/workers")
async def get_all_workers(
    current_worker_id: int = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    workers = db.query(Worker).all()
    
    return {
        "success": True,
        "count": len(workers),
        "workers": [
            {
                "id": w.id,
                "name": w.name,
                "email": w.email,
                "phone": w.phone,
                "city": w.city,
                "platform": w.platform,
                "role": w.role,
                "total_earnings": w.total_earnings,
                "is_active": w.is_active,
                "created_at": w.created_at
            }
            for w in workers
        ]
    }

@app.put("/api/admin/workers/{worker_id}/role")
async def update_worker_role(
    worker_id: int,
    role_update: RoleUpdate,
    current_worker_id: int = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    if role_update.role not in ["worker", "advocate", "admin"]:
        raise HTTPException(400, "Invalid role. Must be: worker, advocate, admin")
    
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(404, "Worker not found")
    
    worker.role = role_update.role
    db.commit()
    
    return {
        "success": True,
        "message": f"Worker role updated to {role_update.role}",
        "worker_id": worker.id,
        "new_role": worker.role
    }

@app.put("/api/admin/workers/{worker_id}/status")
async def update_worker_status(
    worker_id: int,
    is_active: bool,
    current_worker_id: int = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(404, "Worker not found")
    
    worker.is_active = is_active
    db.commit()
    
    return {
        "success": True,
        "message": f"Worker {'activated' if is_active else 'deactivated'}",
        "worker_id": worker.id,
        "is_active": worker.is_active
    }

@app.get("/api/admin/stats")
async def get_admin_stats(
    current_worker_id: int = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    total_workers = db.query(Worker).filter(Worker.role == "worker").count()
    total_advocates = db.query(Worker).filter(Worker.role == "advocate").count()
    total_admins = db.query(Worker).filter(Worker.role == "admin").count()
    total_earnings = db.query(Earning).count()
    total_approved = db.query(Earning).filter(Earning.verified == "approved").count()
    total_pending = db.query(Earning).filter(Earning.verified == "pending").count()
    total_flagged = db.query(Earning).filter(Earning.verified == "flagged").count()
    
    return {
        "success": True,
        "stats": {
            "users": {
                "workers": total_workers,
                "advocates": total_advocates,
                "admins": total_admins,
                "total": total_workers + total_advocates + total_admins
            },
            "earnings": {
                "total": total_earnings,
                "approved": total_approved,
                "pending": total_pending,
                "flagged": total_flagged
            }
        }
    }

    # ==========================================
# TOKEN REFRESH ENDPOINT
# ==========================================

@app.post("/api/auth/refresh")
async def refresh_token(
    current_worker: Worker = Depends(get_current_worker)
):
    """Generate new access token using existing valid token"""
    
    # Create new token
    new_token = create_token({"sub": current_worker.email, "worker_id": current_worker.id})
    
    return {
        "success": True,
        "token": new_token,
        "token_type": "bearer"
    }
# ==========================================
# CSV IMPORT FOR EARNINGS (Bulk Upload)
# ==========================================



@app.post("/api/earnings/csv-import")
async def import_earnings_csv(
    file: UploadFile = File(...),
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db)
):
    """Bulk import earnings from CSV file"""
    
    # Only workers can import their own earnings
    if current_worker.role != "worker":
        raise HTTPException(403, "Only workers can import earnings")
    
    # Check file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are allowed")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_text = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Expected CSV headers
        expected_headers = ['date', 'platform', 'hours', 'gross', 'deductions', 'net']
        
        # Validate headers
        headers = csv_reader.fieldnames
        if not headers or not all(h in headers for h in expected_headers):
            raise HTTPException(400, f"CSV must have columns: {', '.join(expected_headers)}")
        
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Parse and validate data
                date = row.get('date', '').strip()
                platform = row.get('platform', '').strip()
                hours = float(row.get('hours', 0))
                gross = float(row.get('gross', 0))
                deductions = float(row.get('deductions', 0))
                net = float(row.get('net', 0))
                
                # Validate required fields
                if not date or not platform:
                    errors.append(f"Row {row_num}: Missing date or platform")
                    continue
                
                if net <= 0:
                    errors.append(f"Row {row_num}: Net amount must be greater than 0")
                    continue
                
                # Create earning record
                new_earning = Earning(
                    worker_id=current_worker.id,
                    amount=net,
                    platform=platform,
                    date=date,
                    hours=hours,
                    gross=gross,
                    deductions=deductions,
                    screenshot=None,  # No screenshot for CSV import
                    verified="pending"  # Needs verification
                )
                db.add(new_earning)
                current_worker.total_earnings += net
                imported_count += 1
                
            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid number format - {str(e)}")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"CSV import completed",
            "imported_count": imported_count,
            "error_count": len(errors),
            "errors": errors[:10]  # Return first 10 errors only
        }
        
    except Exception as e:
        raise HTTPException(500, f"CSV import failed: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
