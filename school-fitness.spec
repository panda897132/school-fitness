# -*- mode: python ; coding: utf-8 -*-
"""小学体测管理系统 — PyInstaller 打包配置

修复历史:
   2026-05-25: 修复 hiddenimports 缺失模块 + 添加 matplotlib/PIL 数据文件收集
              + 移除过于激进的 excludes(lxml 等) 避免 openpyxl 功能受限
   2026-05-27: [FIX] 解决 Windows 7 下"丢失 api-ms-win-core-path-l1-1-0.dll"问题
              → 打包 UCRT API Set DLL，支持 Windows 7/8 运行
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# ─── Windows API Set DLL 兼容性修复 ──────────────────────────────────
# Python 3.8+ 链接到 UCRT（通用 C 运行时），UCRT 依赖 Windows 10 API Set DLL
# 如 api-ms-win-core-path-l1-1-0.dll。在 Windows 7/8 上运行时会报"丢失 DLL"。
# 
# 修复方式：
#   1. 打包 API Set DLL 到 EXE（Windows 构建机上自动查找 System32/SysWOW64）
#   2. 打包 ucrtbase.dll（UCRT 实际实现）
#   3. 运行时 hook 确保应用目录在 DLL 搜索路径中
#
# 注意：32-bit Python → 查找 SysWOW64；64-bit Python → 查找 System32
# ---------------------------------------------------------------------
_WIN_API_SET_DLLS = []

if sys.platform == 'win32':
    # 根据 Python 位数选择正确的系统目录
    is_64bit = sys.maxsize > 2**32
    sys_dir = 'System32' if is_64bit else 'SysWOW64'
    system32 = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), sys_dir)
    
    # 完整 API Set DLL 列表 — 解决级联依赖
    api_set_dlls = [
        # ── Core Path（错误报告的入口 DLL） ──
        'api-ms-win-core-path-l1-1-0.dll',
        # ── 常用 API Set（级联依赖，同时打包避免连环缺失） ──
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
        # ── Security API Set ──
        'api-ms-win-security-base-l1-1-0.dll',
        'api-ms-win-security-base-l1-2-0.dll',
        # ── UCRT 实际实现 ──
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
    binaries=_WIN_API_SET_DLLS,  # 非 Windows 平台自动为 []
    datas=[
        ('icon.png', '.'),
        ('data/scoring_standards.json', 'data'),
        # 注意: 不打包 app_config.json → 它是运行时生成(含密码)的用户配置文件
    ] + collect_data_files('matplotlib')    # ← 收集 matplotlib 字体/样式/图标等数据
      + collect_data_files('PIL'),          # ← 收集 PIL 插件数据文件
    hiddenimports=[
        # --- 项目自身模块 ---
        'utils', 'config', 'login', 'main_window', 'data_manager',
        'excel_io', 'charts', 'score_engine',
        'dialogs', 'dialogs.analysis',

        # --- Tkinter 全套子模块 ---
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
        'tkinter.simpledialog', 'tkinter.messagebox',

        # --- openpyxl + numpy ---
        'openpyxl', 'numpy',

        # --- matplotlib 核心模块 ---
        'matplotlib',
        'matplotlib.figure',
        'matplotlib.pyplot',
        'matplotlib.font_manager',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backend_bases',

        # --- Pillow (matplotlib savefig/PIL.Image) ---
        'PIL', 'PIL._imaging', 'PIL.Image',

        # --- matplotlib 间接依赖（PyInstaller 常漏掉的关键链） ---
        'kiwisolver',          # matplotlib 布局引擎
        'dateutil',            # matplotlib 日期处理
        'pyparsing',           # matplotlib 文本解析
        'cycler',              # matplotlib 颜色循环
        'certifi',             # SSL 证书
        'six',                 # Python 2/3 兼容层
        'pytz',                # 时区支持
        'et_xmlfile',          # openpyxl 的 XML 引擎
    ],
    hookspath=[os.path.join(os.path.dirname(__file__), 'hooks')],
    hooksconfig={},
    runtime_hooks=[os.path.join(os.path.dirname(__file__), 'hooks', 'runtime-ucrt-compat.py')],
    excludes=[
        'numpy.random._examples',
        'scipy', 'PyQt5', 'IPython', 'jupyter',
        'setuptools', 'pkg_resources', 'test',
        # 注意: 不排除 unittest — numpy.testing 运行时可能加载
        # 不排除 lxml — openpyxl 大文件读写可能依赖
        # 不排除 cffi — 部分间接依赖可能需要
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
    name='school-fitness',
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
    version='version_info.txt',
    manifest='app.manifest',
)
