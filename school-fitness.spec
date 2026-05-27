# -*- mode: python ; coding: utf-8 -*-
"""小学体测管理系统 — PyInstaller 打包配置

修复历史:
    2026-05-25: 修复 hiddenimports 缺失模块 + 添加 matplotlib/PIL 数据文件收集
               + 移除过于激进的 excludes(lxml 等) 避免 openpyxl 功能受限
    2026-05-27: [FIX] 解决 Windows 7 下"丢失 api-ms-win-core-path-l1-1-0.dll"问题
               → 打包 UCRT API Set DLL，支持 Windows 7/8 运行
    2026-05-28: [FIX] 彻底解决 Windows 7 兼容性
               → 使用自定义 api-ms-win-core-path-l1-1-0.dll shim
               → 移除从 System32 复制 API Set DLL 的不可靠方式
               → 该 shim 基于 Wine 项目代码实现，转发 PathCch* 调用到 shlwapi.dll
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

# ─── Windows 7 API Set Shim DLL ─────────────────────────────────────
# Python 3.9+ 静态链接到 api-ms-win-core-path-l1-1-0.dll（Windows 10 API Set）
# Windows 7 不存在此 DLL，导致 EXE 启动时报"丢失 api-ms-win-core-path-l1-1-0.dll"
#
# 修复方式：
#   使用自定义 shim DLL，将 PathCch* 函数调用转发到 Windows 7 已有的 shlwapi.dll
#   （shlwapi.dll 在 Windows 7 上原生包含 Path* 系列函数）
#
# 源码位置：hooks/api-ms-win-core-path-blender.c (基于 Wine/LGPL 2.1)
# 编译方式：hooks/build-shim.sh 或 hooks/build-shim.bat
# ---------------------------------------------------------------------
_WIN_API_SET_SHIM = []

# 从 hooks/ 目录加载预编译的 shim DLL
_shim_path = os.path.join(os.getcwd(), 'hooks', 'api-ms-win-core-path-l1-1-0.dll')
if os.path.exists(_shim_path):
    _WIN_API_SET_SHIM.append((_shim_path, '.'))
    print(f"   [WIN7] ✅ 已加载 api-ms-win-core-path-l1-1-0.dll shim ({os.path.getsize(_shim_path)} bytes)")
else:
    print(f"   [WIN7] ⚠️ 未找到 shim DLL（hooks/api-ms-win-core-path-l1-1-0.dll）")
    print(f"   [WIN7]    Windows 7 用户将需要安装 KB2999226 (UCRT) 或手动部署 shim DLL")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_WIN_API_SET_SHIM,  # 自定义 shim DLL（非 Windows 平台自动为 []）
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
    hookspath=[os.path.join(os.getcwd(), 'hooks')],
    hooksconfig={},
    runtime_hooks=[os.path.join(os.getcwd(), 'hooks', 'runtime-ucrt-compat.py')],
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
