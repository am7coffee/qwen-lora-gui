@echo off
title QWEN LoRA GUI
echo ========================================
echo   QWEN LoRA GUI - Starting...
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate

echo Starting GUI at http://127.0.0.1:7860
echo Recommended: Use dark mode - http://127.0.0.1:7860/?__theme=dark
echo.
python launch_gui.py

echo.
echo GUI has been closed.
pause