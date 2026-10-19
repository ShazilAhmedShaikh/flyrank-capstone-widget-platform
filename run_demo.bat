@echo off
title FlyRank Platform Launcher
echo =======================================================
echo   Starting FlyRank Embeddable Widget Platform
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Ensuring clean ports...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5500 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo [2/3] Seeding demo database (Tenants, Widgets, Leads)...
python -m app.seed
echo.

echo [3/3] Starting Customer Test Website on Port 5500 (Second Origin)...
start "Customer Website (Port 5500)" /D "%~dp0" python -m http.server 5500 --directory customer_site

echo.
echo =======================================================
echo   SYSTEM IS READY!
echo.
echo   Owner Dashboard:   http://localhost:8000
echo   Customer Website:  http://localhost:5500 (or http://localhost:8000/demo)
echo   Swagger API Docs:  http://localhost:8000/docs
echo =======================================================
echo.
python -m app.main
pause
