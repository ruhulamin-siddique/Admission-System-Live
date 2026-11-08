@echo off
title BAUST Admission System - Instant Database Backup
color 0B
cd /d "%~dp0"

echo =====================================================================
echo          BAUST Admission System - Live Database Backup
echo =====================================================================
echo.

python scripts\auto_backup.py

echo.
pause

