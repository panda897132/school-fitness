@echo off
REM 诸葛镇中心小学 体测管理系统 — Windows 一键打包
REM 双击此文件即可生成 exe

echo ================================================
echo   小学体测管理系统 — Windows 打包
echo ================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install openpyxl matplotlib pillow pyinstaller -q

REM 打包
echo [2/3] 开始打包（约 2-5 分钟）...
python -m PyInstaller --clean --noconfirm "小学体测管理系统.spec"

REM 检查结果
echo [3/3] 检查结果...
if exist "dist\小学体测管理系统.exe" (
    for %%A in ("dist\小学体测管理系统.exe") do set size=%%~zA
    set /a mb=!size!/1024/1024
    echo.
    echo ================================================
    echo   ✅ 打包成功!
    echo   输出: dist\小学体测管理系统.exe
    echo ================================================
) else (
    echo [失败] 未生成 exe，请检查错误信息
)

pause
