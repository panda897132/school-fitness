@echo off

echo ================================================
echo   School Fitness - Build Windows EXE
echo ================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    pause
    exit /b 1
)

REM Install deps (include numpy explicitly for safety)
echo [1/3] Installing dependencies...
pip install openpyxl matplotlib numpy pillow pyinstaller -q

REM Build
echo [2/3] Building EXE (2-5 minutes)...
python -m PyInstaller --clean --noconfirm "school-fitness.spec"

REM Check result
echo [3/3] Checking result...
set EXE_NAME=school-fitness.exe
if exist "dist\%EXE_NAME%" (
    echo.
    echo ================================================
    echo   SUCCESS!
    echo   Output: dist\%EXE_NAME%
    echo   Size: 
    for %%I in ("dist\%EXE_NAME%") do echo   %%~zI bytes
    echo ================================================
    echo.
    echo   NOTE: If the EXE still reports missing modules
    echo   at runtime, check school-fitness.spec hiddenimports
    echo   and ensure all dependencies are listed.
) else (
    echo [FAILED] No EXE generated. Check error messages above.
)

pause
