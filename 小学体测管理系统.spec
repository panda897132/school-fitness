# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon.png', '.'),
        ('data/', 'data/'),
    ],
    hiddenimports=['tkinter', 'matplotlib.backends.backend_tkagg', 'openpyxl', 'numpy', 'utils'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
