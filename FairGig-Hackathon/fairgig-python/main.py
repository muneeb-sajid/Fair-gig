# main.py - Auth & Earnings Service with MongoDB
# PRODUCTION READY - Using MongoDB Atlas

from fastapi import FastAPI, HTTPException, status, Depends, Header, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import shutil
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import csv
import io

load_dotenv()

app = FastAPI(title="FairGig Auth & Earnings Service")

# ==========================================
# CORS CONFIGURATION
# ==========================================
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
# MONGODB CONNECTION
# ==========================================
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://muneebsajid1247_db_user:Angry_Birds.234@cluster0.gmpxyxy.mongodb.net/fairgig?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "fairgig_auth")

# Create MongoDB client
client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

# Collections
workers_collection = db.workers
earnings_collection = db.earnings

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

def serialize_worker(worker):
    """Convert MongoDB worker document to JSON serializable format"""
    if worker:
        worker["_id"] = str(worker["_id"])
    return worker

def serialize_earning(earning):
    """Convert MongoDB earning document to JSON serializable format"""
    if earning:
        earning["_id"] = str(earning["_id"])
    return earning

# ==========================================
# JWT MIDDLEWARE
# ==========================================
async def get_current_worker(authorization: str = Header(None)):
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
        
        from bson import ObjectId
        worker = await workers_collection.find_one({"_id": ObjectId(worker_id)})
        if not worker:
            raise HTTPException(status_code=401, detail="Worker not found")
        
        if not worker.get("is_active", True):
            raise HTTPException(status_code=401, detail="Account is deactivated")
        
        return worker
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================
def require_role(allowed_roles: List[str]):
    async def role_checker(current_worker: dict = Depends(get_current_worker)):
        if current_worker.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_worker.get('role')}"
            )
        return current_worker["_id"]
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
    role: str

class EarningsUpdate(BaseModel):
    amount: Optional[float] = None
    platform: Optional[str] = None
    date: Optional[str] = None
    hours: Optional[float] = None
    gross: Optional[float] = None
    deductions: Optional[float] = None

# ==========================================
# PUBLIC API ENDPOINTS
# ==========================================

