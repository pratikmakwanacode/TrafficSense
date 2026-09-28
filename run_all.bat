@echo off
title Smart City System — Unified Launcher
color 0A
cls

echo ============================================================
echo   SMART CITY TRAFFIC ^& EMISSION REDUCTION SYSTEM
echo   Unified Local Launcher
echo ============================================================
echo.

set "ROOT=%~dp0smart_city_project"
set "BACKEND=%ROOT%\backend"
set "DASHBOARD=%ROOT%\dashboard"
set "EDGE=%ROOT%\edge_processor"

:: Ensure backend uploads dir exists
if not exist "%BACKEND%\uploads" mkdir "%BACKEND%\uploads"

:: ── SERVICE 1: FastAPI Backend (Port 8000) ──────────────────
echo [SERVICE 1] Starting FastAPI Backend on http://localhost:8000 ...
start "Smart City — FastAPI Backend :8000" /D "%BACKEND%" cmd /k "echo. && echo ======================================== && echo  FastAPI Backend  ^|  http://localhost:8000 && echo  Swagger Docs     ^|  http://localhost:8000/docs && echo ======================================== && echo. && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul

:: ── SERVICE 2: React Operator Dashboard (Port 3000) ─────────
echo [SERVICE 2] Starting React Dashboard on http://localhost:3000 ...
start "Smart City — React Dashboard :3000" /D "%DASHBOARD%" cmd /k "echo. && echo ======================================== && echo  React Dashboard  ^|  http://localhost:3000 && echo ======================================== && echo. && node node_modules\vite\bin\vite.js --port 3000 --host"
timeout /t 2 /nobreak >nul

:: ── SERVICE 3: YOLO Edge Processor ──────────────────────────
echo [SERVICE 3] Starting YOLO Edge Processor (simulation mode)...
start "Smart City — YOLO Edge Processor" /D "%EDGE%" cmd /k "echo. && echo ======================================== && echo  YOLO Edge Processor — Live Frame Stream && echo  Pushing telemetry → http://localhost:8000 && echo ======================================== && echo. && python processor.py"

echo.
echo ============================================================
echo   ALL SERVICES LAUNCHED — LOCAL ACCESS URLS
echo ============================================================
echo.
echo   Backend API + Swagger  :  http://localhost:8000/docs
echo   React Operator Dashboard:  http://localhost:3000
echo   Unified Server View    :  http://localhost:8000
echo   Mock Citizen App       :  http://localhost:8000/app
echo.
echo   Default Login Credentials:
echo     Username : admin
echo     Password : admin123
echo.
echo ============================================================
pause
