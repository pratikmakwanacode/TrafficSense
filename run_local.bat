@echo off
title Smart City Traffic System — Local Launcher
color 0A
cls

echo ============================================================
echo   SMART CITY TRAFFIC ^& EMISSION REDUCTION SYSTEM
echo   Local Development Launcher v1.0
echo ============================================================
echo.

:: ─────────────────────────────────────────────
:: 0. Resolve project root (same folder as this script)
:: ─────────────────────────────────────────────
set "ROOT=%~dp0smart_city_project"
set "BACKEND=%ROOT%\backend"
set "DASHBOARD=%ROOT%\dashboard"
set "MOBILE=%ROOT%\mobile_app"
set "EDGE=%ROOT%\edge_processor"

:: ─────────────────────────────────────────────
:: 1. PYTHON CHECK
:: ─────────────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)
python --version
echo.

:: ─────────────────────────────────────────────
:: 2. INSTALL BACKEND DEPENDENCIES
:: ─────────────────────────────────────────────
echo [2/5] Installing Backend Python dependencies...
pip install -r "%BACKEND%\requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [WARNING] Some backend packages may not have installed cleanly. Check above output.
) else (
    echo [OK] Backend dependencies ready.
)
echo.

:: ─────────────────────────────────────────────
:: 3. INSTALL EDGE PROCESSOR DEPENDENCIES
:: ─────────────────────────────────────────────
echo [3/5] Installing Edge Processor dependencies...
pip install -r "%EDGE%\requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [WARNING] Some edge packages may not have installed cleanly.
) else (
    echo [OK] Edge Processor dependencies ready.
)
echo.

:: ─────────────────────────────────────────────
:: 4. NODE / NPM CHECK
:: ─────────────────────────────────────────────
echo [4/5] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
node --version
call npm --version
echo.

:: ─────────────────────────────────────────────
:: 5. DB STATUS CHECK (MySQL probe → SQLite fallback is automatic in code)
:: ─────────────────────────────────────────────
echo [5/5] Checking MySQL availability on localhost:3306...
powershell -Command "try { $c = New-Object System.Net.Sockets.TcpClient('localhost', 3306); $c.Close(); Write-Host '[OK] MySQL is reachable on port 3306.' } catch { Write-Host '[INFO] MySQL not reachable — backend will auto-fall back to SQLite (smart_city_db.db).' }"
echo.

:: ─────────────────────────────────────────────
:: LAUNCH ALL SERVICES IN SEPARATE WINDOWS
:: ─────────────────────────────────────────────
echo ============================================================
echo   LAUNCHING ALL 4 SERVICES...
echo ============================================================
echo.

:: Ensure backend uploads dir exists
if not exist "%BACKEND%\uploads" mkdir "%BACKEND%\uploads"

:: ── SERVICE 1: FastAPI Backend (Port 8000) ──────────────────
echo [SERVICE 1] Starting FastAPI Backend on http://localhost:8000 ...
start "Smart City — FastAPI Backend :8000" /D "%BACKEND%" cmd /k "echo. && echo ======================================== && echo  FastAPI Backend  ^|  http://localhost:8000 && echo  Swagger Docs     ^|  http://localhost:8000/docs && echo ======================================== && echo. && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul

:: ── SERVICE 2: React Operator Dashboard (Port 3000) ─────────
echo [SERVICE 2] Starting React Dashboard on http://localhost:3000 ...
start "Smart City — React Dashboard :3000" /D "%DASHBOARD%" cmd /k "echo. && echo ======================================== && echo  React Dashboard  ^|  http://localhost:3000 && echo ======================================== && echo. && node node_modules\vite\bin\vite.js --host"
timeout /t 2 /nobreak >nul

:: ── SERVICE 3: Flutter Citizen Web App (Port 8080) ──────────
echo [SERVICE 3] Starting Flutter Web App on http://localhost:8080 ...
start "Smart City — Flutter Web App :8080" /D "%MOBILE%" cmd /k "echo. && echo ======================================== && echo  Flutter Citizen App  ^|  http://localhost:8080 && echo ======================================== && echo. && flutter run -d chrome --web-port=8080"
timeout /t 2 /nobreak >nul

:: ── SERVICE 4: YOLO Edge Processor ──────────────────────────
echo [SERVICE 4] Starting YOLO Edge Processor (simulation mode)...
start "Smart City — YOLO Edge Processor" /D "%EDGE%" cmd /k "echo. && echo ======================================== && echo  YOLO Edge Processor — Simulated Feed && echo  Pushing telemetry → http://localhost:8000 && echo ======================================== && echo. && python processor.py"

:: ─────────────────────────────────────────────
:: SUMMARY BANNER
:: ─────────────────────────────────────────────
echo.
echo ============================================================
echo   ALL SERVICES LAUNCHED — LOCAL ACCESS URLS
echo ============================================================
echo.
echo   Backend API + Swagger  :  http://localhost:8000/docs
echo   React Operator Dashboard:  http://localhost:3000
echo   Flutter Citizen App    :  http://localhost:8080
echo   Edge Processor Logs    :  See "YOLO Edge Processor" terminal
echo.
echo   Default Login Credentials:
echo     Username : admin
echo     Password : admin123
echo.
echo   Tips:
echo     - Wait ~10 seconds for all services to fully initialise.
echo     - Upload a .mp4 video via Dashboard to start live analysis.
echo     - YOLO edge processor auto-authenticates and begins sending
echo       telemetry frames to the backend immediately.
echo     - The DB auto-creates all tables on first backend startup.
echo       (SQLite fallback: smart_city_project\backend\smart_city_db.db)
echo.
echo ============================================================
echo   Press any key to close THIS launcher window.
echo   The 4 service windows will keep running independently.
echo ============================================================
pause >nul
