"""登录界面"""

import tkinter as tk
from tkinter import messagebox
from config import LOGIN_WINDOW_SIZE, APP_TITLE, DEFAULT_USERNAME, TK_FONT
from utils import center_window


class LoginWindow:
    """登录窗口"""
    
    def __init__(self, data_manager, on_login_success):
        """
        Args:
            data_manager: DataManager 实例
            on_login_success: 登录成功回调函数
        """
        self.dm = data_manager
        self.on_login_success = on_login_success
        
        self.window = tk.Tk()
        self.window.title(APP_TITLE)
        self.window.resizable(False, False)
        
        # 窗口居中
        w, h = LOGIN_WINDOW_SIZE
        center_window(self.window, w, h)
        
        self._build_ui()
    
    def _build_ui(self):
        """构建登录界面"""
        # 主框架
        main_frame = tk.Frame(self.window, bg='#f0f4f8')
        main_frame.pack(fill='both', expand=True)
        
        # 顶部标题区
        title_frame = tk.Frame(main_frame, bg='#1a73e8', height=80)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame, 
            text=APP_TITLE,
            font=(TK_FONT, 16, 'bold'),
            fg='white', bg='#1a73e8'
        ).pack(expand=True)
        
        # 分隔线
        tk.Frame(main_frame, height=2, bg='#1565c0').pack(fill='x')
        
        # 登录表单区
        form_frame = tk.Frame(main_frame, bg='white')
        form_frame.pack(pady=30, padx=60, fill='both', expand=True)
        
        # 内表单
        inner = tk.Frame(form_frame, bg='white')
        inner.pack(expand=True)
        
        # 用户名
        tk.Label(
            inner, text='用户名:', 
            font=(TK_FONT, 11),
            fg='#555', bg='white', anchor='w'
        ).pack(fill='x', pady=(5, 2))
        
        self.username_entry = tk.Entry(
            inner, font=(TK_FONT, 11),
            relief='solid', bd=1, highlightthickness=0
        )
        self.username_entry.pack(fill='x', ipady=5)
        self.username_entry.insert(0, DEFAULT_USERNAME)
        self.username_entry.focus_set()
        
        # 密码
        tk.Label(
            inner, text='密  码:', 
            font=(TK_FONT, 11),
            fg='#555', bg='white', anchor='w'
        ).pack(fill='x', pady=(15, 2))
        
        self.password_entry = tk.Entry(
            inner, font=(TK_FONT, 11),
            show='●', relief='solid', bd=1, highlightthickness=0
        )
        self.password_entry.pack(fill='x', ipady=5)
        self.password_entry.bind('<Return>', lambda e: self._do_login())
        
        # 登录按钮
        login_btn = tk.Button(
            inner, text='登  录',
            font=(TK_FONT, 12, 'bold'),
            bg='#1a73e8', fg='white',
            activebackground='#1565c0', activeforeground='white',
            relief='flat', cursor='hand2',
            command=self._do_login,
            padx=40, pady=6
        )
        login_btn.pack(pady=(25, 10))
        
        # 版本信息
        tk.Label(
            inner, text='v1.0 — 基于《国家学生体质健康标准（2014修订版）》', 
            font=(TK_FONT, 8),
            fg='#999', bg='white'
        ).pack(pady=(10, 0))
    
    def _do_login(self):
        """执行登录"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showwarning('提示', '请输入用户名和密码')
            return
        
        if self.dm.verify_login(username, password):
            self.window.destroy()
            self.on_login_success()
        else:
            messagebox.showerror('登录失败', '用户名或密码错误！')
            self.password_entry.delete(0, 'end')
            self.password_entry.focus_set()
    
    def run(self):
        """运行登录窗口"""
        self.window.mainloop()
