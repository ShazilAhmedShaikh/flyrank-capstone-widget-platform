@echo off
echo =======================================================
echo  Starting FlyRank Embeddable Widget Platform
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Seeding demo database (Tenants, Widgets, Leads)...
python -m app.seed
echo.

echo [2/3] Starting Customer Test Website on Port 5500 (Second Origin)...
start "Customer Website (Port 5500)" python -m http.server 5500 --directory customer_site

echo [3/3] Starting FastAPI Backend on Port 8000...
echo.
echo =======================================================
echo  Backend:      http://localhost:8000
echo  Swagger Docs: http://localhost:8000/docs
echo  Customer App: http://localhost:5500
echo =======================================================
echo.
python -m app.main
pause
