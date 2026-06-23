@echo off
chcp 65001 >nul
title Setup - School Fitness Management System

echo.
echo   +==============================================+
echo   ^|  School Fitness Management System           ^|
echo   ^|  Zhuge Town Central Primary School           ^|
echo   ^|  One-Click Setup                             ^|
echo   +==============================================+
echo.

:: ===== Request admin privileges (Win7+ compatible) =====
net session >nul 2>&1
if not %errorlevel% equ 0 (
    echo [INFO] Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs" 2>nul
    if not %errorlevel% equ 0 (
        echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
        echo UAC.ShellExecute "%~f0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
        "%temp%\getadmin.vbs"
        del "%temp%\getadmin.vbs"
    )
    exit /b
)

:: Switch to script directory
cd /d "%~dp0"

:: ===== Step 1: Detect Python =====
echo [1/4] Checking Python environment...
set PYTHON=
set PIP=

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    set PIP=pip
    goto python_ready
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py
    set PIP=py -m pip
    goto python_ready
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python3
    set PIP=pip3
    goto python_ready
)

:: ===== Step 2: Auto-install Python =====
echo.
echo [2/4] Python not found. Attempting auto-install...
echo.

:: Detect OS architecture
set ARCH=64
set PY_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe
if not exist "%SystemRoot%\SysWOW64\cmd.exe" (
    set ARCH=32
    set PY_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9.exe
)
echo   Architecture: %ARCH%-bit
set PY_SETUP=%temp%\python-setup.exe

:: Method 1: winget (Win10 1809+)
winget install Python.Python.3.12 --silent --accept-package-agreements 2>nul
if %errorlevel% equ 0 (
    echo [OK] Installed via winget
    goto python_done
)

:: Method 2: PowerShell download
echo   Downloading via PowerShell...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_SETUP%'" 2>nul
if exist "%PY_SETUP%" goto install_python

:: Method 3: bitsadmin (Win7 compatible)
echo   Downloading via BITS...
bitsadmin /transfer "PythonDL" "%PY_URL%" "%PY_SETUP%" >nul 2>&1
if exist "%PY_SETUP%" goto install_python

:: Method 4: certutil (Win7 fallback)
echo   Downloading via certutil...
certutil -urlcache -split -f "%PY_URL%" "%PY_SETUP%" >nul 2>&1
if exist "%PY_SETUP%" goto install_python

:: All methods failed
echo.
echo [ERROR] Cannot download Python automatically. Please install manually:
echo   1. Open https://www.python.org/downloads/
echo   2. Download Python 3.10+
echo   3. IMPORTANT: Check "Add Python to PATH" during install
echo   4. Re-run this script
echo.
start "" https://www.python.org/downloads/ 2>nul
pause
exit /b 1

:install_python
echo   Installing Python (this may take 1-3 minutes)...
"%PY_SETUP%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if exist "%PY_SETUP%" del "%PY_SETUP%"
echo [OK] Python installation complete

:python_done
:: Refresh PATH (required after fresh install)
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SysPath=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "UserPath=%%b"
set "PATH=%SysPath%;%UserPath%;%PATH%"

:: Re-detect
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    set PIP=pip
) else (
    echo [WARN] Python installed but not recognized. Please restart your computer and re-run.
    pause
    exit /b 1
)

:python_ready
echo   Found: %PYTHON%
%PYTHON% --version
echo.

:: ===== Step 3: Install dependencies =====
echo [3/4] Installing project dependencies...
%PIP% install --upgrade pip -q 2>nul
%PIP% install openpyxl matplotlib numpy pillow pyinstaller -q
if not %errorlevel% equ 0 (
    echo [WARN] Retrying dependency installation...
    %PIP% install openpyxl matplotlib numpy pillow pyinstaller
)
echo [OK] Dependencies installed
echo.

:: ===== Step 4: Create shortcut and launch =====
echo [4/4] Launching School Fitness Management System...
echo.

:: Create desktop shortcut via PowerShell
set DESKTOP=%USERPROFILE%\Desktop
if not exist "%DESKTOP%" set DESKTOP=%PUBLIC%\Desktop
set LINK=%DESKTOP%\SchoolFitness.lnk
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%LINK%'); $s.TargetPath = '%PYTHON%'; $s.Arguments = '\"%~dp0main.py\"'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0icon.png,0'; $s.Description = 'School Fitness Management System'; $s.Save()" 2>nul
if exist "%LINK%" (echo [OK] Desktop shortcut created) else (echo [INFO] Shortcut creation skipped)

:: Launch the app
start "" "%PYTHON%" "%~dp0main.py"

echo.
echo +==============================================+
echo ^|  Setup complete! App is now running.          ^|
echo ^|  Use desktop shortcut for next launch.         ^|
echo +==============================================+
echo.
timeout /t 3 >nul
exit /b 0
