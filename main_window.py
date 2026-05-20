"""主界面 — 年级Tabs + 班级管理 + 学生数据表格"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import re
import threading
import openpyxl
from config import (
    MAIN_WINDOW_SIZE, APP_TITLE, GRADE_NAMES, GRADE_ITEMS,
    STUDENT_COLUMNS, TK_FONT
)
from score_engine import apply_scores_to_student
from excel_io import import_from_excel, export_statistics_report
from charts import ChartBuilder
from utils import center_window


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
        self.file_menu.add_command(label='导出统计报告...', command=self._export_report, accelerator='Ctrl+E')
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
        self.data_menu.add_command(label='添加学生...', command=self._add_student)
        self.data_menu.add_command(label='编辑学生...', command=self._edit_student)
        self.data_menu.add_command(label='删除学生', command=self._delete_student)
        self.data_menu.add_separator()
        self.data_menu.add_command(label='重新计算全部分数', command=self._recalc_all_scores)
        
        # 统计菜单
        self.stats_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='统计', menu=self.stats_menu)
        self.stats_menu.add_command(label='班级统计', command=lambda: self._show_chart('班级'))
        self.stats_menu.add_command(label='年级统计', command=lambda: self._show_chart('年级'))
        self.stats_menu.add_command(label='全校统计', command=lambda: self._show_chart('全校'))
        self.stats_menu.add_command(label='年级趋势', command=lambda: self._show_chart('趋势'))
        self.stats_menu.add_command(label='项目分析', command=lambda: self._show_chart('雷达图'))
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='帮助', menu=help_menu)
        help_menu.add_command(label='使用说明', command=self._show_help)
        help_menu.add_command(label='关于', command=self._show_about)
        
        # 快捷键绑定
        self.window.bind('<Control-i>', lambda e: self._import_excel())
        self.window.bind('<Control-e>', lambda e: self._export_report())
        self.window.bind('<Control-q>', lambda e: self._on_close())
    
    # ========== 主界面布局 ==========
    def _build_ui(self):
        """构建主界面"""
        # 主容器
        main_paned = tk.PanedWindow(self.window, orient='horizontal', sashrelief='raised', sashwidth=4)
        main_paned.pack(fill='both', expand=True, padx=4, pady=4)
        
        # 左侧面板：年级+班级列表
        left_frame = tk.Frame(main_paned, width=220, bg='#f5f5f5')
        main_paned.add(left_frame, minsize=180)
        left_frame.pack_propagate(False)
        
        self._build_left_panel(left_frame)
        
        # 右侧面板：学生表格
        right_frame = tk.Frame(main_paned, bg='white')
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
            bg='#1976d2', fg='white', pady=8
        ).pack(fill='x')
        
        # 年级列表
        grade_frame = tk.Frame(parent, bg='#f5f5f5')
        grade_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.grade_listbox = tk.Listbox(
            grade_frame,
            font=(TK_FONT, 11),
            selectmode='single',
            activestyle='none',
            bg='white',
            relief='flat',
            highlightthickness=1,
            highlightcolor='#1976d2',
            selectbackground='#1976d2',
            selectforeground='white'
        )
        self.grade_listbox.pack(fill='both', expand=True, padx=4, pady=4)
        self.grade_listbox.bind('<<ListboxSelect>>', self._on_grade_select)
        self.grade_listbox.bind('<Button-3>', self._show_grade_context_menu)
        
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
            bg='#f5f5f5', anchor='w'
        ).pack(fill='x', padx=8, pady=(4, 2))
        
        # 班级列表
        class_frame = tk.Frame(parent, bg='#f5f5f5')
        class_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.class_listbox = tk.Listbox(
            class_frame,
            font=(TK_FONT, 10),
            selectmode='single',
            activestyle='none',
            bg='white',
            relief='flat',
            highlightthickness=1,
            highlightcolor='#1976d2',
            selectbackground='#1976d2',
            selectforeground='white'
        )
        self.class_listbox.pack(fill='both', expand=True, padx=4, pady=(4, 6))
        self.class_listbox.bind('<<ListboxSelect>>', self._on_class_select)
        self.class_listbox.bind('<Button-3>', self._show_class_context_menu)
        # 班级列表创建后刷新
        self._refresh_class_list()
    
    def _build_right_panel(self, parent):
        """构建右侧面板"""
        # 顶部工具栏
        toolbar = tk.Frame(parent, bg='#e3f2fd', height=40)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)
        
        # 班级标题
        self.class_title_label = tk.Label(
            toolbar, text='请选择年级和班级',
            font=(TK_FONT, 13, 'bold'),
            bg='#e3f2fd', fg='#1976d2'
        )
        self.class_title_label.pack(side='left', padx=15, pady=5)
        
        # 统计摘要
        self.stats_label = tk.Label(
            toolbar, text='',
            font=(TK_FONT, 10),
            bg='#e3f2fd', fg='#666'
        )
        self.stats_label.pack(side='right', padx=15)
        
        # 学生表格
        table_frame = tk.Frame(parent, bg='white')
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
        
        # 双击编辑
        self.tree.bind('<Double-1>', self._edit_student)
        
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
    
    def _show_context_menu(self, event):
        """显示学生表格右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def _show_grade_context_menu(self, event):
        """显示年级列表右键菜单"""
        idx = self.grade_listbox.nearest(event.y)
        if idx >= 0:
            self.grade_listbox.selection_clear(0, tk.END)
            self.grade_listbox.selection_set(idx)
            self._on_grade_select(None)
        grade_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        grade_name = GRADE_NAMES[idx] if idx < len(GRADE_NAMES) else '一年级'
        grade_menu.add_command(label=f'在"{grade_name}"添加班级...', command=lambda: self._add_class(grade_name))
        grade_menu.post(event.x_root, event.y_root)
    
    def _show_class_context_menu(self, event):
        """显示班级列表右键菜单"""
        idx = self.class_listbox.nearest(event.y)
        if idx >= 0:
            self.class_listbox.selection_clear(0, tk.END)
            self.class_listbox.selection_set(idx)
            self._on_class_select(None)
        class_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        if self.current_class:
            class_menu.add_command(label='📊 项目分析', command=self._show_class_analysis)
            class_menu.add_command(label='🗑 删除班级', command=self._delete_class)
        class_menu.post(event.x_root, event.y_root)
    
    def _show_class_analysis(self):
        """显示班级项目分析（单项+总成绩的等级占比）"""
        if not self.current_class:
            return
        class_data = self.dm.get_class(self.current_class)
        if not class_data:
            return
        students = class_data.get('students', [])
        if not students:
            messagebox.showinfo('提示', '该班级暂无学生数据')
            return
        
        class_name = class_data.get('name', self.current_class)
        grade_num = class_data.get('grade', 1)
        grade_name = GRADE_NAMES[grade_num - 1] if 1 <= grade_num <= 6 else str(grade_num)
        
        # 获取该年级的测试项目
        from config import GRADE_ITEMS
        items = GRADE_ITEMS.get(grade_num, [])
        
        # 等级判定函数
        def get_grade_level(score):
            if score is None or score == '':
                return None
            try:
                s = float(score)
            except (ValueError, TypeError):
                return None
            if s >= 90: return '优秀'
            elif s >= 80: return '良好'
            elif s >= 60: return '及格'
            else: return '不及格'
        
        def calc_stats(scores_or_key):
            """统计某项目(或总成绩)的等级分布, 返回 {等级: (人数, 百分比)}"""
            counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
            valid = 0
            for s in students:
                if callable(scores_or_key):
                    level = scores_or_key(s)
                else:
                    val = s.get('scores', {}).get(scores_or_key) if isinstance(scores_or_key, str) else s.get('total_score')
                    level = get_grade_level(val)
                if level:
                    counts[level] += 1
                    valid += 1
            return {k: (counts[k], f'{counts[k]/valid*100:.1f}%' if valid > 0 else '—') for k in counts}, valid
        
        # 弹窗
        dialog = tk.Toplevel(self.window)
        dialog.title(f'{class_name} — 项目分析')
        dialog.geometry('760x420')
        dialog.resizable(True, True)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 760, 420)
        
        # 标题
        header = tk.Frame(dialog, bg='#1976d2')
        header.pack(fill='x')
        tk.Label(header, text=f'{class_name} ({grade_name}) — 项目分析', 
                 font=(TK_FONT, 13, 'bold'), bg='#1976d2', fg='white', pady=10).pack()
        
        # 表格
        tree_frame = tk.Frame(dialog)
        tree_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        cols = ('项目', '总人数', '优秀', '优秀%', '良好', '良好%', '及格', '及格%', '不及格', '不及格%')
        col_widths = (120, 60, 55, 55, 55, 55, 55, 55, 55, 55)
        
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=len(items)+4)
        for c, w in zip(cols, col_widths):
            tree.heading(c, text=c, anchor='center')
            tree.column(c, width=w, anchor='center', minwidth=40)
        
        # 滚动条
        sb = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        
        # 填充单项数据
        for item in items:
            stats, valid = calc_stats(item)
            tree.insert('', tk.END, values=(
                item, valid,
                stats['优秀'][0], stats['优秀'][1],
                stats['良好'][0], stats['良好'][1],
                stats['及格'][0], stats['及格'][1],
                stats['不及格'][0], stats['不及格'][1],
            ))
        
        # 总成绩行
        total_stats, total_valid = calc_stats('total_score')
        tree.insert('', tk.END, values=(
            '📌 总成绩', total_valid,
            total_stats['优秀'][0], total_stats['优秀'][1],
            total_stats['良好'][0], total_stats['良好'][1],
            total_stats['及格'][0], total_stats['及格'][1],
            total_stats['不及格'][0], total_stats['不及格'][1],
        ), tags=('total',))
        tree.tag_configure('total', background='#e3f2fd', font=(TK_FONT, 10, 'bold'))
        
        # 关闭按钮
        tk.Button(dialog, text='关闭', command=dialog.destroy, width=12,
                  bg='#1976d2', fg='white', font=(TK_FONT, 10)).pack(pady=(0, 10))
    
    # ========== 事件处理 ==========
    def _on_grade_select(self, event):
        """年级选择事件"""
        sel = self.grade_listbox.curselection()
        if not sel:
            return
        self.current_grade = sel[0] + 1  # 1-indexed
        self._refresh_class_list()
    
    def _on_class_select(self, event):
        """班级选择事件"""
        sel = self.class_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        classes = self.dm.get_classes_by_grade(self.current_grade) if self.current_grade else {}
        class_ids = sorted(classes.keys())
        
        if idx < len(class_ids):
            self.current_class = class_ids[idx]
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
            self.stats_label.config(text='')
            self._update_status('未选择班级')
            return
        
        class_data = self.dm.get_class(self.current_class)
        if class_data is None:
            return
        
        self.class_title_label.config(text=f"{class_data.get('name', self.current_class)} — 学生列表")
        
        students = class_data.get('students', [])
        # 按总成绩降序排列
        students.sort(key=lambda s: s.get('total_score', 0) or 0, reverse=True)
        
        for idx, s in enumerate(students):
            self._insert_student_row(s, idx + 1)
        
        # 更新统计
        self._update_class_stats(students)
        self._update_status(f"当前班级: {class_data.get('name', '')} | 学生数: {len(students)}")
    
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
    
    def _format_run_time(self, val):
        """格式化折返跑时间"""
        if val is None or val == '':
            return ''
        try:
            v = float(val)
            if v >= 60:
                m = int(v // 60)
                s = int(v % 60)
                return f"{m}'{s:02d}"
            return str(v)
        except (ValueError, TypeError):
            return str(val)
    
    def _update_class_stats(self, students):
        """更新班级统计"""
        total = len(students)
        if total == 0:
            self.stats_label.config(text='')
            return
        
        counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
        for s in students:
            g = s.get('total_grade', '')
            if g and g in counts:
                counts[g] += 1
        
        self.stats_label.config(
            text=f"优秀:{counts['优秀']} 良好:{counts['良好']} 及格:{counts['及格']} 不及格:{counts['不及格']} | 共{total}人"
        )
    
    def _update_status(self, text):
        """更新状态栏"""
        self.status_bar.config(text=text)
    
    def _set_buttons_state(self, state):
        """设置所有操作按钮状态（normal/disabled），导入期间禁用防止重复点击"""
        for menu in (self.file_menu, self.data_menu, self.stats_menu):
            for idx in range(menu.index('end') + 1):
                try:
                    menu.entryconfigure(idx, state=state)
                except tk.TclError:
                    pass  # separator 不可改 state
        # add_class_btn 已移除，改用班级右键菜单
    
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
                if existing and existing.get('students'):
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
    
    def _change_password(self):
        """修改密码"""
        dialog = tk.Toplevel(self.window)
        dialog.title('修改密码')
        dialog.geometry('350x250')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        
        # 居中
        x = self.window.winfo_x() + (self.window.winfo_width() - 350) // 2
        y = self.window.winfo_y() + (self.window.winfo_height() - 250) // 2
        dialog.geometry(f'+{x}+{y}')
        
        frame = tk.Frame(dialog, bg='white')
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        tk.Label(frame, text='修改密码', font=(TK_FONT, 14, 'bold'), bg='white').pack(pady=(0, 20))
        
        tk.Label(frame, text='旧密码:', bg='white').pack(anchor='w')
        old_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        old_pw.pack(fill='x', ipady=4, pady=(2, 10))
        
        tk.Label(frame, text='新密码:', bg='white').pack(anchor='w')
        new_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        new_pw.pack(fill='x', ipady=4, pady=(2, 10))
        
        tk.Label(frame, text='确认密码:', bg='white').pack(anchor='w')
        confirm_pw = tk.Entry(frame, show='●', font=(TK_FONT, 10))
        confirm_pw.pack(fill='x', ipady=4, pady=(2, 15))
        
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
        
        tk.Button(
            frame, text='确认修改', command=do_change,
            bg='#1a73e8', fg='white', font=(TK_FONT, 10, 'bold'),
            relief='flat', padx=20, pady=6
        ).pack()
    
    def _add_class(self, default_grade_name=None):
        """添加班级"""
        from config import CN_TO_NUM
        
        # 防止重复打开对话框
        if self._add_class_dialog and self._add_class_dialog.winfo_exists():
            self._add_class_dialog.lift()
            self._add_class_dialog.focus_force()
            return
        
        dialog = tk.Toplevel(self.window)
        dialog.title('添加班级')
        dialog.geometry('340x350')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 340, 350)
        self._add_class_dialog = dialog
        dialog.protocol('WM_DELETE_WINDOW', lambda: (setattr(self, '_add_class_dialog', None), dialog.destroy()))
        # 任意方式关闭对话框时清除引用
        dialog.bind('<Destroy>', lambda e: setattr(self, '_add_class_dialog', None))
        
        frame = tk.Frame(dialog, bg='white')
        frame.pack(fill='both', expand=True, padx=20, pady=12)
        
        # 年级行
        grade_row = tk.Frame(frame, bg='white')
        grade_row.pack(fill='x', pady=3)
        tk.Label(grade_row, text='年级：', font=(TK_FONT, 11), bg='white', width=8, anchor='w').pack(side='left')
        default_grade = default_grade_name or GRADE_NAMES[0]
        grade_var = tk.StringVar(value=default_grade)
        grade_combo = ttk.Combobox(grade_row, textvariable=grade_var, values=GRADE_NAMES, state='readonly', width=18, font=(TK_FONT, 11))
        if default_grade_name and default_grade_name in GRADE_NAMES:
            grade_combo.current(GRADE_NAMES.index(default_grade_name))
        else:
            grade_combo.current(0)
        grade_combo.pack(side='left', fill='x', expand=True)
        
        # 已有班级列表
        tk.Label(frame, text='已有班级：', font=(TK_FONT, 11), bg='white', fg='#555', anchor='w').pack(fill='x', pady=(10, 2))
        
        existing_frame = tk.Frame(frame, bg='#f5f5f5', relief='solid', bd=1)
        existing_frame.pack(fill='x', pady=(0, 8))
        existing_label = tk.Label(
            existing_frame, text='', font=(TK_FONT, 9), bg='#f5f5f5', fg='#666',
            justify='left', anchor='w', wraplength=320
        )
        existing_label.pack(fill='x', padx=8, pady=6)
        
        # 班级编号行
        id_row = tk.Frame(frame, bg='white')
        id_row.pack(fill='x', pady=3)
        tk.Label(id_row, text='班级编号：', font=(TK_FONT, 11), bg='white', width=8, anchor='w').pack(side='left')
        class_id_entry = tk.Entry(id_row, font=(TK_FONT, 11), width=18)
        class_id_entry.pack(side='left', fill='x', expand=True, ipady=4)
        class_id_entry.bind('<Return>', lambda e: do_add())
        
        tk.Label(frame, text='例: 101=一(1)班, 502=五(2)班', font=(TK_FONT, 8), bg='white', fg='#999').pack(anchor='w', pady=(2, 6))
        
        # 年级切换时：刷新已有班级列表 + 自动更新默认编号
        def _refresh_existing():
            grade_name = grade_var.get()
            grade_num = CN_TO_NUM.get(grade_name[0], 0)
            if grade_num:
                all_classes = self.dm.get_classes_by_grade(grade_num)
                if all_classes:
                    items = [f'{cid}' for cid in sorted(all_classes.keys())]
                    existing_label.config(text='  '.join(items), fg='#333')
                else:
                    existing_label.config(text='（暂无班级）', fg='#999')
                # 自动设置默认编号: 1年级→101, 6年级→601
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
        btn_row = tk.Frame(frame, bg='white')
        btn_row.pack(fill='x', pady=(6, 0))
        tk.Button(
            btn_row, text='✓ 确认添加', command=do_add,
            bg='#1a73e8', fg='white', font=(TK_FONT, 11, 'bold'),
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
        self._student_dialog(mode='edit', student_id=student_id)
    
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
    
    def _student_dialog(self, mode='add', student_id=None):
        """学生编辑对话框"""
        dialog = tk.Toplevel(self.window)
        dialog.title('添加学生' if mode == 'add' else '编辑学生')
        dialog.geometry('500x650')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        center_window(dialog, 500, 650)
        
        # 已存在的学生数据
        student_data = {}
        if mode == 'edit' and student_id:
            students = self.dm.get_students(self.current_class)
            for s in students:
                if s.get('id') == student_id:
                    student_data = s
                    break
        
        # 可滚动内容
        canvas = tk.Canvas(dialog, bg='white', highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg='white')
        
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 表单字段
        padx = 30
        pady_frame = 15
        
        def add_field(label, key, row, default='', entry_type='text'):
            tk.Label(scroll_frame, text=label, bg='white', font=(TK_FONT, 10), anchor='w').grid(
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
        v_height = add_field('身高(cm):', 'height', row, student_data.get('height', ''))
        row += 1
        v_weight = add_field('体重(kg):', 'weight', row, student_data.get('weight', ''))
        row += 1
        
        # 分隔线
        ttk.Separator(scroll_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', padx=padx, pady=10)
        row += 1
        
        tk.Label(scroll_frame, text='测试项目成绩', font=(TK_FONT, 11, 'bold'), bg='white', fg='#555').grid(
            row=row, column=0, columnspan=2, pady=(5, 5))
        row += 1
        
        # 测试项目
        tests = student_data.get('tests', {})
        grade = self.current_grade or 1
        items = GRADE_ITEMS.get(grade, [])
        test_vars = {}
        for item_name in items:
            label = item_name
            if item_name == '50*8折返跑':
                label += '(秒)'
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
        btn_frame = tk.Frame(scroll_frame, bg='white')
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(20, 15))
        
        def save():
            # 收集数据
            data = {
                'student_number': v_student_number.get(),
                'name': v_name.get(),
                'student_code': v_student_code.get(),
                'gender': v_gender.get(),
                'height': None,
                'weight': None,
                'tests': {}
            }
            
            # 身高体重
            h = v_height.get().strip()
            if h:
                try:
                    data['height'] = float(h)
                except ValueError:
                    messagebox.showwarning('提示', f'身高格式不正确: {h}', parent=dialog)
                    return
            
            w = v_weight.get().strip()
            if w:
                try:
                    data['weight'] = float(w)
                except ValueError:
                    messagebox.showwarning('提示', f'体重格式不正确: {w}', parent=dialog)
                    return
            
            # 测试项目
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
                else:
                    data['tests'][item_name] = None
            
            # 计算全部得分
            apply_scores_to_student(data, self.current_grade or 1)
            
            if mode == 'add':
                success, msg = self.dm.add_student(self.current_class, data)
            else:
                success, msg = self.dm.update_student(self.current_class, student_id, data)
            
            if success:
                dialog.destroy()
                self._refresh_student_table()
                self._update_status(msg)
            else:
                messagebox.showerror('错误', msg, parent=dialog)
        
        tk.Button(
            btn_frame, text='保存', command=save,
            bg='#1a73e8', fg='white', font=(TK_FONT, 11, 'bold'),
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
            students = cdata.get('students', [])
            
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
    
    # ========== 统计图表 ==========
    def _show_chart(self, chart_type):
        """显示统计图表"""
        dialog = tk.Toplevel(self.window)
        dialog.title(f"统计分析 - {chart_type}")
        dialog.geometry('800x600')
        dialog.resizable(True, True)
        dialog.transient(self.window)
        center_window(dialog, 800, 600)
        
        frame = tk.Frame(dialog, bg='white')
        frame.pack(fill='both', expand=True)
        
        try:
            if chart_type == '班级':
                self._show_class_bar_chart(frame)
            elif chart_type == '年级':
                self._show_grade_pie_chart(frame)
            elif chart_type == '全校':
                self._show_school_pie_chart(frame)
            elif chart_type == '趋势':
                self._show_grade_trend_chart(frame)
            elif chart_type == '雷达图':
                self._show_radar_chart(frame)
        except Exception as e:
            tk.Label(frame, text=f'图表生成失败: {e}', bg='white', font=(TK_FONT, 11)).pack(expand=True)
    
    def _show_class_bar_chart(self, parent):
        """班级统计柱状图"""
        if not self.current_grade:
            tk.Label(parent, text='请先选择年级', bg='white').pack(expand=True)
            return
        
        classes = self.dm.get_classes_by_grade(self.current_grade)
        if not classes:
            tk.Label(parent, text='该年级暂无班级数据', bg='white').pack(expand=True)
            return
        
        stats_list = []
        for cid in sorted(classes.keys()):
            cdata = classes[cid]
            students = cdata.get('students', [])
            counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
            for s in students:
                g = s.get('total_grade', '')
                if g in counts:
                    counts[g] += 1
            stats_list.append((cdata.get('name', cid), counts))
        
        canvas = ChartBuilder.create_bar_chart(parent, stats_list, 
            title=f'{GRADE_NAMES[self.current_grade-1]}各班等级分布')
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas.draw()
    
    def _show_grade_pie_chart(self, parent):
        """年级统计饼图"""
        if not self.current_grade:
            tk.Label(parent, text='请先选择年级', bg='white').pack(expand=True)
            return
        
        stats = self.dm.get_statistics(grade=self.current_grade)
        canvas = ChartBuilder.create_pie_chart(parent, stats, 
            title=f'{GRADE_NAMES[self.current_grade-1]}等级占比')
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas.draw()
    
    def _show_school_pie_chart(self, parent):
        """全校统计饼图"""
        stats = self.dm.get_statistics()
        canvas = ChartBuilder.create_pie_chart(parent, stats, title='全校等级占比')
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas.draw()
    
    def _show_grade_trend_chart(self, parent):
        """年级平均分趋势"""
        scores = {}
        for g in range(1, 7):
            stats = self.dm.get_statistics(grade=g)
            if stats['total'] > 0:
                scores[GRADE_NAMES[g-1]] = stats['avg_score']
        
        if not scores:
            tk.Label(parent, text='暂无数据', bg='white').pack(expand=True)
            return
        
        canvas = ChartBuilder.create_line_chart(parent, scores, title='各年级平均分趋势')
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas.draw()
    
    def _show_radar_chart(self, parent):
        """雷达图分析"""
        if not self.current_grade:
            tk.Label(parent, text='请先选择年级', bg='white').pack(expand=True)
            return
        
        grade = self.current_grade
        items = GRADE_ITEMS.get(grade, [])
        
        # 计算各项目平均得分
        all_classes = self.dm.get_classes_by_grade(grade)
        item_scores = {item: [] for item in items}
        
        for cid, cdata in all_classes.items():
            for s in cdata.get('students', []):
                scores = s.get('scores', {})
                for item in items:
                    sc = scores.get(item, 0) or 0
                    if sc > 0:
                        item_scores[item].append(sc)
        
        avg_scores = {}
        for item in items:
            vals = item_scores[item]
            avg_scores[item] = round(sum(vals) / len(vals), 1) if vals else 0
        
        if not any(v > 0 for v in avg_scores.values()):
            tk.Label(parent, text='暂无评分数据', bg='white').pack(expand=True)
            return
        
        canvas = ChartBuilder.create_radar_chart(parent, avg_scores, 
            title=f'{GRADE_NAMES[grade-1]}各项目平均得分')
        canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas.draw()
    
    # ========== 帮助 ==========
    def _show_help(self):
        messagebox.showinfo('使用说明',
            '诸葛镇中心小学 — 学生体质健康管理系统\n\n'
            '1. 选择年级 → 选择班级 → 查看学生数据\n'
            '2. 文件 → 导入Excel数据：导入模板格式的xlsx文件\n'
            '3. 文件 → 导出统计报告：导出分析报告\n'
            '4. 数据 → 添加/编辑/删除学生\n'
            '5. 统计 → 查看各类统计图表\n'
            '6. 双击学生行可快速编辑'
        )
    
    def _show_about(self):
        messagebox.showinfo('关于',
            '诸葛镇中心小学 — 学生体质健康管理系统\n\n'
            '版本: v1.0\n'
            '标准: 《国家学生体质健康标准（2014修订版）》\n\n'
            '功能: 学生体测数据管理、自动评分、统计分析'
        )
    
    def run(self):
        """运行主窗口"""
        self.window.mainloop()
