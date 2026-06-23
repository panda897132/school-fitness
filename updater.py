"""在线升级模块 — 通过 GitHub Releases 检查/下载更新"""

import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from config import APP_VERSION, APP_REPO, TK_FONT, FONT_BOLD_11

UPDATE_URL = f"https://api.github.com/repos/{APP_REPO}/releases/latest"
RELEASE_URL = f"https://github.com/{APP_REPO}/releases/latest"


def _parse_version(v):
    """'v1.2.3' → (1,2,3)"""
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)', str(v))
    if m:
        return tuple(map(int, m.groups()))
    return (0, 0, 0)


def _make_ssl_context(verify=True):
    """创建兼容 Windows 7 的 SSL 上下文

    关键问题: Windows 7 默认不启用 TLS 1.2，且系统证书存储可能不含现代 CA。
    verify=False 时跳过证书验证（Win7 全场景兼容）。
    """
    if verify:
        ctx = ssl.create_default_context()
    else:
        ctx = ssl._create_unverified_context()
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    except AttributeError:
        try:
            ctx.options |= getattr(ssl, 'OP_NO_TLSv1_0', 0) | getattr(ssl, 'OP_NO_TLSv1_1', 0)
        except Exception:
            pass
    return ctx


def _urlopen(url, timeout=10):
    """带 SSL 兼容的 urlopen（Windows 7 TLS 1.2 支持）

    策略：先验证证书，证书失败则回退到不验证（Win7 证书存储过旧时）。
    """
    import logging as _logging
    req = Request(url, headers={
        "User-Agent": "school-fitness-updater/1.0",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        ctx = _make_ssl_context(verify=True)
        return urlopen(req, timeout=timeout, context=ctx)
    except ssl.SSLError:
        _logging.warning("SSL 握手/证书验证失败，回退到不验证模式")
        ctx = _make_ssl_context(verify=False)
        return urlopen(req, timeout=timeout, context=ctx)


def check_latest_version():
    """查询 GitHub 最新版本，返回 (tag_name, html_url, asset_name, asset_url, size) 或 None"""
    try:
        resp = _urlopen(UPDATE_URL, timeout=10)
        data = json.loads(resp.read().decode())
    except HTTPError as e:
        if e.code == 404:
            return None, "未配置更新源（请管理员在 GitHub 创建 Release）"
        return None, f"服务器错误 ({e.code})"
    except (URLError, json.JSONDecodeError, OSError) as e:
        return None, f"无法连接 ({e.reason if hasattr(e, 'reason') else e})"

    tag = data.get("tag_name", "")
    if not tag:
        return None, "未找到版本信息"

    assets = data.get("assets", [])
    if not assets:
        return None, "Release 中没有可下载的附件"

    # 优先选主程序 EXE，回退到第一个附件
    asset = None
    for a in assets:
        name = a.get("name", "")
        if name == "SchoolFitness.exe" or "管理系统" in name:
            asset = a
            break
    if not asset:
        asset = assets[0]
    return (
        tag,
        data.get("html_url", RELEASE_URL),
        asset.get("name", ""),
        asset.get("browser_download_url", ""),
        asset.get("size", 0),
    )


def download_update(url, progress_callback=None):
    """下载更新文件到临时目录，返回本地路径"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
    tmp_path = tmp.name
    tmp.close()

    resp = _urlopen(url, timeout=120)
    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    chunk_size = 8192

    with open(tmp_path, "wb") as f:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress_callback and total:
                progress_callback(downloaded / total)

    return tmp_path


def launch_updater(old_exe, new_exe, app_dir):
    """启动独立升级进程，当前进程退出"""
    updater_exe = os.path.join(os.path.dirname(old_exe), "updater.exe")
    if not os.path.exists(updater_exe):
        updater_exe = os.path.join(app_dir, "updater.exe")
    args = json.dumps({
        "old_exe": old_exe,
        "new_exe": new_exe,
        "pid": os.getpid(),
        "app_dir": app_dir,
    })
    try:
        subprocess.Popen([updater_exe, args], cwd=os.path.dirname(old_exe))
    except Exception:
        subprocess.Popen([sys.executable, "-c", """
import json, os, sys, time, subprocess
args = json.loads(sys.argv[1])
if args.get('pid'):
    try:
        os.kill(args['pid'], 0)
        while True:
            time.sleep(0.5)
            os.kill(args['pid'], 0)
    except OSError:
        pass
else:
    time.sleep(3)
for _ in range(10):
    try:
        os.replace(args['new_exe'], args['old_exe'])
        break
    except PermissionError:
        time.sleep(0.5)
if os.name != 'nt':
    os.chmod(args['old_exe'], 0o755)
subprocess.Popen([args['old_exe']], cwd=args.get('app_dir', os.path.dirname(args['old_exe'])))
""", args], cwd=os.path.dirname(old_exe))


class UpdateDialog:
    """检查更新对话框"""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("检查更新")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        w, h = 420, 200
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self._start_check()

    def _build_ui(self):
        self.status_var = tk.StringVar(value="正在检查更新...")
        tk.Label(self.dialog, textvariable=self.status_var,
                 font=(TK_FONT, 11), wraplength=380).pack(pady=(30, 10))
        self.progress = ttk.Progressbar(self.dialog, mode='indeterminate', length=300)
        self.progress.pack(pady=5)
        self.progress.start()
        self.btn_frame = tk.Frame(self.dialog)
        self.btn_frame.pack(pady=15)

    def _start_check(self):
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        result = check_latest_version()
        self.dialog.after(0, lambda: self._on_result(result))

    def _on_result(self, result):
        self.progress.stop()
        self.progress.pack_forget()
        for w in self.btn_frame.winfo_children():
            w.destroy()

        if result is None or len(result) != 5:
            err = result[1] if isinstance(result, tuple) else "无法连接到 GitHub"
            self.status_var.set(f"检查失败: {err}")
            tk.Button(self.btn_frame, text="关闭", font=(TK_FONT, 10),
                      command=self.dialog.destroy).pack()
            return

        tag, html_url, asset_name, asset_url, size = result
        current = _parse_version(APP_VERSION)
        latest = _parse_version(tag)

        if latest <= current:
            self.status_var.set(f"已是最新版本 (v{APP_VERSION})")
            tk.Button(self.btn_frame, text="关闭", font=(TK_FONT, 10),
                      command=self.dialog.destroy).pack()
            return

        size_mb = size / 1024 / 1024
        self.status_var.set(f"发现新版本: {tag}\n当前版本: v{APP_VERSION}\n大小: {size_mb:.1f} MB")
        tk.Button(self.btn_frame, text="下载并升级", font=(TK_FONT, 10),
                  command=lambda: self._start_download(asset_url)).pack(side='left', padx=5)
        tk.Button(self.btn_frame, text="关闭", font=(TK_FONT, 10),
                  command=self.dialog.destroy).pack(side='left', padx=5)

    def _start_download(self, url):
        self.progress.pack(pady=5)
        self.progress.config(mode='determinate', value=0, maximum=100)
        for w in self.btn_frame.winfo_children():
            w.destroy()
        self.status_var.set("正在下载更新...")
        threading.Thread(target=self._download, args=(url,), daemon=True).start()

    def _set_progress(self, pct):
        self.dialog.after(0, lambda: self.progress.config(value=pct * 100))

    def _download(self, url):
        try:
            tmp_path = download_update(url, progress_callback=self._set_progress)
            self.dialog.after(0, lambda: self._on_downloaded(tmp_path))
        except Exception as e:
            self.dialog.after(0, lambda: self._on_download_error(str(e)))

    def _on_download_error(self, err):
        self.progress.pack_forget()
        self.status_var.set(f"下载失败: {err}")
        tk.Button(self.btn_frame, text="关闭", font=(TK_FONT, 10),
                  command=self.dialog.destroy).pack()

    def _on_downloaded(self, tmp_path):
        self.status_var.set("下载完成，正在准备升级...")
        self.dialog.update()
        time.sleep(0.5)

        if getattr(sys, 'frozen', False):
            old_exe = os.path.abspath(sys.executable)
        else:
            old_exe = os.path.abspath(sys.argv[0])
        app_dir = os.path.dirname(old_exe)

        launch_updater(old_exe, tmp_path, app_dir)
        self.dialog.after(100, self._do_exit)

    def _do_exit(self):
        self.dialog.master.destroy()
