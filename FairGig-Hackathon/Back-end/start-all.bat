@echo off
title FairGig Services Launcher
echo ========================================
echo    Starting FairGig Services
echo ========================================
echo.

:: Start Node.js Grievance Service (Port 3001)
echo [1/4] Starting Grievance Service (Port 3001)...
cd /d C:\Users\OK\Desktop\Competition\FairGig-Hackathon\Back-end\fairgig-node
start "Grievance Service (3001)" cmd /k "node server.js"

timeout /t 2 /nobreak > nul

:: Start Python Auth Service (Port 8000)
echo [2/4] Starting Auth & Earnings Service (Port 8000)...
cd /d C:\Users\OK\Desktop\Competition\FairGig-Hackathon\Back-end\fairgig-python
start "Auth Service (8000)" cmd /k "venv\Scripts\activate && python main.py"

timeout /t 2 /nobreak > nul

:: Start Python Anomaly Service (Port 8001)
echo [3/4] Starting Anomaly Detection Service (Port 8001)...
cd /d C:\Users\OK\Desktop\Competition\FairGig-Hackathon\Back-end\fairgig-python
start "Anomaly Service (8001)" cmd /k "venv\Scripts\activate && python anomaly.py"

timeout /t 2 /nobreak > nul

:: Start Certificate Service (Port 8002)
echo [4/4] Starting Certificate Service (Port 8002)...
cd /d C:\Users\OK\Desktop\Competition\FairGig-Hackathon\Back-end\certificate-service
start "Certificate Service (8002)" cmd /k "venv\Scripts\activate && python certificate.py"

echo.
echo ========================================
echo    All services are starting!
echo ========================================
echo.
echo Services running on:
echo   - Grievance Service:  http://localhost:3001
echo   - Auth & Earnings:    http://localhost:8000
echo   - Anomaly Detection:  http://localhost:8001
echo   - Certificate:        http://localhost:8002
echo.
echo Close individual windows to stop each service.
echo ========================================
pause