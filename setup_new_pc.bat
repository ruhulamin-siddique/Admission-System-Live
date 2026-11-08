@echo off
title Setup BAUST Admission System on New PC
color 0B
cd /d "%~dp0"

echo =====================================================================
echo          BAUST Admission System - Initial Setup for New PC
echo =====================================================================
echo.

:: Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo.
    echo Please install Python (3.10 to 3.13):
    echo 1. Download from https://www.python.org/downloads/
    echo 2. During installation, CHECK the box: "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detected:
python --version
echo.

echo [2/3] Installing all required Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some optional packages failed to install.
    echo Attempting to install core server dependencies...
    python -m pip install django whitenoise waitress pymysql pillow openpyxl python-dotenv
)

echo.
echo [3/3] Verifying database and Django system configuration...
python manage.py check
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [ERROR] Django system check reported issues. Please check output above.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [SUCCESS] Setup completed successfully!
echo You can now double-click "run_server.bat" to start the server.
echo =====================================================================
echo.
pause

