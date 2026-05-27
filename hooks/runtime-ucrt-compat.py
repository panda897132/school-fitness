"""PyInstaller 运行时 hook — Windows UCRT API Set DLL 兼容性层

在 Python 初始化完成后、主脚本运行前执行。
确保 PyInstaller 解压目录（sys._MEIPASS）在 DLL 搜索路径中，
使打包的 API Set DLL 能被 Windows 加载器找到。

此 hook 仅作用于 Windows 且 PyInstaller 打包环境。
"""
import os
import sys
import ctypes

# ─── 仅在 Windows 和 PyInstaller 打包环境下执行 ───
if sys.platform != 'win32' or not hasattr(sys, 'frozen') or not getattr(sys, 'frozen', False):
    raise SystemExit("此 hook 仅在 Windows + PyInstaller 打包环境下运行")

# ─── 将应用程序目录加入 DLL 搜索路径 ───
# Python 3.8+ 提供了 os.add_dll_directory()，等效于 Win32 AddDllDirectory
# 让 Windows 在加载 DLL 时优先搜索我们的目录
_meipass = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
try:
    # Python 3.8+ 推荐方式
    os.add_dll_directory(_meipass)
except (AttributeError, OSError):
    # 回退：通过 ctypes 调用 SetDllDirectoryW 直接设置
    try:
        _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        _kernel32.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        _kernel32.SetDllDirectoryW(_meipass)
    except Exception:
        pass  # 静默失败 — DLL 在标准搜索路径下也能找到

# ─── 验证关键 DLL 可加载 ───
# 不能在这里用 LoadLibrary（会导致卸载问题），只做静默检查
_debug = os.environ.get('PYINSTALLER_DEBUG', '') == '1'
if _debug:
    print(f"[UCRT-HOOK] MEIPASS: {_meipass}")
    print(f"[UCRT-HOOK] add_dll_directory: OK")
