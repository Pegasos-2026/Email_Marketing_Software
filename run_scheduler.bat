@echo off
REM Windows batch file to run the campaign scheduler
REM Usage: run_scheduler.bat [check_interval_minutes]

setlocal enabledelayedexpansion

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Get check interval from command line or use default
set CHECK_INTERVAL=%1
if "!CHECK_INTERVAL!"=="" set CHECK_INTERVAL=5

echo.
echo ========================================
echo Campaign Scheduler
echo ========================================
echo Checking for scheduled campaigns every !CHECK_INTERVAL! minute(s)
echo Press Ctrl+C to stop
echo.

REM Run the scheduler
python run_scheduler.py !CHECK_INTERVAL!

pause
