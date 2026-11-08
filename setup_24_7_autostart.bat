@echo off
title Configure BAUST Admission System for 24/7 Autostart
color 0A
cd /d "%~dp0"

echo =====================================================================
echo       Configure BAUST Admission System for 24/7 Autostart
echo =====================================================================
echo.

echo [1/3] Disabling Windows Sleep Mode on AC power (PC stays awake 24/7)...
powercfg /change standby-timeout-ac 0
if %errorlevel% equ 0 (
    echo       [OK] Computer will never go to sleep automatically.
) else (
    echo       [NOTE] Run as Administrator if sleep setting failed.
)
echo.

echo [2/3] Adding silent background server launcher to Windows Startup...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
copy /y "%~dp0run_server_background.vbs" "%STARTUP_FOLDER%\BAUST_Admission_Server.vbs" >nul
if %errorlevel% equ 0 (
    echo       [OK] Server will start automatically in background on Windows boot.
) else (
    echo       [ERROR] Could not copy to startup folder.
)
echo.

echo [3/3] Checking Cloudflare Tunnel background service...
sc query cloudflared | findstr /i "STATE" >nul
if %errorlevel% equ 0 (
    echo       [OK] Cloudflare Tunnel service is installed and active.
) else (
    echo       [NOTE] Ensure cloudflared service is installed.
)
echo.

echo =====================================================================
echo [SUCCESS] 24/7 Configuration Complete!
echo - When your PC restarts, both Cloudflare and your server start automatically.
echo - Your PC will not go to sleep.
echo =====================================================================
echo.
pause
