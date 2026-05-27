@echo off
chcp 65001 >nul
title Build api-ms-win-core-path-l1-1-0.dll Shim

echo ================================================
echo   Build api-ms-win-core-path-l1-1-0.dll Shim
echo   For Windows 7 Compatibility
echo ================================================
echo.

REM Check for MSVC compiler (cl.exe)
cl --version >nul 2>&1
if not errorlevel 1 goto msvc_build

REM Check for MinGW-w64
where gcc 2>nul | findstr mingw >nul 2>&1
if not errorlevel 1 goto mingw_build

echo [ERROR] No supported compiler found.
echo.
echo Option 1: Install MinGW-w64 from:
echo   https://www.mingw-w64.org/downloads/
echo.
echo Option 2: Use Visual Studio Build Tools:
echo   https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
echo.
pause
exit /b 1

:msvc_build
echo [BUILD] Using MSVC compiler...
cl /nologo /O2 /LD /Feapi-ms-win-core-path-l1-1-0.dll ^
    api-ms-win-core-path-blender.c dllmain.cpp ^
    /link /DEF:api-ms-win-core-path-blender.def shlwapi.lib
if %errorlevel% equ 0 (
    echo [OK] DLL built successfully!
    dir api-ms-win-core-path-l1-1-0.dll
) else (
    echo [FAILED] Build failed.
    pause
    exit /b 1
)
goto end

:mingw_build
echo [BUILD] Using MinGW-w64 compiler...
gcc -O2 -shared -o api-ms-win-core-path-l1-1-0.dll ^
    api-ms-win-core-path-blender.c dllmain.cpp ^
    -lshlwapi api-ms-win-core-path-blender.def -s
if %errorlevel% equ 0 (
    echo [OK] DLL built successfully!
    dir api-ms-win-core-path-l1-1-0.dll
) else (
    echo [FAILED] Build failed.
    pause
    exit /b 1
)
goto end

:end
echo.
echo DLL placed at: %CD%\api-ms-win-core-path-l1-1-0.dll
echo Copy this DLL to the hooks/ directory before building the EXE.
pause
