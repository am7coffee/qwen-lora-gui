@echo off
echo ========================================
echo Queue System Launch Debug
echo ========================================
echo Current Directory: %CD%
echo Python Executable: D:\Musubi\qwen-lora-gui\venv\Scripts\python.exe
echo Launch Script: D:\Musubi\qwen-lora-gui\apps\launch_queue.py
echo Port: 7862
echo Project Root: D:\Musubi\qwen-lora-gui\apps
echo ========================================
echo.
echo Starting Queue System...
echo.
"D:\Musubi\qwen-lora-gui\venv\Scripts\python.exe" "D:\Musubi\qwen-lora-gui\apps\launch_queue.py" --port 7862
echo.
echo ========================================
echo Process finished with exit code: %ERRORLEVEL%
echo Press any key to close this window...
echo ========================================
pause
