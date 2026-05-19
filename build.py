#!/usr/bin/env python3
"""诸葛镇中心小学 体测管理系统 — PyInstaller 打包脚本"""

import os, sys, shutil, subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
APP_NAME = "小学体测管理系统"
SPEC_FILE = PROJECT_DIR / f"{APP_NAME}.spec"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"

def clean():
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            print(f"清理: {d}")
            shutil.rmtree(d)

def check_pyinstaller():
    try:
        result = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"],
                                capture_output=True, text=True)
        print(f"[✓] PyInstaller {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("[错误] PyInstaller 未安装 → pip install pyinstaller")
        return False

def build():
    print("=" * 50)
    print(f"  {APP_NAME} — PyInstaller 打包")
    print(f"  平台: {sys.platform}")
    print("=" * 50)

    if not check_pyinstaller():
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

    if result.returncode != 0:
        print("\n[失败] 打包出错")
        return False

    exe = DIST_DIR / (f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME)
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n✅ 打包成功: {exe} ({size_mb:.1f} MB)")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 打包工具")
    parser.add_argument("--clean", action="store_true", help="清理旧的构建文件")
    parser.add_argument("--build", action="store_true", help="执行打包")
    args = parser.parse_args()
    if args.clean or not args.build:
        clean()
    if args.build or (not args.clean and not args.build):
        build()
