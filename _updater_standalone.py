"""独立升级进程 — 等待主进程退出 → 替换 EXE → 重启

编译方式: PyInstaller --onefile --noconsole _updater_standalone.py --name updater
"""

import json
import os
import subprocess
import sys
import time


def pid_exists(pid):
    """检查进程是否存活（Windows 用 ctypes 绕过 PyInstaller 的 os.kill 异常）"""
    if os.name == 'nt':
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle == 0:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    try:
        if len(sys.argv) < 2:
            return

        args = json.loads(sys.argv[1])
        old_exe = args["old_exe"]
        new_exe = args["new_exe"]
        pid = args.get("pid")
        app_dir = args.get("app_dir", os.path.dirname(old_exe))

        if pid:
            timeout = 30
            while timeout > 0 and pid_exists(pid):
                time.sleep(0.5)
                timeout -= 0.5
        else:
            time.sleep(3)

        for _ in range(10):
            try:
                os.replace(new_exe, old_exe)
                break
            except PermissionError:
                time.sleep(0.5)
        else:
            return

        if os.name != "nt":
            os.chmod(old_exe, 0o755)

        subprocess.Popen([old_exe], cwd=app_dir)
    except Exception:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
