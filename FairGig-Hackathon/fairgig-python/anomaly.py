# anomaly.py - Anomaly Detection Service (Port 8001)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="FairGig Anomaly Detection Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Shift(BaseModel):
    date: str
    net: float
    gross: Optional[float] = None
    deductions: Optional[float] = None
    hours: Optional[float] = None

class AnomalyRequest(BaseModel):
    shifts: List[Shift]
    worker_id: Optional[int] = None

@app.get("/api/health")
async def health():
    return {"status": "OK", "service": "Anomaly Detection", "port": 8001}

@app.post("/api/detect-anomaly")
async def detect_anomaly(request: AnomalyRequest):
    shifts = request.shifts
    
    if len(shifts) < 2:
        return {
            "flagged": False,
            "explanation": "Need at least 2 shifts for comparison"
        }
    
    previous_shifts = shifts[:-1]
    latest_shift = shifts[-1]
    
    avg_previous = sum(s.net for s in previous_shifts) / len(previous_shifts)
    
    if avg_previous == 0:
        return {
            "flagged": False,
            "explanation": "Previous earnings average is zero"
        }
    
    drop_percentage = ((avg_previous - latest_shift.net) / avg_previous) * 100
    
    if drop_percentage >= 20:
        explanation = f"Statistically unusual income drop of {drop_percentage:.1f}%. "
        
        if latest_shift.deductions and previous_shifts[-1].deductions:
            deduction_change = latest_shift.deductions - previous_shifts[-1].deductions
            if deduction_change > 0:
                explanation += f"Platform deductions increased by ₹{deduction_change:.2f}."
        
        return {
            "flagged": True,
            "explanation": explanation,
            "drop_percentage": round(drop_percentage, 2),
            "previous_average": round(avg_previous, 2),
            "latest_earning": latest_shift.net
        }
    
    return {
        "flagged": False,
        "explanation": f"Income stable. Drop of {drop_percentage:.1f}% below 20% threshold.",
        "drop_percentage": round(drop_percentage, 2),
        "previous_average": round(avg_previous, 2),
        "latest_earning": latest_shift.net
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)