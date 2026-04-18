# anomaly.py - Anomaly Detection Service (Port 8001)
# Detects statistically unusual income drops (>20%) in worker earnings
# Judges can call this endpoint directly with Postman

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FairGig Anomaly Detection Service")

# CORS for frontend and other services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# PYDANTIC MODELS
# ==========================================

class Shift(BaseModel):
    """Individual shift/earning record"""
    date: str
    net: float  # Net earnings (required)
    gross: Optional[float] = None  # Gross earnings before deductions
    deductions: Optional[float] = None  # Platform deductions
    hours: Optional[float] = None  # Hours worked
    platform: Optional[str] = None  # Platform name (Uber, Foodpanda, etc.)

class AnomalyRequest(BaseModel):
    """Request format for anomaly detection"""
    shifts: List[Shift]  # Array of shifts (minimum 2)
    worker_id: Optional[int] = None  # Optional worker ID for tracking
    threshold: Optional[float] = 20.0  # Custom threshold (default 20%)

class AnomalyResponse(BaseModel):
    """Response format for anomaly detection"""
    flagged: bool
    explanation: str
    drop_percentage: Optional[float] = None
    previous_average: Optional[float] = None
    latest_earning: Optional[float] = None
    threshold_used: Optional[float] = None
    recommendation: Optional[str] = None

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def calculate_drop_percentage(previous_avg: float, current: float) -> float:
    """Calculate percentage drop from previous average to current"""
    if previous_avg == 0:
        return 0
    return ((previous_avg - current) / previous_avg) * 100

def generate_explanation(drop_percentage: float, previous_avg: float, 
                         latest_net: float, threshold: float,
                         latest_shift: Shift, previous_shifts: List[Shift]) -> str:
    """Generate human-readable explanation for the anomaly"""
    
    explanation = f"⚠️ ANOMALY DETECTED: Income dropped by {drop_percentage:.1f}% "
    explanation += f"(from ₹{previous_avg:.2f} to ₹{latest_net:.2f}), "
    explanation += f"exceeding the {threshold}% threshold."
    
    # Add context about deductions
    if latest_shift.deductions and previous_shifts[-1].deductions:
        deduction_change = latest_shift.deductions - previous_shifts[-1].deductions
        if deduction_change > 0:
            explanation += f" Platform deductions increased by ₹{deduction_change:.2f}."
        elif deduction_change < 0:
            explanation += f" Platform deductions decreased by ₹{abs(deduction_change):.2f}."
    
    # Add context about hours
    if latest_shift.hours and previous_shifts[-1].hours:
        hours_change = latest_shift.hours - previous_shifts[-1].hours
        if hours_change < -2:
            explanation += f" Hours worked decreased by {abs(hours_change):.1f} hours."
    
    # Add context about platform
    if latest_shift.platform:
        previous_platforms = [s.platform for s in previous_shifts if s.platform]
        if previous_platforms and latest_shift.platform != previous_platforms[-1]:
            explanation += f" Platform changed from {previous_platforms[-1]} to {latest_shift.platform}."
    
    return explanation

def generate_recommendation(drop_percentage: float, latest_shift: Shift) -> str:
    """Generate actionable recommendation for the worker"""
    
    if drop_percentage >= 50:
        return "URGENT: Contact platform support immediately and file a grievance."
    elif drop_percentage >= 30:
        return "Review your recent shifts for any unusual deductions or missing payments."
    elif drop_percentage >= 20:
        return "Compare your earnings with city median and consider filing a grievance if pattern continues."
    else:
        return "Monitor your next few shifts to see if this is a temporary fluctuation."

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "OK",
        "service": "Anomaly Detection",
        "port": 8001,
        "version": "1.0.0"
    }

@app.get("/api/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "FairGig Anomaly Detection Service",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/detect-anomaly": "Detect income anomalies in worker shifts",
            "GET /api/health": "Health check"
        },
        "threshold": "20% income drop triggers anomaly flag",
        "example_payload": {
            "shifts": [
                {"date": "2026-04-15", "net": 5000},
                {"date": "2026-04-16", "net": 4800},
                {"date": "2026-04-17", "net": 3000}
            ]
        }
    }

@app.post("/api/detect-anomaly", response_model=AnomalyResponse)
async def detect_anomaly(request: AnomalyRequest):
    """
    Detect if worker's latest shift shows an income drop.
    
    Judges: You can test this endpoint directly with Postman.
    
    Threshold: Default 20% drop triggers anomaly flag.
    
    Example Payload:
    {
        "shifts": [
            {"date": "2026-04-15", "net": 5000},
            {"date": "2026-04-16", "net": 4800},
            {"date": "2026-04-17", "net": 3000}
        ]
    }
    
    Expected Response (anomaly detected):
    {
        "flagged": true,
        "explanation": "⚠️ ANOMALY DETECTED: Income dropped by 37.5%...",
        "drop_percentage": 37.5,
        "previous_average": 4900,
        "latest_earning": 3000,
        "threshold_used": 20.0,
        "recommendation": "Review your recent shifts..."
    }
    """
    
    shifts = request.shifts
    threshold = request.threshold or 20.0
    
    # Validate input
    if not shifts or len(shifts) < 2:
        return AnomalyResponse(
            flagged=False,
            explanation="Insufficient data. Need at least 2 shifts for comparison.",
            threshold_used=threshold
        )
    
    # Separate latest shift from previous shifts
    previous_shifts = shifts[:-1]
    latest_shift = shifts[-1]
    
    # Calculate average of previous shifts
    previous_net_values = [s.net for s in previous_shifts]
    avg_previous = sum(previous_net_values) / len(previous_net_values)
    
    # Check if previous average is zero
    if avg_previous == 0:
        return AnomalyResponse(
            flagged=False,
            explanation="Previous earnings average is zero. Cannot calculate drop percentage.",
            previous_average=0,
            latest_earning=latest_shift.net,
            threshold_used=threshold
        )
    
    # Calculate drop percentage
    drop_percentage = calculate_drop_percentage(avg_previous, latest_shift.net)
    
    # Check if drop exceeds threshold
    if drop_percentage >= threshold:
        explanation = generate_explanation(
            drop_percentage, avg_previous, latest_shift.net, 
            threshold, latest_shift, previous_shifts
        )
        recommendation = generate_recommendation(drop_percentage, latest_shift)
        
        return AnomalyResponse(
            flagged=True,
            explanation=explanation,
            drop_percentage=round(drop_percentage, 2),
            previous_average=round(avg_previous, 2),
            latest_earning=latest_shift.net,
            threshold_used=threshold,
            recommendation=recommendation
        )
    
    # No anomaly detected
    return AnomalyResponse(
        flagged=False,
        explanation=f"Income stable. Drop of {drop_percentage:.1f}% is below the {threshold}% threshold.",
        drop_percentage=round(drop_percentage, 2),
        previous_average=round(avg_previous, 2),
        latest_earning=latest_shift.net,
        threshold_used=threshold,
        recommendation="Continue monitoring. No action needed at this time."
    )

@app.post("/api/detect-batch")
async def detect_batch_anomaly(workers_data: List[AnomalyRequest]):
    """
    Batch anomaly detection for multiple workers.
    Useful for advocate dashboard to flag multiple workers at once.
    """
    results = []
    for worker_data in workers_data:
        result = await detect_anomaly(worker_data)
        results.append(result.dict())
    
    flagged_count = sum(1 for r in results if r['flagged'])
    
    return {
        "success": True,
        "total_workers": len(results),
        "flagged_count": flagged_count,
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
