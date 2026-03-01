@echo off
title Tomorrow You
setlocal

set ROOT=%~dp0
:: Strip trailing backslash
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

echo Tomorrow You -- starting...
echo.

:: Ensure storage directory exists
if not exist "%ROOT%\storage\sessions" mkdir "%ROOT%\storage\sessions"

:: Install Python deps
echo [backend]  Installing Python dependencies...
pip install -r "%ROOT%\requirements.txt" -q

:: Install frontend deps if missing
if not exist "%ROOT%\frontend\node_modules" (
    echo [frontend] node_modules not found -- running npm install...
    pushd "%ROOT%\frontend"
    call npm install
    popd
)

:: Launch backend from project root so backend.* imports resolve
echo [backend]  Starting FastAPI on http://localhost:8000
start "Tomorrow You - Backend" cmd /k "cd /d "%ROOT%" && python -m uvicorn backend.main:app --reload --port 8000"

timeout /t 1 /nobreak >nul

:: Launch frontend
echo [frontend] Starting Next.js on http://localhost:3000
start "Tomorrow You - Frontend" cmd /k "cd /d "%ROOT%\frontend" && npm run dev"

echo.
echo Both services starting in separate windows.
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo.
echo Close those windows to stop the services.
endlocal
