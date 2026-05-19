#!/usr/bin/env python3
"""诸葛镇中心小学 — 学生体质健康管理系统 启动器"""
import subprocess, sys, os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
subprocess.run([sys.executable, "main.py"])
