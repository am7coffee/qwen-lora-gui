@echo off
title Development Quality Check
echo ========================================
echo   Code Quality Check
echo ========================================
echo.

cd /d %~dp0
call venv\Scripts\activate

echo [1/3] Running Ruff Format...
echo ----------------------------------------
venv\Scripts\ruff format apps/ core/
echo.

echo [2/3] Running Ruff Lint Check...
echo ----------------------------------------
venv\Scripts\ruff check apps/ core/ --fix
echo.

echo [3/3] Running MyPy Type Check...
echo ----------------------------------------
venv\Scripts\mypy apps/ core/ --ignore-missing-imports
echo.

echo ========================================
echo   Quality check completed!
echo ========================================
pause