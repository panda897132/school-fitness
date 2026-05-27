# -*- mode: python ; coding: utf-8 -*-
"""小学体测管理系统 — PyInstaller 打包配置（备用 spec）

修复历史:
    2026-05-27: [FIX] 解决 Windows 7 下"丢失 api-ms-win-core-path-l1-1-0.dll"问题
               → 打包 UCRT API Set DLL + 运行时 hook，支持 Windows 7/8 运行
    2026-05-28: [FIX] 使用自定义 shim DLL 替代从 System32 复制 API Set DLL
               → 彻底解决 Windows 7 兼容性（不再依赖构建机系统版本）
"""

import os
import sys

# ─── Windows 7 API Set Shim DLL ─────────────────────────────────────
# Python 3.9+ 静态链接到 api-ms-win-core-path-l1-1-0.dll（Windows 10 API Set）
# Windows 7 不存在此 DLL，导致 EXE 启动时报"丢失 api-ms-win-core-path-l1-1-0.dll"
#
# 修复方式：使用自定义 shim DLL，将 PathCch* 函数调用转发到 Windows 7 已有的 shlwapi.dll
# 源码位置：hooks/api-ms-win-core-path-blender.c（基于 Wine/LGPL 2.1）
# ---------------------------------------------------------------------
_WIN_API_SET_SHIM = []

_shim_path = os.path.join(os.path.dirname(__file__), 'hooks', 'api-ms-win-core-path-l1-1-0.dll')
if os.path.exists(_shim_path):
    _WIN_API_SET_SHIM.append((_shim_path, '.'))
    print(f"   [WIN7] ✅ 已加载 api-ms-win-core-path-l1-1-0.dll shim ({os.path.getsize(_shim_path)} bytes)")
else:
    print(f"   [WIN7] ⚠️ 未找到 shim DLL（hooks/api-ms-win-core-path-l1-1-0.dll）")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_WIN_API_SET_SHIM,
    datas=[
        ('icon.png', '.'),
        ('data/', 'data/'),
    ],
    hiddenimports=['tkinter', 'matplotlib.backends.backend_tkagg', 'openpyxl', 'numpy', 'utils'],
    hookspath=[os.path.join(os.getcwd(), 'hooks')],
    hooksconfig={},
    runtime_hooks=[os.path.join(os.getcwd(), 'hooks', 'runtime-ucrt-compat.py')],
    excludes=[
        'numpy.random._examples',
        'scipy',
        'PyQt5',
        'IPython',
        'jupyter',
        'setuptools',
        'pkg_resources',
        'test',
        'unittest',
    ],
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
    name='小学体测管理系统',
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
    icon='icon.png',
    version='version_info.txt',
    manifest='app.manifest',
)
