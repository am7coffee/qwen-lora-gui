@echo off
title QWEN LoRA - Launcher
echo ========================================
echo   QWEN LoRA GUI ^& Queue System
echo   Integrated Launcher
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate

echo [1/2] Starting QWEN LoRA GUI...
start "QWEN LoRA GUI" cmd /k python launch_gui.py

:: Wait for GUI to initialize
timeout /t 3 /nobreak > nul

echo [2/2] Starting Queue System...
start "Queue System" cmd /k python launch_queue.py

echo.
echo ========================================
echo   Both systems are now running!
echo ========================================
echo.
echo   GUI:   http://127.0.0.1:7860/?__theme=dark
echo   Queue: http://127.0.0.1:7861/?__theme=dark
echo.
echo ========================================
echo Press any key to close this launcher...
echo (The systems will continue running)
pause > nul