# certificate.py - Income Certificate Service (Port 8002)
# FIXED: Correct JWT import and error handling

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import os
import requests
from jinja2 import Template
from dotenv import load_dotenv
from jose import jwt, JWTError  # FIXED: Use python-jose, not pyjwt

load_dotenv()

app = FastAPI(title="FairGig Income Certificate Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURATION
# ==========================================
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"

# ==========================================
# JWT VERIFICATION (FIXED)
# ==========================================
def verify_token(authorization: str = Header(None)):
    """Verify JWT token and get worker info from Auth Service"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.split(" ")[1]
    
    try:
        # Decode token using python-jose
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        worker_id = payload.get("worker_id")
        
        if not worker_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Get worker details from Auth Service
        response = requests.get(
            f"{AUTH_SERVICE_URL}/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to get worker info")
        
        worker_data = response.json()
        return {
            "id": worker_id,
            "name": worker_data.get("worker", {}).get("name"),
            "email": worker_data.get("worker", {}).get("email"),
            "platform": worker_data.get("worker", {}).get("platform"),
            "token": token
        }
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_worker_earnings(worker_id: int, token: str, start_date: str = None, end_date: str = None):
    """Fetch worker's earnings from Auth Service"""
    
    url = f"{AUTH_SERVICE_URL}/api/earnings/me"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return []
        
        earnings = response.json().get("earnings", [])
        
        # Filter by date range
        if start_date:
            earnings = [e for e in earnings if e.get("date", "") >= start_date]
        if end_date:
            earnings = [e for e in earnings if e.get("date", "") <= end_date]
        
        # Filter only verified earnings
        earnings = [e for e in earnings if e.get("verified") == "approved"]
        
        return earnings
    except Exception as e:
        print(f"Error fetching earnings: {e}")
        return []

def get_city_median():
    """Get Lahore city median for comparison"""
    
    url = f"{AUTH_SERVICE_URL}/api/earnings/city-median?city=Lahore"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("median", 0)
        return 0
    except Exception:
        return 0

# ==========================================
# CERTIFICATE TEMPLATE (HTML)
# ==========================================
CERTIFICATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Income Certificate - {{ worker_name }}</title>
    <style>
        @media print {
            body {
                margin: 0;
                padding: 0;
            }
            .no-print {
                display: none;
            }
            .certificate-container {
                box-shadow: none;
                margin: 0;
                padding: 20px;
            }
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            padding: 40px;
        }
        
        .certificate-container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .certificate-header {
            background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .certificate-header h1 {
            font-size: 32px;
            margin-bottom: 10px;
        }
        
        .certificate-body {
            padding: 40px;
        }
        
        .worker-info {
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border-left: 4px solid #1a56db;
        }
        
        .worker-info h3 {
            color: #1e40af;
            margin-bottom: 15px;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 0;
        }
        
        .info-label {
            font-weight: 600;
            color: #475569;
        }
        
        .info-value {
            color: #1e293b;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .summary-card {
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .summary-card h4 {
            color: #64748b;
            font-size: 14px;
            margin-bottom: 10px;
        }
        
        .summary-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #1e40af;
        }
        
        .earnings-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }
        
        .earnings-table th,
        .earnings-table td {
            border: 1px solid #e2e8f0;
            padding: 12px;
            text-align: left;
        }
        
        .earnings-table th {
            background: #f1f5f9;
            font-weight: 600;
            color: #475569;
        }
        
        .certificate-footer {
            background: #f8fafc;
            padding: 20px 40px;
            text-align: center;
            border-top: 1px solid #e2e8f0;
            font-size: 12px;
            color: #64748b;
        }
        
        .print-button {
            background: #1a56db;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin-bottom: 20px;
            display: inline-block;
        }
        
        .print-button:hover {
            background: #1e40af;
        }
    </style>
</head>
<body>
    <div style="text-align: center;">
        <button class="print-button no-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
    </div>
    
    <div class="certificate-container">
        <div class="certificate-header">
            <h1>INCOME CERTIFICATE</h1>
            <p>Verified Earnings Statement</p>
        </div>
        
        <div class="certificate-body">
            <div class="worker-info">
                <h3>Worker Information</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Name:</span>
                        <span class="info-value">{{ worker_name }}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Email:</span>
                        <span class="info-value">{{ worker_email }}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Platform:</span>
                        <span class="info-value">{{ worker_platform }}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Certificate ID:</span>
                        <span class="info-value">{{ certificate_id }}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Issue Date:</span>
                        <span class="info-value">{{ issue_date }}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Period:</span>
                        <span class="info-value">{{ start_date }} to {{ end_date }}</span>
                    </div>
                </div>
            </div>
            
            <div class="summary-cards">
                <div class="summary-card">
                    <h4>Total Verified Earnings</h4>
                    <div class="value">PKR {{ total_earnings | round(2) | int }}</div>
                </div>
                <div class="summary-card">
                    <h4>Total Shifts</h4>
                    <div class="value">{{ total_shifts }}</div>
                </div>
                <div class="summary-card">
                    <h4>Average per Shift</h4>
                    <div class="value">PKR {{ avg_per_shift | round(2) | int }}</div>
                    <div class="sub">Lahore median: PKR {{ city_median | int }}</div>
                </div>
            </div>
            
            <h3 style="margin-bottom: 15px; color: #1e40af;">Earnings Details</h3>
            
            <table class="earnings-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Platform</th>
                        <th>Hours</th>
                        <th>Gross (PKR)</th>
                        <th>Deductions (PKR)</th>
                        <th>Net (PKR)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for earning in earnings %}
                    <tr>
                        <td>{{ earning.date }}</td>
                        <td>{{ earning.platform }}</td>
                        <td>{{ earning.hours or '-' }}</td>
                        <td>PKR {{ (earning.gross or earning.amount) | round(2) | int }}</td>
                        <td>PKR {{ (earning.deductions or 0) | round(2) | int }}</td>
                        <td><strong>PKR {{ earning.amount | round(2) | int }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="certificate-footer">
            <p>This is a computer-generated certificate and requires no signature.</p>
            <p>Generated by FairGig - Gig Worker Income & Rights Platform</p>
        </div>
    </div>
</body>
</html>
"""

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/health")
async def health():
    return {"status": "OK", "service": "Income Certificate", "port": 8002}

@app.get("/api/certificate", response_class=HTMLResponse)
async def generate_certificate(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    worker_info: dict = Depends(verify_token)
):
    """Generate printable income certificate HTML"""
    
    # Set default date range (last 90 days)
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    
    # Get worker's earnings
    earnings = get_worker_earnings(
        worker_info["id"], 
        worker_info["token"],
        start_date, 
        end_date
    )
    
    # Get city median
    city_median = get_city_median()
    
    # Calculate totals
    total_earnings = sum(e.get("amount", 0) for e in earnings)
    total_shifts = len(earnings)
    avg_per_shift = total_earnings / total_shifts if total_shifts > 0 else 0
    
    # Generate certificate ID
    certificate_id = f"FC-{datetime.now().strftime('%Y%m%d')}-{worker_info['id']:04d}"
    
    # Render HTML template
    template = Template(CERTIFICATE_TEMPLATE)
    html_content = template.render(
        worker_name=worker_info.get("name", "N/A"),
        worker_email=worker_info.get("email", "N/A"),
        worker_platform=worker_info.get("platform", "N/A"),
        certificate_id=certificate_id,
        issue_date=datetime.now().strftime("%B %d, %Y"),
        start_date=start_date,
        end_date=end_date,
        total_earnings=total_earnings,
        total_shifts=total_shifts,
        avg_per_shift=avg_per_shift,
        city_median=city_median,
        earnings=earnings
    )
    
    return HTMLResponse(content=html_content)

@app.get("/api/certificate/summary")
async def get_certificate_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    worker_info: dict = Depends(verify_token)
):
    """Get certificate summary data (JSON format)"""
    
    # Set default date range
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    
    # Get worker's earnings
    earnings = get_worker_earnings(
        worker_info["id"], 
        worker_info["token"],
        start_date, 
        end_date
    )
    
    # Get city median
    city_median = get_city_median()
    
    # Calculate totals
    total_earnings = sum(e.get("amount", 0) for e in earnings)
    total_shifts = len(earnings)
    avg_per_shift = total_earnings / total_shifts if total_shifts > 0 else 0
    
    return {
        "success": True,
        "worker": {
            "name": worker_info.get("name"),
            "email": worker_info.get("email"),
            "platform": worker_info.get("platform")
        },
        "period": {
            "start_date": start_date,
            "end_date": end_date
        },
        "summary": {
            "total_earnings": round(total_earnings, 2),
            "total_shifts": total_shifts,
            "average_per_shift": round(avg_per_shift, 2),
            "city_median": city_median,
            "comparison": "above" if avg_per_shift > city_median else "below" if total_shifts > 0 else "no_data"
        },
        "certificate_id": f"FC-{datetime.now().strftime('%Y%m%d')}-{worker_info['id']:04d}",
        "issue_date": datetime.now().strftime("%Y-%m-%d")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)