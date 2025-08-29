@echo off
title Queue System
echo ========================================
echo   Queue System - Starting...
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate

echo Starting Queue System at http://127.0.0.1:7861
echo Recommended: Use dark mode - http://127.0.0.1:7861/?__theme=dark
echo.
python launch_queue.py

echo.
echo Queue System has been closed.
pause