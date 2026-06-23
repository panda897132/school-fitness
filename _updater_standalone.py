"""独立升级进程 — 等待主进程退出 → 替换 EXE → 重启

编译方式: PyInstaller --onefile --noconsole _updater_standalone.py --name updater
"""

import json
import os
import subprocess
import sys
import time


def pid_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    args = json.loads(sys.argv[1])
    old_exe = args["old_exe"]
    new_exe = args["new_exe"]
    pid = args.get("pid")
    app_dir = args.get("app_dir", os.path.dirname(old_exe))

    # 等主进程退出
    if pid:
        timeout = 30
        while timeout > 0 and pid_exists(pid):
            time.sleep(0.5)
            timeout -= 0.5
    else:
        time.sleep(3)

    # 替换 EXE
    for _ in range(10):
        try:
            os.replace(new_exe, old_exe)
            break
        except PermissionError:
            time.sleep(0.5)
    else:
        sys.exit(2)

    if os.name != "nt":
        os.chmod(old_exe, 0o755)

    # 重启
    subprocess.Popen([old_exe], cwd=app_dir)


if __name__ == "__main__":
    main()
