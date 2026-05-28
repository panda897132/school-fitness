"""入口程序 — 诸葛镇中心小学学生体质健康管理系统"""

import sys
import os
import traceback
import logging
import tkinter.messagebox as msgbox

# ─── 路径解析（PyInstaller 冻结模式 vs 源码模式） ─────────────────────
# PyInstaller 冻结 EXE 中 __file__ 指向临时提取目录（_MEIxxxxx），
# 该目录在 EXE 退出时会被删除。必须使用 sys.executable 获取 EXE 真实路径，
# 否则导入的学生数据会在重启后丢失。
if getattr(sys, 'frozen', False):
    _app_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))

# ─── 运行时数据根目录（处理 Program Files 等只读安装路径） ──────
# 如果 EXE 所在目录不可写，运行时数据（students.json、app_config.json、
# audit.log、error.log）回退到用户数据目录，避免 PermissionError 崩溃。
if os.access(_app_dir, os.W_OK):
    DATA_ROOT = _app_dir
else:
    DATA_ROOT = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'SchoolFitness',
    )

# 错误日志路径（记录完整 traceback，不向用户展示）
ERROR_LOG = os.path.join(DATA_ROOT, 'data', 'error.log')

# 将根日志记录器连接到 ERROR_LOG，确保所有 logging.exception() 写入文件
# （在 console=False EXE 中 stderr 被抑制，不连接则崩溃跟踪静默丢失）
os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# 确保在正确的目录运行（Python 路径和 CWD 始终用 EXE 目录）
BASE_DIR = _app_dir
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def main():
    """应用程序入口"""
    try:
        from login import LoginWindow
        from main_window import MainWindow
        from data_manager import DataManager
        
        # 初始化数据管理器（使用 DATA_ROOT 确保写入可写目录）
        dm = DataManager(DATA_ROOT)
        
        def on_login_success():
            """登录成功后打开主窗口"""
            try:
                main_win = MainWindow(dm)
                main_win.run()
            except Exception:
                logging.exception('启动主窗口失败', exc_info=True)
                msgbox.showerror('错误', '程序启动失败，请查看错误日志。')
                raise
        
        # 启动登录窗口
        login_win = LoginWindow(dm, on_login_success)
        login_win.run()
    
    except ImportError as e:
        msg = (
            f"缺少依赖库: {e}\n\n"
            "请先安装依赖:\n"
            "  pip install openpyxl matplotlib pillow"
        )
        try:
            msgbox.showerror('依赖缺失', msg)
        except Exception:
            print(msg, file=sys.stderr)
        sys.exit(1)
    
    except Exception:
        logging.exception('程序启动失败', exc_info=True)
        try:
            msgbox.showerror('启动失败', '程序启动失败，请查看错误日志。')
        except Exception:
            print('启动失败: 无法显示错误对话框', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
