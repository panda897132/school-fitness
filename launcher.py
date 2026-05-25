#!/usr/bin/env python3
"""诸葛镇中心小学 — 学生体质健康管理系统 启动器"""
import subprocess, sys, os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

try:
    result = subprocess.run(
        [sys.executable, "main.py"],
        timeout=300,  # 5分钟超时，防止GUI卡死时启动器无限等待
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"[启动器] main.py 异常退出，返回码: {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
except subprocess.TimeoutExpired:
    print("[启动器] main.py 运行超时（5分钟），已强制终止", file=sys.stderr)
    sys.exit(1)
except FileNotFoundError:
    print("[启动器] 未找到 Python 解释器或 main.py", file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    print("[启动器] 用户中断", file=sys.stderr)
    sys.exit(0)
