"""独立升级进程 — 等待主进程退出 → 替换 EXE → 重启

编译方式: PyInstaller --onefile --noconsole _updater_standalone.py --name updater
"""

import json
import os
import subprocess
import sys
import time


def main():
    try:
        if len(sys.argv) < 2:
            return

        args = json.loads(sys.argv[1])
        old_exe = args["old_exe"]
        new_exe = args["new_exe"]
        app_dir = args.get("app_dir", os.path.dirname(old_exe))

        # 不检查 PID 是否存在——PyInstaller 中 os.kill/ctypes 都可能触发
        # C 层异常导致崩溃。固定等待主进程退出足够安全。
        time.sleep(6)

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
        # 静默退出——不弹"Unhandled exception"对话框。升级失败后
        # 用户重启旧版可重试检查更新
        pass


if __name__ == "__main__":
    main()
