@echo off
title Stopping FairGig Services
echo ========================================
echo    Stopping All FairGig Services
echo ========================================
echo.

echo Stopping Grievance Service...
taskkill /F /FI "WINDOWTITLE eq Grievance Service*" 2>nul

echo Stopping Auth Service...
taskkill /F /FI "WINDOWTITLE eq Auth Service*" 2>nul

echo Stopping Anomaly Service...
taskkill /F /FI "WINDOWTITLE eq Anomaly Service*" 2>nul

echo Stopping Certificate Service...
taskkill /F /FI "WINDOWTITLE eq Certificate Service*" 2>nul

echo.
echo ========================================
echo    All services stopped!
echo ========================================
pause