@echo off
chcp 65001 >nul
cd /d D:\Musubi\qwen-lora-gui
echo Running Python static analysis in D:\Musubi\qwen-lora-gui...
echo.

echo [1/4] Running Ruff linter...
python -m ruff check .
if %ERRORLEVEL% neq 0 (
    echo Ruff found issues!
) else (
    echo Ruff check passed!
)
echo.

echo [2/4] Running Ruff format check...
python -m ruff format --check .
if %ERRORLEVEL% neq 0 (
    echo Format issues found!
) else (
    echo Format check passed!
)
echo.

echo [3/4] Running MyPy type check...
python -m mypy .
if %ERRORLEVEL% neq 0 (
    echo MyPy found type issues!
) else (
    echo MyPy check passed!
)
echo.

echo [4/4] Running Bandit security check...
python -m bandit -r .
if %ERRORLEVEL% neq 0 (
    echo Bandit found security issues!
) else (
    echo Bandit check passed!
)
echo.

echo Static analysis completed.
pause
