@echo off
title BAUST Admission System Server
color 0A
cd /d "%~dp0"

echo =====================================================================
echo                BAUST Admission System Server
echo =====================================================================
echo.

:: Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not found on this computer!
    echo Please install Python 3.10+ and make sure to check:
    echo "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Find current LAN IP address using PowerShell
for /f "delims=" %%I in ('powershell -Command "try { (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Ethernet*','Wi-Fi*' -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress } catch { '127.0.0.1' }"') do set "LAN_IP=%%I"
if "%LAN_IP%"=="" set "LAN_IP=localhost"

echo Starting server...
echo ---------------------------------------------------------------------
echo   Local PC Access:   http://localhost:8000
echo   LAN Office Access: http://%LAN_IP%:8000
echo ---------------------------------------------------------------------
echo.
echo Press Ctrl + C to stop the server at any time.
echo.

:: Try starting with Waitress (multi-threaded, recommended for LAN & Cloudflare)
python -m waitress --listen=0.0.0.0:8000 --threads=8 admission_system.wsgi:application
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Falling back to standard Django runserver...
    python manage.py runserver 0.0.0.0:8000
)

pause

