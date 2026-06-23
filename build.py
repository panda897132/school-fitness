#!/usr/bin/env python3
"""诸葛镇中心小学 体测管理系统 — PyInstaller 打包脚本"""

import os, sys, shutil, subprocess, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
APP_NAME = "小学体测管理系统"
SPEC_FILE = PROJECT_DIR / f"{APP_NAME}.spec"
UPDATER_SPEC = PROJECT_DIR / "updater.spec"
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

def build_app():
    print(f"▶ 打包主程序: {APP_NAME}")
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        return False

    exe = DIST_DIR / (f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME)
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  ✅ {exe.name} ({size_mb:.1f} MB)")
        return True
    return False

def build_updater():
    print(f"▶ 打包升级程序: updater")
    # 生成 updater.spec
    _write_updater_spec()
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(UPDATER_SPEC)]
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        return False

    exe_name = "updater.exe" if sys.platform == "win32" else "updater"
    exe = DIST_DIR / exe_name
    if exe.exists():
        size_kb = exe.stat().st_size / 1024
        print(f"  ✅ updater ({size_kb:.1f} KB)")
        return True
    return False

def _write_updater_spec():
    content = f"""# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['_updater_standalone.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'openpyxl', 'PIL', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='updater')
"""
    UPDATER_SPEC.write_text(content, encoding="utf-8")

def archive_release():
    """将主程序 + updater 打包为 release ZIP"""
    import zipfile
    zip_name = DIST_DIR / f"{APP_NAME}.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in DIST_DIR.iterdir():
            if f.suffix in ('.exe',) and f.is_file():
                zf.write(f, f.name)
    mb = zip_name.stat().st_size / (1024 * 1024)
    print(f"📦 Release ZIP: {zip_name.name} ({mb:.1f} MB)")
    return zip_name

def build():
    print("=" * 50)
    print(f"  {APP_NAME} — PyInstaller 打包")
    print(f"  平台: {sys.platform}")
    print("=" * 50)

    if not check_pyinstaller():
        return False

    ok = build_app() and build_updater()
    if ok:
        archive_release()
        print(f"\n✅ 全部打包成功 → {DIST_DIR}")
    else:
        print("\n❌ 打包失败")
    return ok

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 打包工具")
    parser.add_argument("--clean", action="store_true", help="清理旧的构建文件")
    parser.add_argument("--build", action="store_true", help="执行打包")
    args = parser.parse_args()
    if args.clean:
        clean()
    if args.build:
        build()
    if not args.clean and not args.build:
        build()
