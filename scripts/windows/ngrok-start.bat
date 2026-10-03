@echo off
setlocal
cd /d "%~dp0..\.."

where ngrok >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok is not installed.
    echo 1. Sign up at https://ngrok.com
    echo 2. Download ngrok for Windows
    echo 3. Run: ngrok config add-authtoken YOUR_TOKEN
    pause
    exit /b 1
)

echo Make sure backend and frontend are already running (start.bat).
echo.
echo This opens TWO ngrok tunnels:
echo   - port 8000 (API)
echo   - port 3000 (UI - share this URL with your tester)
echo.
echo After ngrok starts, copy the https URL for port 3000 and send it to your tester.
echo.
pause

start "ngrok API" cmd /k ngrok http 8000
timeout /t 2 /nobreak >nul
start "ngrok UI" cmd /k ngrok http 3000
