@echo off
cd /d "%~dp0"

:: Detect Python
set PYTHON=
python  --version >nul 2>&1 && set PYTHON=python
if not defined PYTHON py --version >nul 2>&1 && set PYTHON=py
if not defined PYTHON python3 --version >nul 2>&1 && set PYTHON=python3

if not defined PYTHON (
    echo [ERROR] Python not found. Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting School Fitness Management System...
start "" "%PYTHON%" "%~dp0main.py"
