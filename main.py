"""入口程序 — 诸葛镇中心小学学生体质健康管理系统"""

import sys
import os
import traceback

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
            except Exception as e:
                import tkinter.messagebox as msgbox
                msgbox.showerror('错误', f'启动主窗口失败:\n{traceback.format_exc()}')
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
            import tkinter.messagebox as msgbox
            msgbox.showerror('依赖缺失', msg)
        except Exception:
            print(msg, file=sys.stderr)
        sys.exit(1)
    
    except Exception as e:
        try:
            import tkinter.messagebox as msgbox
            msgbox.showerror('启动失败', f'程序启动失败:\n{traceback.format_exc()}')
        except Exception:
            print(f'启动失败: {traceback.format_exc()}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
