@echo off
setlocal
cd /d "%~dp0..\.."

if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env file missing. Run install.bat or copy .env.example to .env
    pause
    exit /b 1
)

echo Starting Pegasos Email Marketing...
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Keep both windows open while testing. Close them to stop the app.
echo.

start "Pegasos Backend" cmd /k "cd /d %CD% && .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak >nul
start "Pegasos Frontend" cmd /k "cd /d %CD%\email-marketing-frontend && set NODE_OPTIONS=--openssl-legacy-provider && npm start"
timeout /t 8 /nobreak >nul
start http://localhost:3000

echo Browser opened. If login fails, wait a few seconds for servers to finish starting.
