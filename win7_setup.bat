@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ================================================
echo   School Fitness - Win7 兼容性设置工具
echo ================================================
echo.

ver | find "6.1" >nul 2>&1
if errorlevel 1 (
    echo [OK] Not Windows 7, no setup needed
    echo If DLL missing error persists, rebuild on Win10
    pause
    exit /b 0
)

echo [Windows 7 已检测到]
echo.
echo 错误 "丢失 api-ms-win-core-path-l1-1-0.dll" 是因为 Python 3.9+
echo 使用了 Windows 10 才有的 API Set DLL。
echo.
echo 本工具提供两种修复方法：
echo   1. [推荐] 使用 shim DLL（免安装、免重启）
echo   2. [官方] 安装 KB2999226（Universal C Runtime 更新）
echo.
echo ────────────────────────────────────────────
echo.

REM ─── Method 1: Shim DLL ──────────────────────────────────────────
echo [方法 1] 部署 api-ms-win-core-path-l1-1-0.dll shim
echo.
echo 检查 shim DLL 是否存在...
set SHIM_SOURCE=%~dp0hooks\api-ms-win-core-path-l1-1-0.dll
set SHIM_DEST=%~dp0api-ms-win-core-path-l1-1-0.dll

if exist "%SHIM_SOURCE%" (
    echo [OK] 发现 shim DLL (hooks\ 目录)
    copy /Y "%SHIM_SOURCE%" "%SHIM_DEST%" >nul
    if exist "%SHIM_DEST%" (
        echo [OK] shim DLL 已部署到应用目录
        echo.
        echo 现在可以直接运行 school-fitness.exe 了。
    ) else (
        echo [FAILED] 复制失败，请检查权限。
    )
    goto end
)

REM 检查是否有预编译的 shim DLL 在应用根目录
if exist "%SHIM_DEST%" (
    echo [OK] 应用目录已存在 shim DLL
    echo 可以直接运行 school-fitness.exe。
    goto end
)

echo [INFO] 未发现预编译的 shim DLL。
echo 切换到方法 2...

REM ─── Method 2: KB2999226 ─────────────────────────────────────────
:method2
echo.
echo ────────────────────────────────────────────
echo [方法 2] 安装 KB2999226 (Universal C Runtime)
echo ────────────────────────────────────────────

dism /online /get-packages 2>nul | find "KB2999226" >nul 2>&1
if not errorlevel 1 (
    echo [OK] KB2999226 (UCRT) 已安装
    echo 系统已就绪，可以直接运行 EXE。
    goto end
)

echo [NEED] KB2999226 (Universal C Runtime) 未安装
echo.
echo 下载 KB2999226 并安装:
echo.
echo   1. 打开微软下载中心
echo      www.microsoft.com /download /details.aspx?id=49010
echo.
echo   2. 下载 Windows6.1-KB2999226-x64.msu
echo.
echo   【重要】如果安装失败（错误 0x800b0001），
echo   需要先安装以下 SHA-2 更新:
echo     - KB4474419 (SHA-2 代码签名支持)
echo     - KB4490628 (服务栈更新)
echo.
echo   3. 以管理员身份运行:
echo      wusa.exe Windows6.1-KB2999226-x64.msu
echo.
echo   4. 重启计算机
echo.
echo   5. 运行 school-fitness.exe
echo.
set /p CHOICE=是否打开下载页面? (Y/N):
if /i "!CHOICE!"=="Y" (
    start https://www.microsoft.com/download/details.aspx?id=49010
)

:end
echo.
echo ================================================
echo   Setup completed.
echo ================================================
pause
endlocal