@app.get("/api/health")
async def health():
    return {"status": "OK", "service": "Auth & Earnings", "port": 8000, "database": "MongoDB"}

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(worker: WorkerRegister):
    # Check if email already exists
    existing = await workers_collection.find_one({"email": worker.email})
    if existing:
        raise HTTPException(400, "Email already registered")
    
    new_worker = {
        "name": worker.name,
        "email": worker.email,
        "password": hash_password(worker.password),
        "phone": worker.phone,
        "city": worker.city,
        "platform": worker.platform,
        "role": "worker",
        "total_earnings": 0,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    result = await workers_collection.insert_one(new_worker)
    
    token = create_token({"sub": worker.email, "worker_id": str(result.inserted_id)})
    
    return {
        "success": True,
        "message": "Worker registered",
        "worker_id": str(result.inserted_id),
        "role": "worker",
        "token": token
    }

@app.post("/api/auth/login")
async def login(login: WorkerLogin):
    worker = await workers_collection.find_one({"email": login.email})
    if not worker or not verify_password(login.password, worker["password"]):
        raise HTTPException(401, "Invalid credentials")
    
    if not worker.get("is_active", True):
        raise HTTPException(401, "Account is deactivated")
    
    token = create_token({"sub": worker["email"], "worker_id": str(worker["_id"])})
    
    return {
        "success": True,
        "token": token,
        "worker_id": str(worker["_id"]),
        "name": worker["name"],
        "role": worker.get("role", "worker")
    }

@app.get("/api/auth/profile")
async def get_profile(current_worker: dict = Depends(get_current_worker)):
    return {
        "success": True,
        "worker": {
            "id": str(current_worker["_id"]),
            "name": current_worker["name"],
            "email": current_worker["email"],
            "phone": current_worker["phone"],
            "city": current_worker["city"],
            "platform": current_worker["platform"],
            "role": current_worker.get("role", "worker"),
            "total_earnings": current_worker.get("total_earnings", 0),
            "is_active": current_worker.get("is_active", True),
            "created_at": current_worker["created_at"]
        }
    }

@app.post("/api/auth/refresh")
async def refresh_token(current_worker: dict = Depends(get_current_worker)):
    new_token = create_token({"sub": current_worker["email"], "worker_id": str(current_worker["_id"])})
    return {
        "success": True,
        "token": new_token,
        "token_type": "bearer"
    }

# ==========================================
# EARNINGS ENDPOINTS
# ==========================================

@app.post("/api/earnings")
async def add_earnings(
    amount: float = Form(...),
    platform: str = Form(...),
    date: str = Form(...),
    hours: Optional[float] = Form(None),
    gross: Optional[float] = Form(None),
    deductions: Optional[float] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    current_worker: dict = Depends(get_current_worker)
):
    if current_worker.get("role") != "worker":
        raise HTTPException(403, "Only workers can add earnings")
    
    screenshot_filename = None
    if screenshot:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"worker_{current_worker['_id']}_{timestamp}_{screenshot.filename}"
        file_path = os.path.join(UPLOAD_DIR, screenshot_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(screenshot.file, buffer)
    
    new_earning = {
        "worker_id": str(current_worker["_id"]),
        "amount": amount,
        "platform": platform,
        "date": date,
        "hours": hours,
        "gross": gross,
        "deductions": deductions,
        "screenshot": screenshot_filename,
        "verified": "pending",
        "verified_by": None,
        "verified_at": None,
        "flag_reason": None,
        "created_at": datetime.utcnow()
    }
    
    result = await earnings_collection.insert_one(new_earning)
    
    # Update worker's total earnings
    await workers_collection.update_one(
        {"_id": current_worker["_id"]},
        {"$inc": {"total_earnings": amount}}
    )
    
    return {
        "success": True, 
        "message": "Earnings added successfully",
        "earning_id": str(result.inserted_id),
        "screenshot": screenshot_filename,
        "verified": "pending"
    }

@app.get("/api/earnings/me")
async def get_my_earnings(current_worker: dict = Depends(get_current_worker)):
    earnings_cursor = earnings_collection.find({"worker_id": str(current_worker["_id"])}).sort("date", -1)
    earnings = await earnings_cursor.to_list(length=100)
    
    return {
        "success": True,
        "count": len(earnings),
        "earnings": [
            {
                "id": str(e["_id"]),
                "amount": e["amount"],
                "platform": e["platform"],
                "date": e["date"],
                "hours": e.get("hours"),
                "gross": e.get("gross"),
                "deductions": e.get("deductions"),
                "screenshot": e.get("screenshot"),
                "verified": e["verified"]
            }
            for e in earnings
        ]
    }

@app.put("/api/earnings/{earning_id}")
async def update_earning(
    earning_id: str,
    update_data: EarningsUpdate,
    current_worker: dict = Depends(get_current_worker)
):
    from bson import ObjectId
    earning = await earnings_collection.find_one({"_id": ObjectId(earning_id)})
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    if current_worker.get("role") == "worker" and earning["worker_id"] != str(current_worker["_id"]):
        raise HTTPException(403, "You can only update your own earnings")
    
    old_amount = earning["amount"]
    
    update_dict = {}
    if update_data.amount is not None:
        update_dict["amount"] = update_data.amount
        update_dict["verified"] = "pending"
        update_dict["verified_by"] = None
        update_dict["verified_at"] = None
    if update_data.platform is not None:
        update_dict["platform"] = update_data.platform
    if update_data.date is not None:
        update_dict["date"] = update_data.date
    if update_data.hours is not None:
        update_dict["hours"] = update_data.hours
    if update_data.gross is not None:
        update_dict["gross"] = update_data.gross
    if update_data.deductions is not None:
        update_dict["deductions"] = update_data.deductions
    
    if update_dict:
        await earnings_collection.update_one(
            {"_id": ObjectId(earning_id)},
            {"$set": update_dict}
        )
        
        # Update worker's total earnings if amount changed
        if update_data.amount is not None:
            await workers_collection.update_one(
                {"_id": ObjectId(earning["worker_id"])},
                {"$inc": {"total_earnings": update_data.amount - old_amount}}
            )
    
    return {
        "success": True,
        "message": "Earning updated successfully"
    }

@app.delete("/api/earnings/{earning_id}")
async def delete_earning(
    earning_id: str,
    current_worker: dict = Depends(get_current_worker)
):
    from bson import ObjectId
    earning = await earnings_collection.find_one({"_id": ObjectId(earning_id)})
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    if current_worker.get("role") == "worker" and earning["worker_id"] != str(current_worker["_id"]):
        raise HTTPException(403, "You can only delete your own earnings")
    
    # Update worker's total earnings
    await workers_collection.update_one(
        {"_id": ObjectId(earning["worker_id"])},
        {"$inc": {"total_earnings": -earning["amount"]}}
    )
    
    await earnings_collection.delete_one({"_id": ObjectId(earning_id)})
    
    return {
        "success": True,
        "message": "Earning deleted successfully"
    }

@app.get("/api/earnings/city-median")
async def get_city_median(city: str = "Lahore"):
    workers_cursor = workers_collection.find({"city": city, "role": "worker"})
    workers = await workers_cursor.to_list(length=1000)
    worker_ids = [str(w["_id"]) for w in workers]
    
    if not worker_ids:
        return {"success": True, "city": city, "median": 0, "message": "No workers found"}
    
    earnings_cursor = earnings_collection.find({"worker_id": {"$in": worker_ids}})
    earnings = await earnings_cursor.to_list(length=10000)
    
    if not earnings:
        return {"success": True, "city": city, "median": 0, "message": "No earnings data"}
    
    amounts = sorted([e["amount"] for e in earnings])
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
# VERIFICATION ENDPOINTS (Advocate/Admin)
# ==========================================

@app.get("/api/verification/queue")
async def get_verification_queue(current_worker_id: str = Depends(require_role(["advocate", "admin"]))):
    pending_cursor = earnings_collection.find({"verified": "pending"}).sort("created_at", -1)
    pending_earnings = await pending_cursor.to_list(length=100)
    
    result = []
    for earning in pending_earnings:
        from bson import ObjectId
        worker = await workers_collection.find_one({"_id": ObjectId(earning["worker_id"])})
        result.append({
            "id": str(earning["_id"]),
            "worker": {
                "id": str(worker["_id"]),
                "name": worker["name"],
                "email": worker["email"],
                "platform": worker["platform"]
            },
            "amount": earning["amount"],
            "platform": earning["platform"],
            "date": earning["date"],
            "hours": earning.get("hours"),
            "gross": earning.get("gross"),
            "deductions": earning.get("deductions"),
            "screenshot": earning.get("screenshot"),
            "verified": earning["verified"],
            "created_at": earning["created_at"]
        })
    
    return {
        "success": True,
        "count": len(result),
        "queue": result
    }

@app.get("/api/screenshot/{filename}")
async def get_screenshot(
    filename: str,
    current_worker_id: str = Depends(require_role(["advocate", "admin"]))
):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(404, "Screenshot not found")

@app.put("/api/verification/{earning_id}/approve")
async def approve_earning(
    earning_id: str,
    action: VerificationAction,
    current_worker_id: str = Depends(require_role(["advocate", "admin"]))
):
    from bson import ObjectId
    earning = await earnings_collection.find_one({"_id": ObjectId(earning_id)})
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    await earnings_collection.update_one(
        {"_id": ObjectId(earning_id)},
        {"$set": {
            "verified": "approved",
            "verified_by": action.verified_by,
            "verified_at": datetime.utcnow()
        }}
    )
    
    return {
        "success": True,
        "message": "Earning approved successfully",
        "earning_id": earning_id,
        "verified": "approved"
    }

@app.put("/api/verification/{earning_id}/flag")
async def flag_earning(
    earning_id: str,
    action: VerificationAction,
    current_worker_id: str = Depends(require_role(["advocate", "admin"]))
):
    from bson import ObjectId
    earning = await earnings_collection.find_one({"_id": ObjectId(earning_id)})
    if not earning:
        raise HTTPException(404, "Earning not found")
    
    await earnings_collection.update_one(
        {"_id": ObjectId(earning_id)},
        {"$set": {
            "verified": "flagged",
            "verified_by": action.verified_by,
            "verified_at": datetime.utcnow(),
            "flag_reason": action.flag_reason or "Suspicious activity detected"
        }}
    )
    
    return {
        "success": True,
        "message": "Earning flagged for review",
        "earning_id": earning_id,
        "verified": "flagged",
        "flag_reason": action.flag_reason
    }

# ==========================================
# ADMIN-ONLY ENDPOINTS
# ==========================================

@app.get("/api/admin/workers")
async def get_all_workers(current_worker_id: str = Depends(require_role(["admin"]))):
    workers_cursor = workers_collection.find()
    workers = await workers_cursor.to_list(length=1000)
    
    return {
        "success": True,
        "count": len(workers),
        "workers": [
            {
                "id": str(w["_id"]),
                "name": w["name"],
                "email": w["email"],
                "phone": w["phone"],
                "city": w["city"],
                "platform": w["platform"],
                "role": w.get("role", "worker"),
                "total_earnings": w.get("total_earnings", 0),
                "is_active": w.get("is_active", True),
                "created_at": w["created_at"]
            }
            for w in workers
        ]
    }

@app.put("/api/admin/workers/{worker_id}/role")
async def update_worker_role(
    worker_id: str,
    role_update: RoleUpdate,
    current_worker_id: str = Depends(require_role(["admin"]))
):
    from bson import ObjectId
    if role_update.role not in ["worker", "advocate", "admin"]:
        raise HTTPException(400, "Invalid role. Must be: worker, advocate, admin")
    
    worker = await workers_collection.find_one({"_id": ObjectId(worker_id)})
    if not worker:
        raise HTTPException(404, "Worker not found")
    
    await workers_collection.update_one(
        {"_id": ObjectId(worker_id)},
        {"$set": {"role": role_update.role}}
    )
    
    return {
        "success": True,
        "message": f"Worker role updated to {role_update.role}",
        "worker_id": worker_id,
        "new_role": role_update.role
    }

@app.put("/api/admin/workers/{worker_id}/status")
async def update_worker_status(
    worker_id: str,
    is_active: bool,
    current_worker_id: str = Depends(require_role(["admin"]))
):
    from bson import ObjectId
    worker = await workers_collection.find_one({"_id": ObjectId(worker_id)})
    if not worker:
        raise HTTPException(404, "Worker not found")
    
    await workers_collection.update_one(
        {"_id": ObjectId(worker_id)},
        {"$set": {"is_active": is_active}}
    )
    
    return {
        "success": True,
        "message": f"Worker {'activated' if is_active else 'deactivated'}",
        "worker_id": worker_id,
        "is_active": is_active
    }

@app.get("/api/admin/stats")
async def get_admin_stats(current_worker_id: str = Depends(require_role(["admin"]))):
    total_workers = await workers_collection.count_documents({"role": "worker"})
    total_advocates = await workers_collection.count_documents({"role": "advocate"})
    total_admins = await workers_collection.count_documents({"role": "admin"})
    total_earnings = await earnings_collection.count_documents({})
    total_approved = await earnings_collection.count_documents({"verified": "approved"})
    total_pending = await earnings_collection.count_documents({"verified": "pending"})
    total_flagged = await earnings_collection.count_documents({"verified": "flagged"})
    
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
# CSV IMPORT
# ==========================================

@app.post("/api/earnings/csv-import")
async def import_earnings_csv(
    file: UploadFile = File(...),
    current_worker: dict = Depends(get_current_worker)
):
    if current_worker.get("role") != "worker":
        raise HTTPException(403, "Only workers can import earnings")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are allowed")
    
    try:
        content = await file.read()
        csv_text = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        expected_headers = ['date', 'platform', 'hours', 'gross', 'deductions', 'net']
        headers = csv_reader.fieldnames
        if not headers or not all(h in headers for h in expected_headers):
            raise HTTPException(400, f"CSV must have columns: {', '.join(expected_headers)}")
        
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                date = row.get('date', '').strip()
                platform = row.get('platform', '').strip()
                hours = float(row.get('hours', 0))
                gross = float(row.get('gross', 0))
                deductions = float(row.get('deductions', 0))
                net = float(row.get('net', 0))
                
                if not date or not platform:
                    errors.append(f"Row {row_num}: Missing date or platform")
                    continue
                
                if net <= 0:
                    errors.append(f"Row {row_num}: Net amount must be greater than 0")
                    continue
                
                new_earning = {
                    "worker_id": str(current_worker["_id"]),
                    "amount": net,
                    "platform": platform,
                    "date": date,
                    "hours": hours,
                    "gross": gross,
                    "deductions": deductions,
                    "screenshot": None,
                    "verified": "pending",
                    "verified_by": None,
                    "verified_at": None,
                    "flag_reason": None,
                    "created_at": datetime.utcnow()
                }
                
                await earnings_collection.insert_one(new_earning)
                await workers_collection.update_one(
                    {"_id": current_worker["_id"]},
                    {"$inc": {"total_earnings": net}}
                )
                imported_count += 1
                
            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid number format - {str(e)}")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        return {
            "success": True,
            "message": f"CSV import completed",
            "imported_count": imported_count,
            "error_count": len(errors),
            "errors": errors[:10]
        }
        
    except Exception as e:
        raise HTTPException(500, f"CSV import failed: {str(e)}")

# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================

@app.get("/api/analytics/platform-commissions")
async def get_platform_commissions(
    platform: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    filter_query = {
        "gross": {"$ne": None},
        "deductions": {"$ne": None}
    }
    if platform:
        filter_query["platform"] = platform
    if start_date:
        filter_query["date"] = {"$gte": start_date}
    if end_date:
        if "date" in filter_query:
            filter_query["date"]["$lte"] = end_date
        else:
            filter_query["date"] = {"$lte": end_date}
    
    earnings_cursor = earnings_collection.find(filter_query)
    earnings = await earnings_cursor.to_list(length=10000)
    
    commission_data = []
    platform_stats = {}
    
    for earning in earnings:
        if earning.get("gross", 0) > 0:
            commission_percent = (earning.get("deductions", 0) / earning["gross"]) * 100
        else:
            commission_percent = 0
        
        commission_data.append({
            "platform": earning["platform"],
            "date": earning["date"],
            "commission_percent": round(commission_percent, 2),
            "gross": earning["gross"],
            "deductions": earning.get("deductions", 0)
        })
        
        if earning["platform"] not in platform_stats:
            platform_stats[earning["platform"]] = {
                "total_commissions": 0,
                "total_gross": 0,
                "count": 0
            }
        platform_stats[earning["platform"]]["total_commissions"] += earning.get("deductions", 0)
        platform_stats[earning["platform"]]["total_gross"] += earning["gross"]
        platform_stats[earning["platform"]]["count"] += 1
    
    platform_averages = {}
    for plat, stats in platform_stats.items():
        if stats["total_gross"] > 0:
            platform_averages[plat] = round((stats["total_commissions"] / stats["total_gross"]) * 100, 2)
        else:
            platform_averages[plat] = 0
    
    return {
        "success": True,
        "platform_averages": platform_averages,
        "trend_data": commission_data[-50:],
        "total_records": len(commission_data)
    }

@app.get("/api/analytics/earnings-trends")
async def get_earnings_trends(
    period: str = "weekly",
    current_worker: dict = Depends(get_current_worker)
):
    earnings_cursor = earnings_collection.find({"worker_id": str(current_worker["_id"])})
    earnings = await earnings_cursor.to_list(length=1000)
    
    if period == "weekly":
        trends = {}
        for earning in earnings:
            earning_date = datetime.strptime(earning["date"], "%Y-%m-%d")
            week_key = f"{earning_date.year}-W{earning_date.isocalendar()[1]}"
            
            if week_key not in trends:
                trends[week_key] = {
                    "week": week_key,
                    "total_earnings": 0,
                    "total_hours": 0,
                    "count": 0
                }
            trends[week_key]["total_earnings"] += earning["amount"]
            trends[week_key]["total_hours"] += earning.get("hours", 0)
            trends[week_key]["count"] += 1
        
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
        trends = {}
        for earning in earnings:
            earning_date = datetime.strptime(earning["date"], "%Y-%m-%d")
            month_key = f"{earning_date.year}-{earning_date.month:02d}"
            
            if month_key not in trends:
                trends[month_key] = {
                    "month": month_key,
                    "total_earnings": 0,
                    "total_hours": 0,
                    "count": 0
                }
            trends[month_key]["total_earnings"] += earning["amount"]
            trends[month_key]["total_hours"] += earning.get("hours", 0)
            trends[month_key]["count"] += 1
        
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

@app.get("/api/analytics/hourly-rate")
async def get_hourly_rate_trend(current_worker: dict = Depends(get_current_worker)):
    filter_query = {
        "worker_id": str(current_worker["_id"]),
        "hours": {"$ne": None, "$gt": 0}
    }
    earnings_cursor = earnings_collection.find(filter_query).sort("date", 1)
    earnings = await earnings_cursor.to_list(length=1000)
    
    hourly_rates = []
    for earning in earnings:
        hourly_rate = earning["amount"] / earning["hours"]
        hourly_rates.append({
            "date": earning["date"],
            "hourly_rate": round(hourly_rate, 2),
            "amount": earning["amount"],
            "hours": earning["hours"],
            "platform": earning["platform"]
        })
    
    if hourly_rates:
        avg_hourly_rate = sum(h["hourly_rate"] for h in hourly_rates) / len(hourly_rates)
    else:
        avg_hourly_rate = 0
    
    return {
        "success": True,
        "average_hourly_rate": round(avg_hourly_rate, 2),
        "trend": hourly_rates[-30:],
        "total_shifts": len(hourly_rates)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
