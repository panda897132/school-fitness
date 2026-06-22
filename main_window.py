"""主界面 — 年级Tabs + 班级管理 + 学生数据表格"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import re
import os
import threading
import openpyxl
from config import (
    MAIN_WINDOW_SIZE, APP_TITLE, GRADE_NAMES, GRADE_ITEMS,
    STUDENT_COLUMNS, TK_FONT, NUM_TO_CN,
    COLOR_PRIMARY, COLOR_PRIMARY_DARK, COLOR_ACCENT,
    COLOR_SUCCESS, COLOR_DANGER, COLOR_WARNING, COLOR_NEUTRAL,
    COLOR_BG_LIGHT, COLOR_BG_WHITE, COLOR_BG_HEADER,
    COLOR_TEXT_LIGHT, COLOR_TEXT_MUTED,
    FONT_BOLD_14, FONT_BOLD_13, FONT_BOLD_12, FONT_BOLD_11, FONT_BOLD_10,
    FONT_NORMAL_11, FONT_NORMAL_10, FONT_NORMAL_9, FONT_SMALL_8
)
from score_engine import apply_scores_to_student
from excel_io import import_from_excel, export_statistics_report, parse_filename_for_import, quick_scan_excel
from merge_projects import merge_all, import_merged_excel
from updater import UpdateDialog
from config import APP_VERSION, APP_REPO, CN_TO_NUM
from charts import ChartBuilder
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from utils import center_window, get_grade_level, calc_item_stats, compute_grade_distribution
from dialogs.analysis import (
    show_class_analysis,
    show_class_full_analysis,
    show_grade_analysis,
    show_school_analysis,
    show_test_comparison,
    show_aggregate_test_comparison,
    _build_test_comparison_table,
    _build_bmi_by_grade_tab,
    _build_item_grade_distribution_tab,
)


class MainWindow:
    """主界面窗口"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        
        self.window = tk.Tk()
        self.window.title(APP_TITLE)
        
        w, h = MAIN_WINDOW_SIZE
        center_window(self.window, w, h)
        self.window.minsize(900, 500)
        
        self.current_grade = 1  # 当前选中的年级（默认一年级）
        self.current_class = None  # 当前选中的班级
        self._iid_to_sid = {}  # TreeView iid → 真实 student_id 映射
        self._importing = False  # 导入锁，防止并发导入
        self._add_class_dialog = None  # 添加班级对话框引用，防止重复打开
        self._grade_analysis_dialog = None  # 年级分析对话框引用
        self._school_analysis_dialog = None  # 全校分析对话框引用
        self._class_analysis_dialog = None  # 班级分析对话框引用
        self._context_menu_iid = None  # 右键菜单选中项
        
        self._build_menu()
        self._build_ui()
        self._setup_close_handler()
    
    def _setup_close_handler(self):
        """设置关闭处理"""
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """关闭窗口"""
        self.window.destroy()
    
    # ========== 菜单栏 ==========
    def _build_menu(self):
        menubar = tk.Menu(self.window, font=(TK_FONT, 10))
        self.window.config(menu=menubar)
        
        # 文件菜单
        self.file_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='文件', menu=self.file_menu)
        self.file_menu.add_command(label='导入Excel数据...', command=self._import_excel, accelerator='Ctrl+I')
        self.file_menu.add_command(label='批量导入Excel...', command=self._batch_import, accelerator='Ctrl+B')
        self.file_menu.add_command(label='导出统计报告...', command=self._export_report, accelerator='Ctrl+E')
        self.file_menu.add_separator()
        self.file_menu.add_command(label='按照项目批量导入...', command=self._merge_projects)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='测试轮次...', command=self._show_test_rounds)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='修改密码...', command=self._change_password)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='退出', command=self._on_close, accelerator='Ctrl+Q')
        
        # 数据菜单
        self.data_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='数据', menu=self.data_menu)
        self.data_menu.add_command(label='添加班级...', command=self._add_class)
        self.data_menu.add_command(label='删除班级', command=self._delete_class)
        self.data_menu.add_separator()
        self.data_menu.add_command(label='重新计算全部分数', command=self._recalc_all_scores)
        
        # 统计菜单
        self.stats_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='统计', menu=self.stats_menu)
        self.stats_menu.add_command(label='全校测试对比', command=self._show_school_test_comparison)
        self.stats_menu.add_separator()
        self.stats_menu.add_command(label='全校分析', command=self._show_school_analysis)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='帮助', menu=help_menu)
        help_menu.add_command(label='使用说明', command=self._show_help)
        help_menu.add_command(label='检查更新...', command=self._check_update)
        help_menu.add_separator()
        help_menu.add_command(label='关于', command=self._show_about)
        
        # 快捷键绑定
        self.window.bind('<Control-i>', lambda e: self._import_excel())
        self.window.bind('<Control-b>', lambda e: self._batch_import())
        self.window.bind('<Control-e>', lambda e: self._export_report())
        self.window.bind('<Control-q>', lambda e: self._on_close())
    
    # ========== 主界面布局 ==========
    def _build_ui(self):
        """构建主界面"""
        # 主容器
        main_paned = tk.PanedWindow(self.window, orient='horizontal', sashrelief='raised', sashwidth=4)
        main_paned.pack(fill='both', expand=True, padx=4, pady=4)
        
        # 左侧面板：年级+班级列表
        left_frame = tk.Frame(main_paned, width=220, bg=COLOR_BG_LIGHT)
        main_paned.add(left_frame, minsize=180)
        left_frame.pack_propagate(False)
        
        self._build_left_panel(left_frame)
        
        # 右侧面板：学生表格
        right_frame = tk.Frame(main_paned, bg=COLOR_BG_WHITE)
        main_paned.add(right_frame)
        
        self._build_right_panel(right_frame)
        
        # 状态栏
        self.status_bar = tk.Label(
            self.window, text='就绪', anchor='w',
            relief='sunken', font=(TK_FONT, 9),
            bg='#e8e8e8'
        )
        self.status_bar.pack(side='bottom', fill='x')
    
    def _build_left_panel(self, parent):
        """构建左侧面板"""
        # 标题
        tk.Label(
            parent, text='年级列表', 
            font=(TK_FONT, 12, 'bold'),
            bg=COLOR_PRIMARY, fg='white', pady=8
        ).pack(fill='x')
        
        # 年级列表
        grade_frame = tk.Frame(parent, bg=COLOR_BG_LIGHT)
        grade_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.grade_listbox = tk.Listbox(
            grade_frame,
            font=(TK_FONT, 11),
            selectmode='single',
            activestyle='none',
            bg=COLOR_BG_WHITE,
            relief='flat',
            highlightthickness=1,
            highlightcolor='#1976d2',
            selectbackground='#1976d2',
            selectforeground='white'
        )
        self.grade_listbox.pack(fill='both', expand=True, padx=4, pady=4)
        self.grade_listbox.bind('<<ListboxSelect>>', self._on_grade_select)
        self.grade_listbox.bind('<Button-3>', self._show_grade_context_menu)
        self.grade_listbox.bind('<Button-1>', self._on_grade_click_unpost)
        
        for i, gname in enumerate(GRADE_NAMES):
            self.grade_listbox.insert(tk.END, f"  {gname}")
        
        # 默认选中一年级
        self.grade_listbox.selection_set(0)
        
        # 分隔
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=4, pady=4)
        
        # 班级列表标题
        tk.Label(
            parent, text='班级列表',
            font=(TK_FONT, 11, 'bold'),
            bg=COLOR_BG_LIGHT, anchor='w'
        ).pack(fill='x', padx=8, pady=(4, 2))
        
        # 班级列表
        class_frame = tk.Frame(parent, bg=COLOR_BG_LIGHT)
        class_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.class_listbox = tk.Listbox(
            class_frame,
            font=(TK_FONT, 10),
            selectmode='single',
            activestyle='none',
            bg=COLOR_BG_WHITE,
            relief='flat',
            highlightthickness=1,
            highlightcolor='#1976d2',
            selectbackground='#1976d2',
            selectforeground='white'
        )
        self.class_listbox.pack(fill='both', expand=True, padx=4, pady=(4, 6))
        self.class_listbox.bind('<<ListboxSelect>>', self._on_class_select)
        self.class_listbox.bind('<Button-3>', self._show_class_context_menu)
        self.class_listbox.bind('<Button-1>', self._on_class_click_unpost)
        # 班级列表创建后刷新
        self._refresh_class_list()
    
    def _build_right_panel(self, parent):
        """构建右侧面板"""
        # 顶部工具栏
        toolbar = tk.Frame(parent, bg=COLOR_BG_HEADER, height=40)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)
        
        # 班级标题
        self.class_title_label = tk.Label(
            toolbar, text='请选择年级和班级',
            font=(TK_FONT, 13, 'bold'),
            bg=COLOR_BG_HEADER, fg=COLOR_PRIMARY
        )
        self.class_title_label.pack(side='left', padx=15, pady=5)
        
        # 测试轮次标签
        self.round_label = tk.Label(
            toolbar, text='',
            font=(TK_FONT, 9),
            bg=COLOR_BG_HEADER, fg='#ff9800'
        )
        self.round_label.pack(side='left', padx=(0, 15))
        
        # 搜索框
        search_frame = tk.Frame(toolbar, bg=COLOR_BG_HEADER)
        search_frame.pack(side='left', padx=(0, 10))
        tk.Label(search_frame, text='🔍', font=(TK_FONT, 9),
                 bg=COLOR_BG_HEADER).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                      font=(TK_FONT, 9), width=12,
                                      relief='solid', bd=1)
        self.search_entry.pack(side='left', ipady=1)
        self.search_var.trace('w', lambda *a: self._on_search_key())
        self._search_after_id = None  # 防抖id
        self._school_cache = None     # 全校学生缓存
        
        # 统计摘要
        self.stats_label = tk.Label(
            toolbar, text='',
            font=(TK_FONT, 10),
            bg=COLOR_BG_HEADER, fg=COLOR_TEXT_MUTED
        )
        self.stats_label.pack(side='right', padx=15)
        
        # 学生表格
        table_frame = tk.Frame(parent, bg=COLOR_BG_WHITE)
        table_frame.pack(fill='both', expand=True)
        
        # 使用 Treeview
        columns = [col[0] for col in STUDENT_COLUMNS]
        widths = [col[1] for col in STUDENT_COLUMNS]
        
        # 创建表格容器（带滚动条）
        tree_container = tk.Frame(table_frame)
        tree_container.pack(fill='both', expand=True)
        
        # 横向滚动条
        h_scrollbar = tk.Scrollbar(tree_container, orient='horizontal')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # 纵向滚动条
        v_scrollbar = tk.Scrollbar(tree_container, orient='vertical')
        v_scrollbar.pack(side='right', fill='y')
        
        # Treeview 格子线样式（深色边框）
        style = ttk.Style()
        style.configure('Treeview', borderwidth=1, relief='solid', rowheight=26, fieldbackground='#bdbdbd')
        style.configure('Treeview.Heading', borderwidth=1, relief='solid', font=(TK_FONT, 10, 'bold'), background='#e0e0e0')
        
        # Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show='headings',
            height=20,
            xscrollcommand=h_scrollbar.set,
            yscrollcommand=v_scrollbar.set
        )
        h_scrollbar.config(command=self.tree.xview)
        v_scrollbar.config(command=self.tree.yview)
        
        # 设置列
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col, anchor='center')
            self.tree.column(col, width=width, anchor='center', minwidth=40)
        
        self.tree.pack(fill='both', expand=True)
        

        # 右键菜单
        self._build_context_menu()
    
    def _build_context_menu(self):
        """学生表格右键菜单"""
        self.context_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        self.context_menu.add_command(label='编辑学生', command=self._edit_student)
        self.context_menu.add_command(label='删除学生', command=self._delete_student)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='重新计算分数', command=self._recalc_current)
        
        self.tree.bind('<Button-3>', self._show_context_menu)
        self.tree.bind('<Button-1>', self._on_tree_click_unpost)
    
    def _show_context_menu(self, event):
        """显示学生表格右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._context_menu_iid = item
            self.context_menu.post(event.x_root, event.y_root)
    
    def _on_tree_click_unpost(self, event):
        if hasattr(self, 'context_menu') and self.context_menu:
            self.context_menu.unpost()

    def _on_grade_click_unpost(self, event):
        if hasattr(self, '_last_grade_menu') and self._last_grade_menu:
            self._last_grade_menu.unpost()

    def _on_class_click_unpost(self, event):
        if hasattr(self, '_last_class_menu') and self._last_class_menu:
            self._last_class_menu.unpost()

    def _show_grade_context_menu(self, event):
        """显示年级列表右键菜单"""
        idx = self.grade_listbox.nearest(event.y)
        if idx >= 0:
            self.grade_listbox.selection_clear(0, tk.END)
            self.grade_listbox.selection_set(idx)
            self._on_grade_select(None)
        if hasattr(self, '_last_grade_menu') and self._last_grade_menu:
            self._last_grade_menu.unpost()
        grade_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        grade_name = GRADE_NAMES[idx] if idx < len(GRADE_NAMES) else '一年级'
        grade_num = idx + 1
        grade_menu.add_command(label=f'在"{grade_name}"添加班级...', command=lambda: self._add_class(grade_name))
        grade_menu.add_separator()
        grade_menu.add_command(label='年级分析', command=lambda g=grade_num: self._show_grade_analysis(g, False))
        grade_menu.add_command(label='年级测试对比', command=lambda g=grade_num: self._show_grade_test_comparison(g, False))
        grade_menu.add_separator()
        grade_menu.add_command(label='导出年级数据', command=lambda g=grade_num: self._export_grade_data(g))
        grade_menu.post(event.x_root, event.y_root)
        self._last_grade_menu = grade_menu
    
    def _show_class_context_menu(self, event):
        """显示班级列表右键菜单"""
        idx = self.class_listbox.nearest(event.y)
        if idx >= 0:
            self.class_listbox.selection_clear(0, tk.END)
            self.class_listbox.selection_set(idx)
            self._on_class_select(None)
        if hasattr(self, '_last_class_menu') and self._last_class_menu:
            self._last_class_menu.unpost()
        class_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        if self.current_class:
            # 获取右键点击的班级ID（而非当前选中的）
            classes = self.dm.get_classes_by_grade(self.current_grade) if self.current_grade else {}
            class_ids = sorted(classes.keys())
            click_class_id = class_ids[idx] if idx < len(class_ids) else self.current_class
            class_menu.add_command(label='班级分析', command=self._show_class_full_analysis)
            class_menu.add_command(label='测试对比', command=self._show_test_comparison)
            class_menu.add_command(label='重新计算分数', command=self._recalc_class_scores)
            class_menu.add_separator()
            class_menu.add_command(label='导出班级数据', command=lambda cid=click_class_id: self._export_class_data(cid))
            class_menu.add_separator()
            class_menu.add_command(label='删除班级', command=self._delete_class)
        class_menu.post(event.x_root, event.y_root)
        self._last_class_menu = class_menu
    
    def _show_class_analysis(self):
        """显示班级项目分析（单项+总成绩的等级占比）"""
        show_class_analysis(self)

    def _show_class_full_analysis(self):
        """班级综合分析（图表+数据）"""
        show_class_full_analysis(self)
    
    def _show_test_comparison(self):
        """多次测试数据对比"""
        show_test_comparison(self)
    
    def _show_school_test_comparison(self):
        """全校多次测试数据对比"""
        self._show_aggregate_test_comparison(grade=None, title='全校测试对比')
    
    def _show_grade_test_comparison(self, grade=None, show_selector=True):
        """年级多次测试数据对比"""
        if grade is None:
            grade = self.current_grade
            show_selector = True
        if not grade and not show_selector:
            messagebox.showwarning('提示', '请先选择年级')
            return
        
        gname = GRADE_NAMES[grade - 1] if grade else ''
        
        if not grade:
            # 没有年级，弹出选择对话框
            sel_dialog = tk.Toplevel(self.window)
            sel_dialog.title('选择年级')
            sel_dialog.geometry('300x200')
            sel_dialog.resizable(False, False)
            sel_dialog.transient(self.window)
            sel_dialog.grab_set()
            center_window(sel_dialog, 300, 200)
            
            tk.Label(sel_dialog, text='选择要对比的年级：', font=(TK_FONT, 12), pady=15).pack()
            g_var = tk.StringVar(value=GRADE_NAMES[0])
            g_combo = ttk.Combobox(sel_dialog, textvariable=g_var, values=GRADE_NAMES,
                                    state='readonly', width=12, font=(TK_FONT, 11))
            g_combo.current(0)
            g_combo.pack(pady=5)
            
            def _on_confirm():
                idx = GRADE_NAMES.index(g_var.get())
                sel_dialog.destroy()
                self._show_aggregate_test_comparison(grade=idx+1, title=f'{GRADE_NAMES[idx]}测试对比')
            
            tk.Button(sel_dialog, text='确认', command=_on_confirm, width=10,
                      bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 11)).pack(pady=10)
            return
        
        self._show_aggregate_test_comparison(grade=grade, title=f'{gname}测试对比')
    
    def _show_aggregate_test_comparison(self, grade=None, title='测试对比'):
        """聚合测试对比（全校或某年级）"""
        show_aggregate_test_comparison(self, grade=grade, title=title)
        

    def _on_grade_select(self, event):
        """年级选择事件"""
        if hasattr(self, '_last_grade_menu') and self._last_grade_menu:
            self._last_grade_menu.unpost()
        sel = self.grade_listbox.curselection()
        if not sel:
            return
        self.current_grade = sel[0] + 1  # 1-indexed
        self._refresh_class_list()
    
    def _on_class_select(self, event):
        """班级选择事件"""
        if hasattr(self, '_last_class_menu') and self._last_class_menu:
            self._last_class_menu.unpost()
        sel = self.class_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        classes = self.dm.get_classes_by_grade(self.current_grade) if self.current_grade else {}
        class_ids = sorted(classes.keys())
        
        if idx < len(class_ids):
            self.current_class = class_ids[idx]
            self._searching = False
            self._school_cache = None
            self._suppress_search = True
            self.search_var.set('')
            self._suppress_search = False
            self._refresh_student_table()
    
    def _refresh_class_list(self):
        """刷新班级列表"""
        if not hasattr(self, 'class_listbox'):
            return  # 控件尚未创建
        self.class_listbox.delete(0, tk.END)
        if self.current_grade is None:
            return
        
        classes = self.dm.get_classes_by_grade(self.current_grade)
        for cid in sorted(classes.keys()):
            cdata = classes[cid]
            self.class_listbox.insert(tk.END, f"  {cdata.get('name', cid)}")
        
        self.current_class = None
        self._refresh_student_table()
    
    def _refresh_student_table(self):
        """刷新学生表格"""
        if not hasattr(self, 'tree'):
            return  # 控件尚未创建
        # 清空
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._iid_to_sid.clear()
        
        if self.current_class is None:
            self.class_title_label.config(text='请选择年级和班级')
            self.round_label.config(text='')
            self.stats_label.config(text='')
            self._update_status('未选择班级')
            return
        
        class_data = self.dm.get_class(self.current_class)
        if class_data is None:
            return
        
        self.class_title_label.config(text=f"{class_data.get('name', self.current_class)} — 学生列表")
        
        # 显示测试轮次
        rounds = self.dm.get_test_rounds(self.current_class)
        cur = class_data.get('current_round', 0)
        if len(rounds) > 1:
            self.round_label.config(text=f'第{cur+1}/{len(rounds)}次测试')
        else:
            self.round_label.config(text='')
        
        students = self.dm.get_students(self.current_class)
        self._render_student_rows(students)
    
    def _render_student_rows(self, students):
        """渲染学生行到TreeView"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._iid_to_sid.clear()
        
        students.sort(key=lambda s: s.get('total_score', 0) or 0, reverse=True)
        for idx, s in enumerate(students):
            self._insert_student_row(s, idx + 1)
        
        self._update_class_stats(students)
        class_data = self.dm.get_class(self.current_class)
        cname = class_data.get('name', '') if class_data else ''
        self._update_status(f"当前班级: {cname} | 学生数: {len(students)}")
    
    def _on_search_key(self):
        """搜索框按键事件 — 300ms防抖后执行全校搜索"""
        if self._search_after_id:
            self.window.after_cancel(self._search_after_id)
        self._search_after_id = self.window.after(300, self._filter_students)
    
    def _filter_students(self):
        """全校搜索（使用 DataManager.search_students）"""
        if getattr(self, '_suppress_search', False):
            return
        keyword = self.search_var.get().strip()
        if not keyword:
            if hasattr(self, '_saved_class') and self._saved_class:
                self.current_class = self._saved_class
            self._searching = False
            self._refresh_student_table()
            return
        
        if not hasattr(self, '_searching') or not self._searching:
            self._saved_class = self.current_class
            self._searching = True
        
        raw_results = self.dm.search_students(keyword)
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._iid_to_sid.clear()
        
        if not raw_results:
            self.class_title_label.config(text=f'🔍 "{keyword}" — 无匹配')
            self.stats_label.config(text='')
            self.round_label.config(text='全校搜索')
            self._update_status(f'未找到 "{keyword}"')
            return
        
        class_cache = {}
        def _get_cname(cid):
            if cid not in class_cache:
                cdata = self.dm.get_class(cid)
                class_cache[cid] = cdata.get('name', cid) if cdata else cid
            return class_cache[cid]
        
        for s in raw_results:
            apply_scores_to_student(s, int(str(s.get('_class_id', '1'))[0]))
            s['_class_name'] = _get_cname(s['_class_id'])
        
        raw_results.sort(key=lambda s: s.get('total_score', 0) or 0, reverse=True)
        for idx, s in enumerate(raw_results):
            ds = dict(s)
            ds['name'] = f"[{s['_class_name']}] {s['name']}"
            self._insert_student_row(ds, idx + 1)
        
        self.class_title_label.config(text=f'🔍 "{keyword}" — {len(raw_results)}人')
        self.stats_label.config(text=f'来自 {len(set(s["_class_id"] for s in raw_results))} 个班级')
        self.round_label.config(text='全校搜索')
        self._update_status(f'找到 {len(raw_results)} 人')
    
    def _insert_student_row(self, student, row_num=0):
        """插入学生行（列顺序对齐模板格式）"""
        tests = student.get('tests', {})
        scores = student.get('scores', {})
        
        values = [
            row_num,
            student.get('name', ''),
            student.get('gender', ''),
            student.get('height', ''),
            student.get('weight', ''),
            student.get('bmi', ''),
            student.get('bmi_score', ''),
            tests.get('肺活量', ''),
            scores.get('肺活量', ''),
            tests.get('50米跑', ''),
            scores.get('50米跑', ''),
            tests.get('坐位体前屈', ''),
            scores.get('坐位体前屈', ''),
            tests.get('一分钟跳绳', ''),
            scores.get('一分钟跳绳', ''),
            student.get('jump_rope_bonus', ''),
            tests.get('仰卧起坐', ''),
            scores.get('仰卧起坐', ''),
            self._format_run_time(tests.get('50*8折返跑')),
            scores.get('50*8折返跑', ''),
            student.get('total_score', ''),
            student.get('total_grade', '')
        ]
        
        # 根据等级设置行颜色（四种等级对应四种底色）
        grade_level = student.get('total_grade', '')
        tags = []
        if grade_level == '优秀':
            tags.append('excellent')
        elif grade_level == '良好':
            tags.append('good')
        elif grade_level == '及格':
            tags.append('pass')
        elif grade_level == '不及格':
            tags.append('fail')
        elif grade_level == '数据不完整':
            tags.append('incomplete')
        
        sid = student.get('id')
        iid = sid if sid else f'tmp_{id(student)}'
        self.tree.insert('', tk.END, values=values, tags=tags, iid=iid)
        # 记录 iid→真实ID 映射，后续编辑/删除时可通过映射找回真实ID
        self._iid_to_sid[iid] = sid
        
        # 配置等级 tag 颜色（底色 + 文字色）
        self.tree.tag_configure('excellent', background='#c8e6c9', foreground='#1b5e20')
        self.tree.tag_configure('good', background='#bbdefb', foreground='#0d47a1')
        self.tree.tag_configure('pass', background='#fff9c4', foreground='#e65100')
        self.tree.tag_configure('fail', background='#ffcdd2', foreground='#b71c1c')
        self.tree.tag_configure('incomplete', background='#e0e0e0', foreground='#757575')
    
    def _format_run_time(self, val):
        """格式化折返跑时间（m.ss 小数格式，与导入/导出一致）"""
        if val is None or val == '':
            return ''
        try:
            v = float(val)
            if v >= 60:
                m = int(v // 60)
                s = int(v % 60)
                return f"{m}.{s:02d}"
            return str(v)
        except (ValueError, TypeError):
            return str(val)
    
    def _update_class_stats(self, students):
        """更新班级统计"""
        total = len(students)
        if total == 0:
            self.stats_label.config(text='')
            return
        
        counts = compute_grade_distribution(students)['counts']
        
        self.stats_label.config(
            text=f"优秀:{counts['优秀']} 良好:{counts['良好']} 及格:{counts['及格']} 不及格:{counts['不及格']} | 共{total}人"
        )
    
    def _update_status(self, text):
        """更新状态栏"""
        self.status_bar.config(text=text)
    
    def _set_buttons_state(self, state):
        """设置所有操作按钮状态（normal/disabled），导入期间禁用防止重复点击"""
        for menu in (self.file_menu, self.data_menu, self.stats_menu):
            try:
                end = menu.index('end')
            except tk.TclError:
                continue
            for idx in range(end + 1):
                try:
                    menu.entryconfigure(idx, state=state)
                except tk.TclError:
                    pass
    
    # ========== 菜单命令 ==========
    def _import_excel(self):
        """导入Excel数据"""
        if self._importing:
            return
        self._importing = True
        
        filepath = filedialog.askopenfilename(
            title='选择Excel文件',
            filetypes=[('Excel文件', '*.xlsx *.xls'), ('所有文件', '*.*')]
        )
        if not filepath:
            self._importing = False
            return
        
        self._update_status('正在检查文件格式...')
        self.window.update()
        
        # 快速检测文件格式
        grade_hint = None
        class_prefix = None
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
            grade_sheet_names = {'一年级', '二年级', '三年级', '四年级', '五年级', '六年级'}
            has_old_format = any(sn in grade_sheet_names for sn in wb.sheetnames)
            wb.close()
            
            if not has_old_format:
                # 新格式——弹出对话框让用户指定年级和班级编号
                grade_str = simpledialog.askstring(
                    '新格式导入 - 年级',
                    '检测到新格式Excel文件。\n\n请指定年级 (1-6，留空则自动推断):',
                    initialvalue=''
                )
                if grade_str and grade_str.strip().isdigit():
                    g = int(grade_str.strip())
                    if 1 <= g <= 6:
                        grade_hint = g
                
                class_prefix = simpledialog.askstring(
                    '新格式导入 - 班级编号',
                    '请输入班级编号 (如501，留空则自动生成):',
                    initialvalue=f'{grade_hint or 5}01' if grade_hint else ''
                )
                if class_prefix:
                    class_prefix = class_prefix.strip()
        except Exception:
            pass  # 检测失败则走自动推断路径
        
        self._update_status('正在导入...')
        
        # 禁用按钮，防止重复点击
        self._set_buttons_state('disabled')
        
        def do_import():
            """在 worker 线程中执行 Excel 解析（绝不访问 GUI 控件）"""
            try:
                result = import_from_excel(filepath, grade_hint=grade_hint, class_prefix=class_prefix)
                self.window.after(0, lambda r=result: self._on_import_done(r))
            except Exception as e:
                self.window.after(0, lambda e_msg=str(e): self._on_import_error(e_msg))
        
        t = threading.Thread(target=do_import, daemon=True)
        t.start()
    
    def _on_import_done(self, result):
        """导入完成回调（主线程）"""
        if result['success']:
            # 合并导入的数据
            classes = result['data'].get('classes', {})
            imported_classes = {}
            
            for cid, cdata in classes.items():
                # 如果班级已存在，询问是否覆盖
                existing = self.dm.get_class(cid)
                if existing and self.dm.get_students(cid):
                    if not messagebox.askyesno('确认', f"班级 {cdata.get('name', cid)} 已有数据，是否覆盖？"):
                        continue  # 用户跳过，不导入此班级
                
                # 确保班级存在
                if not existing:
                    self.dm.add_class(cid, cdata.get('grade', 1), cdata.get('name', f'班级{cid}'))
                
                imported_classes[cid] = cdata
            
            # 导入后自动计算分数
            self._recalc_imported(imported_classes)
            # 保存计算后的数据
            for cid, cdata in imported_classes.items():
                self.dm.import_students(cid, cdata.get('students', []))
            
            messagebox.showinfo('导入完成', result['message'])
            self._refresh_class_list()
            if self.current_class:
                self._refresh_student_table()
        else:
            messagebox.showerror('导入失败', result['message'])
        
        self._update_status('就绪')
        self._set_buttons_state('normal')
        self._importing = False
    
    def _merge_projects(self):
        filepaths = filedialog.askopenfilenames(
            title='选择体测项目文件（可多选）',
            initialdir=os.path.expanduser('~/桌面/体测项目'),
            filetypes=[('Excel文件', '*.xlsx'), ('所有文件', '*.*')]
        )
        if not filepaths:
            return
        wb, error = merge_all(list(filepaths))
        if error:
            messagebox.showerror('错误', error)
            return
        folder = os.path.dirname(filepaths[0])
        out_path = os.path.join(folder, '合成数据.xlsx')
        wb.save(out_path)
        
        # 直接导入
        total, ok_rate, avg = import_merged_excel(out_path, self.dm)
        messagebox.showinfo('完成', 
            f'✅ 合成并导入完成！\n\n'
            f'学生: {total} 人\n'
            f'优良率: {ok_rate}%\n'
            f'平均分: {avg}')

    def _batch_import(self):
        """批量导入：选择多个文件，从文件名自动识别年级/班级"""
        if self._importing:
            return
        self._importing = True
        
        filepaths = filedialog.askopenfilenames(
            title='批量选择Excel文件',
            filetypes=[('Excel文件', '*.xlsx *.xls'), ('所有文件', '*.*')]
        )
        if not filepaths:
            self._importing = False
            return
        
        # 扫描所有文件
        self._update_status('正在扫描文件...')
        self.window.update()
        
        files_info = []
        for fp in filepaths:
            info = parse_filename_for_import(fp)
            scan = quick_scan_excel(fp)
            info['filepath'] = fp
            info['filename'] = os.path.basename(fp)
            info['scan'] = scan
            
            # 如果文件名没识别到班级，尝试从扫描结果获取
            if info['class_id'] is None and scan.get('classes'):
                first_cid = next(iter(scan['classes']))
                if first_cid != '_new_':
                    info['class_id'] = first_cid
                    info['grade'] = scan['classes'][first_cid].get('grade', info['grade'])
                    cn = NUM_TO_CN.get(info['grade'], str(info['grade']))
                    info['class_name'] = f'{cn}({first_cid[-2:]})班' if len(first_cid) >= 2 else first_cid
            
            # 检查目标班级状态
            if info['class_id']:
                existing = self.dm.get_class(info['class_id'])
                if existing:
                    has_data = len(self.dm.get_students(info['class_id'])) > 0
                    info['status'] = 'existing_data' if has_data else 'existing_empty'
                else:
                    info['status'] = 'new'
            else:
                info['status'] = 'unknown'
            
            files_info.append(info)
        
        self._update_status('就绪')
        self._importing = False
        
        if not files_info:
            messagebox.showinfo('提示', '未选择任何文件')
            return
        
        self._show_batch_import_preview(files_info)
    
    def _show_batch_import_preview(self, files_info):
        """批量导入预览窗口"""
        dialog = tk.Toplevel(self.window)
        dialog.title(f'批量导入预览 — {len(files_info)} 个文件')
        dialog.geometry('860x600')
        dialog.resizable(True, True)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 860, 600)
        
        # 顶部标题
        header = tk.Frame(dialog, bg=COLOR_PRIMARY)
        header.pack(fill='x')
        tk.Label(header, text=f'扫描完成，共 {len(files_info)} 个文件',
                 font=(TK_FONT, 13, 'bold'), bg=COLOR_PRIMARY, fg='white', pady=10).pack()
        
        # 表格区域
        tree_frame = tk.Frame(dialog)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        cols = ('选择', '文件名', '年级', '班级', '班级编号', '人数', '状态')
        widths = (40, 240, 60, 80, 70, 50, 100)
        
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='extended')
        for c, w in zip(cols, widths):
            tree.heading(c, text=c, anchor='center')
            tree.column(c, width=w, anchor='center' if c != '文件名' else 'w', minwidth=30)
        tree.column('文件名', width=280)
        
        vsb = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # 填充数据
        grade_names_map = {1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级', 5: '五年级', 6: '六年级'}
        status_labels = {
            'existing_data': '⚠ 已有数据',
            'existing_empty': '✅ 已有班级(空)',
            'new': '🆕 自动创建',
            'unknown': '❓ 无法识别',
        }
        
        for info in files_info:
            scan = info['scan']
            student_count = scan.get('total_rows', 0)
            grade_text = grade_names_map.get(info['grade'], '?') if info['grade'] else '?'
            cname = info.get('class_name', '') or ''
            cid = info.get('class_id', '') or ''
            status = status_labels.get(info['status'], info['status'])
            
            iid = tree.insert('', tk.END, values=('☑', info['filename'], grade_text, cname, cid, student_count, status))
            info['_tree_iid'] = iid
        
        # 点击切换选中
        def _toggle_select(event):
            item = tree.identify_row(event.y)
            col = tree.identify_column(event.x)
            if item and col == '#1':
                vals = list(tree.item(item, 'values'))
                vals[0] = '☐' if vals[0] == '☑' else '☑'
                tree.item(item, values=vals)
        
        tree.bind('<Button-1>', _toggle_select)
        
        # 全选/取消按钮
        btn_row = tk.Frame(dialog)
        btn_row.pack(fill='x', padx=8, pady=(0, 2))
        
        def _select_all():
            for item in tree.get_children():
                vals = list(tree.item(item, 'values'))
                vals[0] = '☑'
                tree.item(item, values=vals)
        
        def _deselect_all():
            for item in tree.get_children():
                vals = list(tree.item(item, 'values'))
                vals[0] = '☐'
                tree.item(item, values=vals)
        
        tk.Button(btn_row, text='全选', command=_select_all,
                  font=(TK_FONT, 9), relief='flat', padx=10).pack(side='left', padx=2)
        tk.Button(btn_row, text='取消全选', command=_deselect_all,
                  font=(TK_FONT, 9), relief='flat', padx=10).pack(side='left', padx=2)
        
        tk.Label(btn_row, text='提示: 点击第一列切换 ☑/☐',
                 font=(TK_FONT, 9), fg=COLOR_TEXT_LIGHT).pack(side='right', padx=10)
        
        # 底部操作按钮
        bottom = tk.Frame(dialog, bg=COLOR_BG_LIGHT)
        bottom.pack(fill='x', padx=8, pady=(8, 10))
        
        progress_frame = tk.Frame(bottom, bg=COLOR_BG_LIGHT)
        progress_frame.pack(fill='x', pady=(0, 8))
        
        self._batch_progress = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        
        status_label = tk.Label(bottom, text='', font=(TK_FONT, 9), bg=COLOR_BG_LIGHT, fg=COLOR_TEXT_MUTED)
        status_label.pack()
        
        def _do_batch_import():
            selected = []
            for item in tree.get_children():
                vals = tree.item(item, 'values')
                if vals[0] == '☑':
                    for info in files_info:
                        if info.get('_tree_iid') == item:
                            selected.append(info)
                            break
            
            if not selected:
                messagebox.showwarning('提示', '请至少选择一个文件')
                return
            
            btn_cancel.config(state='disabled')
            btn_confirm.config(state='disabled')
            
            total = len(selected)
            success_count = 0
            error_msgs = []
            
            self._batch_progress.pack(fill='x')
            self._batch_progress['maximum'] = total
            self._batch_progress['value'] = 0
            
            for i, info in enumerate(selected):
                status_label.config(text=f'导入中 ({i+1}/{total}): {info["filename"]}')
                self._batch_progress['value'] = i
                dialog.update()
                
                try:
                    cid = info['class_id']
                    grade = info['grade']
                    
                    if not cid or not grade:
                        error_msgs.append(f'{info["filename"]}: 无法确定年级/班级')
                        continue
                    
                    # 自动创建班级
                    existing = self.dm.get_class(cid)
                    if not existing:
                        self.dm.add_class(cid, grade, info.get('class_name', f'班级{cid}'))
                    
                    # 导入数据
                    result = import_from_excel(info['filepath'], grade_hint=grade, class_prefix=cid)
                    if result['success']:
                        classes = result['data'].get('classes', {})
                        for imported_cid, cdata in classes.items():
                            students = cdata.get('students', [])
                            if students:
                                # 计算分数
                                for s in students:
                                    apply_scores_to_student(s, grade)
                                self.dm.import_students(imported_cid, students)
                        success_count += 1
                    else:
                        error_msgs.append(f'{info["filename"]}: {result["message"]}')
                except Exception as e:
                    error_msgs.append(f'{info["filename"]}: {str(e)}')
            
            self._batch_progress['value'] = total
            self._batch_progress.pack_forget()
            
            # 摘要
            summary = f'导入完成: 成功 {success_count}/{total}'
            if error_msgs:
                summary += f'\n\n失败详情:\n' + '\n'.join(error_msgs[:5])
                if len(error_msgs) > 5:
                    summary += f'\n...等共 {len(error_msgs)} 个错误'
            
            messagebox.showinfo('批量导入结果', summary)
            self._refresh_class_list()
            if self.current_class:
                self._refresh_student_table()
            dialog.destroy()
        
        btn_confirm = tk.Button(bottom, text='确认导入', command=_do_batch_import,
                                bg=COLOR_ACCENT, fg='white',
                                font=(TK_FONT, 11, 'bold'),
                                relief='flat', padx=20, pady=8, cursor='hand2')
        btn_confirm.pack(side='left', padx=(40, 10))
        
        btn_cancel = tk.Button(bottom, text='取消', command=dialog.destroy,
                               bg='#ccc', fg='#333',
                               font=(TK_FONT, 11),
                               relief='flat', padx=20, pady=8, cursor='hand2')
        btn_cancel.pack(side='left')
    
    def _on_import_error(self, error_msg):
        """导入异常回调（主线程）"""
        messagebox.showerror("导入错误", f"导入过程异常:\n{error_msg}")
        self._update_status('就绪')
        self._set_buttons_state('normal')
        self._importing = False
    
    def _export_report(self):
        """导出统计报告"""
        scope_choice = simpledialog.askstring(
            '导出范围', '请输入导出范围:\n全校(all) / 年级(1-6) / 班级(如101)',
            initialvalue='all'
        )
        if not scope_choice:
            return
        
        filepath = filedialog.asksaveasfilename(
            title='保存统计报告',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')]
        )
        if not filepath:
            return
        
        scope_choice = scope_choice.strip().lower()
        
        if scope_choice == 'all':
            success, msg = export_statistics_report(self.dm, filepath, scope='全校')
        elif scope_choice.isdigit() and 1 <= int(scope_choice) <= 6:
            success, msg = export_statistics_report(self.dm, filepath, scope='年级', grade=int(scope_choice))
        else:
            success, msg = export_statistics_report(self.dm, filepath, scope='班级', class_id=scope_choice)
        
        if success:
            messagebox.showinfo('导出成功', msg)
        else:
            messagebox.showerror('导出失败', msg)
    
    def _export_class_data(self, class_id):
        """右键菜单：导出指定班级数据"""
        filepath = filedialog.asksaveasfilename(
            title='导出班级数据',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')]
        )
        if not filepath:
            return
        success, msg = export_statistics_report(self.dm, filepath, scope='班级', class_id=class_id)
        if success:
            messagebox.showinfo('导出成功', msg)
        else:
            messagebox.showerror('导出失败', msg)
    
    def _export_grade_data(self, grade):
        """右键菜单：导出指定年级数据"""
        filepath = filedialog.asksaveasfilename(
            title='导出年级数据',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')]
        )
        if not filepath:
            return
        success, msg = export_statistics_report(self.dm, filepath, scope='年级', grade=grade)
        if success:
            messagebox.showinfo('导出成功', msg)
        else:
            messagebox.showerror('导出失败', msg)
    
    def _change_password(self):
        """修改密码"""
        dialog = tk.Toplevel(self.window)
        dialog.title('修改密码')
        dialog.geometry('350x280')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()

        # 居中
        x = self.window.winfo_x() + (self.window.winfo_width() - 350) // 2
        y = self.window.winfo_y() + (self.window.winfo_height() - 280) // 2
        dialog.geometry(f'+{x}+{y}')

        frame = tk.Frame(dialog, bg=COLOR_BG_WHITE)
        frame.pack(fill='both', expand=True, padx=20, pady=20)

        tk.Label(frame, text='旧密码:', bg=COLOR_BG_WHITE).pack(anchor='w', pady=(8, 0))
        old_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        old_pw.pack(fill='x', ipady=4, pady=(2, 6))

        tk.Label(frame, text='新密码:', bg=COLOR_BG_WHITE).pack(anchor='w')
        new_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        new_pw.pack(fill='x', ipady=4, pady=(2, 6))

        tk.Label(frame, text='确认密码:', bg=COLOR_BG_WHITE).pack(anchor='w')
        confirm_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        confirm_pw.pack(fill='x', ipady=4, pady=(2, 6))

        def do_change():
            old = old_pw.get()
            new = new_pw.get()
            confirm = confirm_pw.get()

            if not old or not new:
                messagebox.showwarning('提示', '请填写所有字段', parent=dialog)
                return
            if new != confirm:
                messagebox.showwarning('提示', '两次输入的新密码不一致', parent=dialog)
                return
            if len(new) < 4:
                messagebox.showwarning('提示', '密码长度至少4位', parent=dialog)
                return

            if self.dm.change_password('admin', old, new):
                messagebox.showinfo('成功', '密码修改成功！', parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror('失败', '旧密码错误', parent=dialog)

        btn_frame = tk.Frame(frame, bg=COLOR_BG_WHITE)
        btn_frame.pack(pady=(15, 0))

        tk.Button(
            btn_frame, text='确定', command=do_change,
            bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 10, 'bold'),
            relief='flat', padx=20, pady=6
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame, text='取消', command=dialog.destroy,
            bg='#ccc', fg='#333', font=(TK_FONT, 10),
            relief='flat', padx=20, pady=6
        ).pack(side='left', padx=5)
    
    def _add_class(self, default_grade_name=None):
        """添加班级"""
        
        # 防止重复打开对话框
        if self._add_class_dialog and self._add_class_dialog.winfo_exists():
            self._add_class_dialog.lift()
            self._add_class_dialog.focus_force()
            return
        
        dialog = tk.Toplevel(self.window)
        dialog.title('添加班级')
        dialog.geometry('340x310')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 340, 310)
        self._add_class_dialog = dialog
        dialog.protocol('WM_DELETE_WINDOW', lambda: (setattr(self, '_add_class_dialog', None), dialog.destroy()))
        dialog.bind('<Destroy>', lambda e: setattr(self, '_add_class_dialog', None))
        
        frame = tk.Frame(dialog, bg=COLOR_BG_WHITE)
        frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 年级行
        grade_row = tk.Frame(frame, bg=COLOR_BG_WHITE)
        grade_row.pack(fill='x', pady=(0, 8))
        tk.Label(grade_row, text='年级：', font=(TK_FONT, 11), bg=COLOR_BG_WHITE, width=8, anchor='w').pack(side='left')
        default_grade = default_grade_name or GRADE_NAMES[0]
        grade_var = tk.StringVar(value=default_grade)
        grade_combo = ttk.Combobox(grade_row, textvariable=grade_var, values=GRADE_NAMES, state='readonly', width=18, font=(TK_FONT, 11))
        if default_grade_name and default_grade_name in GRADE_NAMES:
            grade_combo.current(GRADE_NAMES.index(default_grade_name))
        else:
            grade_combo.current(0)
        grade_combo.pack(side='left', fill='x', expand=True)
        
        # 班级编号行
        id_row = tk.Frame(frame, bg=COLOR_BG_WHITE)
        id_row.pack(fill='x', pady=(0, 4))
        tk.Label(id_row, text='班级编号：', font=(TK_FONT, 11), bg=COLOR_BG_WHITE, width=8, anchor='w').pack(side='left')
        class_id_entry = tk.Entry(id_row, font=(TK_FONT, 11), width=18)
        class_id_entry.pack(side='left', fill='x', expand=True, ipady=3)
        class_id_entry.bind('<Return>', lambda e: do_add())
        
        tk.Label(frame, text='例: 101=一(1)班, 502=五(2)班', font=(TK_FONT, 8), bg=COLOR_BG_WHITE, fg=COLOR_TEXT_LIGHT).pack(anchor='w', pady=(0, 8))
        
        # 已有班级（紧凑行显示）
        existing_frame = tk.Frame(frame, bg=COLOR_BG_LIGHT, relief='solid', bd=1)
        existing_frame.pack(fill='x', pady=(0, 10))
        existing_label = tk.Label(
            existing_frame, text='', font=(TK_FONT, 9), bg=COLOR_BG_LIGHT, fg=COLOR_TEXT_MUTED,
            justify='left', anchor='w', wraplength=290
        )
        existing_label.pack(fill='x', padx=8, pady=5)
        
        def _refresh_existing():
            grade_name = grade_var.get()
            grade_num = CN_TO_NUM.get(grade_name[0], 0)
            if grade_num:
                all_classes = self.dm.get_classes_by_grade(grade_num)
                if all_classes:
                    items = [f'{cid}' for cid in sorted(all_classes.keys())]
                    existing_label.config(text='已存在: ' + '  '.join(items), fg='#333')
                else:
                    existing_label.config(text='暂无班级', fg=COLOR_TEXT_LIGHT)
                class_id_entry.delete(0, tk.END)
                class_id_entry.insert(0, f'{grade_num}01')
        
        grade_combo.bind('<<ComboboxSelected>>', lambda e: _refresh_existing())
        _refresh_existing()
        class_id_entry.focus_set()
        class_id_entry.select_range(0, 'end')
        
        def do_add():
            grade_name = grade_var.get()
            cid = class_id_entry.get().strip()
            if not cid:
                messagebox.showwarning('提示', '请输入班级编号', parent=dialog)
                return
            
            grade = CN_TO_NUM.get(grade_name[0], 0)
            if grade == 0:
                messagebox.showerror('错误', '无效年级', parent=dialog)
                return
            
            cname = f"{grade_name}({cid[-2:]})班" if len(cid) >= 2 else f"{grade_name}({cid})班"
            success, msg = self.dm.add_class(cid, grade, cname)
            
            if success:
                messagebox.showinfo('成功', msg, parent=dialog)
                dialog.destroy()
                self._refresh_class_list()
            else:
                messagebox.showerror('失败', msg, parent=dialog)
        
        # 按钮行
        btn_row = tk.Frame(frame, bg=COLOR_BG_WHITE)
        btn_row.pack(fill='x', pady=(6, 0))
        tk.Button(
            btn_row, text='✓ 确认添加', command=do_add,
            bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 11, 'bold'),
            relief='flat', padx=25, pady=8, cursor='hand2',
            activebackground='#1565c0', activeforeground='white'
        ).pack(side='left', expand=True, fill='x')
        tk.Button(
            btn_row, text='取消', command=dialog.destroy,
            bg='#ccc', fg='#333', font=(TK_FONT, 11),
            relief='flat', padx=25, pady=8, cursor='hand2'
        ).pack(side='left', padx=(8, 0))
    
    def _delete_class(self):
        """删除班级"""
        if not self.current_class:
            messagebox.showwarning('提示', '请先选择班级')
            return
        
        class_data = self.dm.get_class(self.current_class)
        cname = class_data.get('name', self.current_class) if class_data else self.current_class
        
        if messagebox.askyesno('确认删除', f'确定要删除班级 "{cname}" 及其所有学生数据吗？\n此操作不可恢复！'):
            success, msg = self.dm.delete_class(self.current_class)
            if success:
                self.current_class = None
                self._refresh_class_list()
                self._update_status('班级已删除')
            else:
                messagebox.showerror('错误', msg)
    
    def _add_student(self):
        """添加学生"""
        if not self.current_class:
            messagebox.showwarning('提示', '请先选择班级')
            return
        self._student_dialog(mode='add')
    
    def _edit_student(self, event=None):
        """编辑学生"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('提示', '请先选择学生')
            return
        iid = sel[0]
        student_id = self._iid_to_sid.get(iid, iid)

        class_id = self.current_class
        if getattr(self, '_searching', False):
            results = self.dm.search_students('')
            for s in results:
                if s.get('id') == student_id:
                    class_id = s.get('_class_id', self.current_class)
                    break

        self._student_dialog(mode='edit', student_id=student_id, class_id=class_id)
    
    def _delete_student(self):
        """删除学生"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('提示', '请先选择学生')
            return
        
        if messagebox.askyesno('确认删除', '确定要删除该学生吗？'):
            for iid in sel:
                real_sid = self._iid_to_sid.get(iid, iid)
                self.dm.delete_student(self.current_class, real_sid)
            self._refresh_student_table()
            self._update_status('学生已删除')
    
    def _student_dialog(self, mode='add', student_id=None, class_id=None):
        """学生编辑对话框"""
        if class_id is None:
            class_id = self.current_class
        class_data = self.dm.get_class(class_id) if class_id else None
        grade = class_data.get('grade', self.current_grade or 1) if class_data else (self.current_grade or 1)

        dialog = tk.Toplevel(self.window)
        dialog.title('添加学生' if mode == 'add' else '编辑学生')
        dialog.geometry('500x650')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 500, 650)

        # 已存在的学生数据
        student_data = {}
        if mode == 'edit' and student_id and class_id:
            students = self.dm.get_students(class_id)
            for s in students:
                if s.get('id') == student_id:
                    student_data = s
                    break
        
        # 可滚动内容
        canvas = tk.Canvas(dialog, bg=COLOR_BG_WHITE, highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLOR_BG_WHITE)
        
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 表单字段
        padx = 30
        pady_frame = 15
        
        def add_field(label, key, row, default='', entry_type='text'):
            tk.Label(scroll_frame, text=label, bg=COLOR_BG_WHITE, font=(TK_FONT, 10), anchor='w').grid(
                row=row, column=0, sticky='w', padx=padx, pady=(8, 2))
            
            if key == 'gender':
                var = tk.StringVar(value=default or '男')
                combo = ttk.Combobox(scroll_frame, textvariable=var, values=['男', '女'], state='readonly', width=38)
                combo.grid(row=row, column=1, padx=(10, padx), pady=(8, 2), ipady=3, sticky='ew')
                return var
            
            var = tk.StringVar(value=str(default) if default else '')
            entry = tk.Entry(scroll_frame, textvariable=var, font=(TK_FONT, 10), width=40)
            entry.grid(row=row, column=1, padx=(10, padx), pady=(8, 2), ipady=3, sticky='ew')
            return var
        
        row = 0
        # 基本信息（对齐模板列顺序：姓名→性别→身高→体重）
        v_name = add_field('姓名:', 'name', row, student_data.get('name', ''))
        row += 1
        v_gender = add_field('性别:', 'gender', row, student_data.get('gender', '男'))
        row += 1
        v_student_number = add_field('学号:', 'student_number', row, student_data.get('student_number', ''))
        row += 1
        v_student_code = add_field('学籍号:', 'student_code', row, student_data.get('student_code', ''))
        row += 1
        v_height = add_field('身高(cm) [100-200]:', 'height', row, student_data.get('height', ''))
        row += 1
        v_weight = add_field('体重(kg) [20-80]:', 'weight', row, student_data.get('weight', ''))
        row += 1
        
        # 分隔线
        ttk.Separator(scroll_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', padx=padx, pady=10)
        row += 1
        
        tk.Label(scroll_frame, text='测试项目成绩', font=(TK_FONT, 11, 'bold'), bg=COLOR_BG_WHITE, fg='#555').grid(
            row=row, column=0, columnspan=2, pady=(5, 5))
        row += 1
        
        # 测试项目
        tests = student_data.get('tests', {})
        items = GRADE_ITEMS.get(grade, [])
        test_vars = {}
        for item_name in items:
            label = item_name
            if item_name == '50*8折返跑':
                label += '(分.秒) [60-180秒]'
            elif item_name == '50米跑':
                label += '(秒) [7-20]'
            elif item_name == '肺活量':
                label += '(ml) [500-4000]'
            elif item_name == '坐位体前屈':
                label += '(cm) [-20~30]'
            elif item_name == '一分钟跳绳':
                label += '(个) [0-300]'
            elif item_name == '仰卧起坐':
                label += '(个) [0-100]'
            default_val = tests.get(item_name, '')
            # 如果是折返跑，格式化为时间
            if item_name == '50*8折返跑' and default_val:
                try:
                    default_val = self._format_run_time(default_val)
                except Exception:
                    default_val = str(default_val)
            test_vars[item_name] = add_field(f'{label}:', item_name, row, str(default_val) if default_val else '')
            row += 1
        
        # 按钮
        btn_frame = tk.Frame(scroll_frame, bg=COLOR_BG_WHITE)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(20, 15))
        
        def save():
            data = {
                'student_number': v_student_number.get(),
                'name': v_name.get(),
                'student_code': v_student_code.get(),
                'gender': v_gender.get(),
                'height': None,
                'weight': None,
                'tests': {}
            }
            
            # 姓名必填
            if not data['name'].strip():
                messagebox.showwarning('提示', '请输入学生姓名', parent=dialog)
                return
            
            # 身高体重 — 格式+范围校验
            h = v_height.get().strip()
            if h:
                try:
                    hv = float(h)
                    if hv < 80 or hv > 220:
                        if not messagebox.askyesno('数据异常', f'身高 {hv}cm 超出正常范围(80-220)，是否仍要保存？', parent=dialog):
                            return
                    data['height'] = hv
                except ValueError:
                    messagebox.showwarning('提示', f'身高格式不正确: {h}', parent=dialog)
                    return
            
            w = v_weight.get().strip()
            if w:
                try:
                    wv = float(w)
                    if wv < 15 or wv > 120:
                        if not messagebox.askyesno('数据异常', f'体重 {wv}kg 超出正常范围(15-120)，是否仍要保存？', parent=dialog):
                            return
                    data['weight'] = wv
                except ValueError:
                    messagebox.showwarning('提示', f'体重格式不正确: {w}', parent=dialog)
                    return
            
            # 范围定义: (min, max, unit, 异常提示消息)
            RANGES = {
                '肺活量': (200, 6000, 'ml', '小学生肺活量一般在500-4000之间'),
                '50米跑': (5, 25, '秒', '50米跑一般在7-20秒之间'),
                '坐位体前屈': (-35, 45, 'cm', '坐位体前屈一般在-20~30cm之间'),
                '一分钟跳绳': (0, 350, '个', '一分钟跳绳一般在0-250个之间'),
                '仰卧起坐': (0, 120, '个', '仰卧起坐一般在0-80个之间'),
                '50*8折返跑': (50, 240, '秒', '折返跑一般在70-180秒之间'),
            }
            
            warnings = []
            for item_name, var in test_vars.items():
                val = var.get().strip()
                if val:
                    if '折返跑' in item_name:
                        m = re.match(r"(\d+)'(\d+)", val)
                        if m:
                            data['tests'][item_name] = float(m.group(1)) * 60 + float(m.group(2))
                        else:
                            try:
                                data['tests'][item_name] = float(val)
                            except ValueError:
                                data['tests'][item_name] = 0
                    else:
                        try:
                            data['tests'][item_name] = float(val)
                        except ValueError:
                            messagebox.showwarning('提示', f'{item_name} 格式不正确: {val}', parent=dialog)
                            return
                    
                    # 范围校验
                    r = RANGES.get(item_name)
                    if r and data['tests'][item_name] is not None:
                        vv = data['tests'][item_name]
                        if vv < r[0] or vv > r[1]:
                            warnings.append(f'{item_name}: {vv}{r[2]} ({r[3]})')
                else:
                    data['tests'][item_name] = None
            
            # 如果填了身高体重但没填测试项目，给出提醒
            if data['height'] and data['weight'] and not any(v is not None for v in data['tests'].values()):
                if not messagebox.askyesno('提示', '未填写任何测试项目成绩，是否仍要保存？', parent=dialog):
                    return
            
            if warnings:
                warn_text = '以下数据可能异常:\n' + '\n'.join(warnings) + '\n\n是否仍要保存？'
                if not messagebox.askyesno('数据校验', warn_text, parent=dialog):
                    return
            
            # 计算全部得分
            apply_scores_to_student(data, grade)

            if mode == 'add':
                success, msg = self.dm.add_student(class_id, data)
            else:
                success, msg = self.dm.update_student(class_id, student_id, data)
            
            if success:
                dialog.destroy()
                self._refresh_student_table()
                self._update_status(msg)
            else:
                messagebox.showerror('错误', msg, parent=dialog)
        
        tk.Button(
            btn_frame, text='保存', command=save,
            bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 11, 'bold'),
            relief='flat', width=12, padx=10, pady=6
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_frame, text='取消', command=dialog.destroy,
            bg='#ccc', fg='#333', font=(TK_FONT, 11),
            relief='flat', width=12, padx=10, pady=6
        ).pack(side='left', padx=5)
    
    def _recalc_all_scores(self):
        """重新计算全部分数"""
        if not messagebox.askyesno('确认', '将重新计算所有学生的分数，确定吗？'):
            return
        
        all_classes = self.dm.get_all_classes()
        count = 0
        
        for cid, cdata in all_classes.items():
            grade = cdata.get('grade', 1)
            students = self.dm.get_students(cid)
            
            for s in students:
                apply_scores_to_student(s, grade)
                count += 1
            
            self.dm.import_students(cid, students)
        
        self._refresh_student_table()
        messagebox.showinfo('完成', f'已重新计算 {count} 名学生的分数')
    
    def _recalc_current(self):
        """重新计算当前选中学生分数"""
        sel = self.tree.selection()
        if not sel:
            return
        
        students = self.dm.get_students(self.current_class)
        for iid in sel:
            real_sid = self._iid_to_sid.get(iid, iid)
            for s in students:
                if s.get('id') == real_sid:
                    apply_scores_to_student(s, self.current_grade or 1)
        
        self.dm.import_students(self.current_class, students)
        self._refresh_student_table()
    
    def _recalc_imported(self, classes):
        """计算新导入班级中所有学生的分数"""
        for cid, cdata in classes.items():
            grade = cdata.get('grade', 1)
            students = cdata.get('students', [])
            
            for s in students:
                apply_scores_to_student(s, grade)
    
    def _show_test_rounds(self):
        """管理各班级测试轮次 — 支持单班操作和全校批量操作"""
        dialog = tk.Toplevel(self.window)
        dialog.title('测试轮次管理')
        dialog.geometry('750x560')
        dialog.resizable(True, True)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 750, 560)
        
        tk.Label(dialog, text='各班级测试轮次', font=(TK_FONT, 13, 'bold'),
                 bg=COLOR_PRIMARY, fg='white', pady=10).pack(fill='x')
        
        tree_frame = tk.Frame(dialog)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        cols = ('年级', '班级', '轮次', '当前')
        col_widths = (100, 160, 60, 60)
        
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c, anchor='center')
            tree.column(c, width=w, anchor='center', minwidth=60)
        
        vsb = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        iid_to_cid = {}
        all_cids = []
        for cid, cdata in sorted(self.dm.get_all_classes().items()):
            grade = cdata.get('grade', 1)
            name = cdata.get('name', cid)
            rounds = self.dm.get_test_rounds(cid)
            current = cdata.get('current_round', 0)
            iid = tree.insert('', tk.END, values=(
                GRADE_NAMES[grade-1] if 1 <= grade <= 6 else str(grade),
                name,
                str(len(rounds)),
                str(current + 1)
            ))
            iid_to_cid[iid] = cid
            all_cids.append(cid)
        
        def _refresh_table():
            for item in tree.get_children():
                tree.delete(item)
            iid_to_cid.clear()
            for cid, cdata in sorted(self.dm.get_all_classes().items()):
                grade = cdata.get('grade', 1)
                name = cdata.get('name', cid)
                rounds = self.dm.get_test_rounds(cid)
                current = cdata.get('current_round', 0)
                iid = tree.insert('', tk.END, values=(
                    GRADE_NAMES[grade-1] if 1 <= grade <= 6 else str(grade),
                    name, str(len(rounds)), str(current + 1)
                ))
                iid_to_cid[iid] = cid
        
        # ===== 全校批量操作按钮行 =====
        batch_frame = tk.Frame(dialog, bg=COLOR_BG_HEADER, relief='solid', bd=1)
        batch_frame.pack(fill='x', padx=8, pady=(0, 2))
        tk.Label(batch_frame, text='全校批量:', font=(TK_FONT, 10, 'bold'),
                 bg=COLOR_BG_HEADER, fg=COLOR_PRIMARY).pack(side='left', padx=(10, 6), pady=6)
        
        def _batch_add_round():
            if not messagebox.askyesno('确认', f'将为全部 {len(all_cids)} 个班级各新增一个测试轮次，确定吗？'):
                return
            count = 0
            for cid in all_cids:
                ok, _ = self.dm.add_test_round(cid)
                if ok:
                    count += 1
            _refresh_table()
            self._refresh_student_table()
            messagebox.showinfo('完成', f'已为 {count} 个班级新增测试轮次')
        
        def _batch_delete_round():
            # 找到所有班级中最小的轮次数
            min_rounds = min(len(self.dm.get_test_rounds(cid)) for cid in all_cids) if all_cids else 0
            if min_rounds <= 1:
                messagebox.showwarning('提示', '有班级仅剩1个轮次，无法批量删除')
                return
            ridx = simpledialog.askinteger('删除轮次',
                f'各班级当前轮次数不同。\n要删除第几个轮次？(1-{min_rounds})',
                minvalue=1, maxvalue=min_rounds)
            if not ridx:
                return
            if not messagebox.askyesno('确认', f'将为全部班级删除第 {ridx} 个测试轮次，确定吗？'):
                return
            count = 0
            for cid in all_cids:
                ok, _ = self.dm.delete_test_round(cid, ridx - 1)
                if ok:
                    count += 1
            _refresh_table()
            self._refresh_student_table()
            messagebox.showinfo('完成', f'已为 {count} 个班级删除第 {ridx} 个轮次')
        
        def _batch_switch_round():
            max_rounds = max(len(self.dm.get_test_rounds(cid)) for cid in all_cids) if all_cids else 1
            ridx = simpledialog.askinteger('切换轮次',
                f'各班级当前轮次数不同。\n要切换到第几个轮次？(1-{max_rounds})',
                minvalue=1, maxvalue=max_rounds)
            if not ridx:
                return
            if not messagebox.askyesno('确认', f'将全部班级切换到第 {ridx} 个测试轮次，确定吗？'):
                return
            count = 0
            for cid in all_cids:
                rounds = self.dm.get_test_rounds(cid)
                if ridx - 1 < len(rounds):
                    ok, _ = self.dm.set_current_test_round(cid, ridx - 1)
                else:
                    # 该班级没有这么多轮次，跳过
                    continue
                if ok:
                    count += 1
            _refresh_table()
            self._refresh_student_table()
            messagebox.showinfo('完成', f'已切换 {count} 个班级到第 {ridx} 个轮次')
        
        tk.Button(batch_frame, text='全部新增轮次', command=_batch_add_round,
                  bg=COLOR_SUCCESS, fg='white', font=(TK_FONT, 9),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(side='left', padx=3)
        tk.Button(batch_frame, text='全部删除轮次', command=_batch_delete_round,
                  bg=COLOR_DANGER, fg='white', font=(TK_FONT, 9),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(side='left', padx=3)
        tk.Button(batch_frame, text='全部切换轮次', command=_batch_switch_round,
                  bg=COLOR_WARNING, fg='white', font=(TK_FONT, 9),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(side='left', padx=3)
        tk.Button(batch_frame, text='关闭', command=dialog.destroy,
                  bg=COLOR_NEUTRAL, fg='white', font=(TK_FONT, 9),
                  relief='flat', padx=10, pady=4, cursor='hand2').pack(side='right', padx=8)
    
    def _recalc_class_scores(self):
        """重新计算当前班级的分数"""
        if not self.current_class:
            return
        if not messagebox.askyesno('确认', '将重新计算当前班级所有学生的分数，确定吗？'):
            return
        students = self.dm.get_students(self.current_class)
        count = 0
        for s in students:
            apply_scores_to_student(s, self.current_grade or 1)
            count += 1
        self.dm.import_students(self.current_class, students)
        self._refresh_student_table()
        self._update_status(f'已重新计算 {count} 名学生的分数')
    
    def _show_school_analysis(self):
        """全校综合分析：多维度数据展示"""
        show_school_analysis(self)

    def _build_bmi_by_grade_tab(self, notebook):
        _build_bmi_by_grade_tab(notebook, self)

    def _build_item_grade_distribution_tab(self, notebook):
        """构建各项目分年级等级分布标签页"""
        _build_item_grade_distribution_tab(notebook, self)

    def _add_test_comparison_tab(self, notebook, grade=None, title='测试对比'):
        """添加测试轮次对比标签页"""
        _build_test_comparison_table(notebook, self, grade=grade, title=title)

    def _show_grade_analysis(self, grade=None, show_selector=True):
        """年级综合分析"""
        show_grade_analysis(self, grade=grade, show_selector=show_selector)
    
    def _show_help(self):
        messagebox.showinfo('使用说明',
            '诸葛镇中心小学 — 学生体质健康管理系统\n\n'
            '1. 选择年级 → 选择班级 → 查看学生数据\n'
            '2. 文件 → 导入Excel数据：导入模板格式的xlsx文件\n'
            '3. 文件 → 导出统计报告：导出分析报告\n'
            '4. 数据 → 添加/编辑/删除学生\n'
            '5. 统计 → 查看各类统计图表'
        )
    
    def _check_update(self):
        from updater import UpdateDialog
        UpdateDialog(self.window)

    def _show_about(self):
        messagebox.showinfo('关于',
            '诸葛镇中心小学 — 学生体质健康管理系统\n\n'
            f'版本: v{APP_VERSION}\n'
            f'仓库: {APP_REPO}\n'
            '标准: 《国家学生体质健康标准（2014修订版）》\n\n'
            '功能: 学生体测数据管理、自动评分、统计分析'
        )
    
    def run(self):
        """运行主窗口"""
        self.window.mainloop()
