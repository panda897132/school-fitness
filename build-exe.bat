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
echo [1/4] Installing dependencies...
pip install openpyxl matplotlib numpy pillow pyinstaller -q

REM Check / Build Win7 shim DLL
echo [2/4] Checking Win7 shim DLL...
if not exist "hooks\api-ms-win-core-path-l1-1-0.dll" (
    echo [INFO] Building api-ms-win-core-path-l1-1-0.dll shim...
    call hooks\build-shim.bat
    if exist "api-ms-win-core-path-l1-1-0.dll" (
        move /Y "api-ms-win-core-path-l1-1-0.dll" "hooks\" >nul
    )
)
if exist "hooks\api-ms-win-core-path-l1-1-0.dll" (
    echo [OK] Win7 shim DLL found: hooks\api-ms-win-core-path-l1-1-0.dll
) else (
    echo [WARN] Win7 shim DLL not found. Windows 7 users will need KB2999226.
)

REM Build
echo [3/4] Building EXE (2-5 minutes)...
python -m PyInstaller --clean --noconfirm "school-fitness.spec"

REM Check result
echo [4/4] Checking result...
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
    echo   Win7 compatibility: shim DLL is bundled inside the EXE.
    echo   No additional files needed on Windows 10.
    echo   On Windows 7, the EXE will work automatically.
) else (
    echo [FAILED] No EXE generated. Check error messages above.
)

pause
