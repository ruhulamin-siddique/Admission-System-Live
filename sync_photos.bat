@echo off
title BAUST Student Photo Synchronizer
color 0B
cd /d "%~dp0"

echo =====================================================================
echo               BAUST Student Photo Synchronizer
echo =====================================================================
echo.
echo This tool automatically deploys photos from the 'photos\' folder
echo to 'media\student_photos\' and updates database student records.
echo.

python scripts\sync_student_photos.py --execute

echo.
pause

