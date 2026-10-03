@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================
echo  Pegasos Email Marketing - Install
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Download Python 3.12+ from https://www.python.org/downloads/
    echo Check "Add python to PATH" during install.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed.
    echo Download Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

echo Installing Python packages...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\pip.exe install -r requirements.txt

if not exist ".env" (
    echo.
    echo Creating .env from .env.example - EDIT THIS FILE before sending email.
    copy /Y .env.example .env
)

echo Running database migrations...
call .venv\Scripts\python.exe manage.py migrate

echo.
echo Installing frontend packages and building...
cd email-marketing-frontend
call npm ci
if errorlevel 1 (
    echo npm ci failed, trying npm install...
    call npm install
)
call npm run build
cd ..

echo.
echo ============================================
echo  Install complete.
echo  1. Edit .env with SendGrid key and settings
echo  2. Run scripts\windows\start.bat
echo ============================================
pause
