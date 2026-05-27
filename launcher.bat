@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set EXE_NAME=小学体测管理系统.exe

if not exist "%~dp0%EXE_NAME%" (
    echo [ERROR] %EXE_NAME% not found
    echo Run build-exe.bat first
    pause
    exit /b 1
)

ver | find "6.1" >nul 2>&1
if not errorlevel 1 (
    REM Windows 7: check for api-ms-win-core-path-l1-1-0.dll shim or KB2999226
    if exist "%~dp0api-ms-win-core-path-l1-1-0.dll" (
        echo [Windows 7] api-ms-win-core-path-l1-1-0.dll shim found - OK
    ) else (
        dism /online /get-packages 2>nul | find "KB2999226" >nul 2>&1
        if errorlevel 1 (
            echo [Windows 7] 缺少 api-ms-win-core-path-l1-1-0.dll
            echo 请运行 win7_setup.bat 安装兼容补丁
            pause
            exit /b 1
        )
    )
)

start "" "%~dp0%EXE_NAME%"
endlocal
