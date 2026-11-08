@echo off
title Cloudflare Live Tunnel - BAUST Admission System
color 0B
cd /d "%~dp0"

echo =====================================================================
echo           BAUST Admission System - Cloudflare Live Tunnel
echo =====================================================================
echo.
echo Make sure your server is running on port 8000 (via run_server.bat).
echo.
echo Select an option:
echo   [1] Instant Quick Tunnel (*.trycloudflare.com)
echo       - Free, instant public HTTPS URL, no account or domain needed!
echo.
echo   [2] Connect Custom Domain (e.g. portal.baust.edu.bd)
echo       - Uses your Cloudflare Tunnel Token from Zero Trust Dashboard.
echo.
set /p choice="Enter choice [1 or 2]: "

if "%choice%"=="1" (
    echo.
    echo Starting Cloudflare Quick Tunnel...
    echo Look for the public https://*.trycloudflare.com link below:
    echo -----------------------------------------------------------------
    C:\cloudflared\cloudflared.exe tunnel --url http://localhost:8000
) else if "%choice%"=="2" (
    echo.
    echo Copy the command or token from Step 4 in Cloudflare:
    set /p USER_INPUT="Paste here (command or token): "
    echo.
    echo Starting tunnel...
    powershell -Command "$input = '%USER_INPUT%'.Trim(); if ($input -match '([A-Za-z0-9_\-]{50,})') { $token = $matches[1]; & 'C:\cloudflared\cloudflared.exe' tunnel run --token $token } else { & 'C:\cloudflared\cloudflared.exe' tunnel run --token $input }"
) else (
    echo Invalid choice.
)

pause

