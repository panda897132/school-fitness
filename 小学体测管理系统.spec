# -*- mode: python ; coding: utf-8 -*-
"""小学体测管理系统 — PyInstaller 打包配置（备用 spec）

修复历史:
   2026-05-27: [FIX] 解决 Windows 7 下"丢失 api-ms-win-core-path-l1-1-0.dll"问题
              → 打包 UCRT API Set DLL + 运行时 hook，支持 Windows 7/8 运行
"""

import os
import sys

# ─── Windows API Set DLL 兼容性修复 ──────────────────────────────────
# 参见 school-fitness.spec 中的详细说明
# ---------------------------------------------------------------------
_WIN_API_SET_DLLS = []

if sys.platform == 'win32':
    is_64bit = sys.maxsize > 2**32
    sys_dir = 'System32' if is_64bit else 'SysWOW64'
    system32 = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), sys_dir)

    api_set_dlls = [
        'api-ms-win-core-path-l1-1-0.dll',
        'api-ms-win-core-path-l1-1-1.dll',
        'api-ms-win-core-processthreads-l1-1-2.dll',
        'api-ms-win-core-file-l1-2-1.dll',
        'api-ms-win-core-file-l1-2-2.dll',
        'api-ms-win-core-file-l2-1-1.dll',
        'api-ms-win-core-localization-l1-2-1.dll',
        'api-ms-win-core-synch-l1-2-1.dll',
        'api-ms-win-core-timezone-l1-1-0.dll',
        'api-ms-win-core-errorhandling-l1-1-1.dll',
        'api-ms-win-core-heap-l1-2-0.dll',
        'api-ms-win-core-string-l1-1-0.dll',
        'api-ms-win-core-libraryloader-l1-2-1.dll',
        'api-ms-win-core-shlwapi-l1-1-1.dll',
        'api-ms-win-core-registry-l1-1-0.dll',
        'api-ms-win-core-console-l1-1-0.dll',
        'api-ms-win-core-interlocked-l1-1-0.dll',
        'api-ms-win-core-profile-l1-1-0.dll',
        'api-ms-win-core-rtlsupport-l1-1-0.dll',
        'api-ms-win-core-debug-l1-1-1.dll',
        'api-ms-win-core-io-l1-1-1.dll',
        'api-ms-win-core-namedpipe-l1-1-0.dll',
        'api-ms-win-core-memory-l1-1-1.dll',
        'api-ms-win-core-memory-l1-1-2.dll',
        'api-ms-win-core-datetime-l1-1-1.dll',
        'api-ms-win-core-util-l1-1-0.dll',
        'api-ms-win-core-handle-l1-1-0.dll',
        'api-ms-win-core-threadpool-l1-2-0.dll',
        'api-ms-win-core-fibers-l1-1-0.dll',
        'api-ms-win-security-base-l1-1-0.dll',
        'api-ms-win-security-base-l1-2-0.dll',
        'ucrtbase.dll',
    ]
    for dll_name in api_set_dlls:
        dll_path = os.path.join(system32, dll_name)
        if os.path.exists(dll_path):
            _WIN_API_SET_DLLS.append((dll_path, '.'))
            print(f"   [UCRT] ✅ 已找到 {dll_name}，将打包到 EXE")
        else:
            print(f"   [UCRT] ⚪ 未找到 {dll_name}（跳过 — 非必要）")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_WIN_API_SET_DLLS,
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
