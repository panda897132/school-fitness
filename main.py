"""入口程序 — 诸葛镇中心小学学生体质健康管理系统"""

import sys
import os
import traceback
import logging
import tkinter.messagebox as msgbox

# 错误日志路径（记录完整 traceback，不向用户展示）
ERROR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'error.log')

# 确保在正确的目录运行
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)


def main():
    """应用程序入口"""
    try:
        from login import LoginWindow
        from main_window import MainWindow
        from data_manager import DataManager
        
        # 初始化数据管理器
        dm = DataManager(BASE_DIR)
        
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
