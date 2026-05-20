"""通用工具函数"""

def center_window(window, width, height):
    """窗口居中"""
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    window.geometry(f'{width}x{height}+{x}+{y}')
