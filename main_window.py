"""主界面 — 年级Tabs + 班级管理 + 学生数据表格"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
from config import (
    MAIN_WINDOW_SIZE, APP_TITLE, GRADE_NAMES, GRADE_ITEMS,
    STUDENT_COLUMNS, TK_FONT
)
from score_engine import calc_bmi_score, calc_total_score
from excel_io import import_from_excel, export_statistics_report
from charts import ChartBuilder


class MainWindow:
    """主界面窗口"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
        
        self.window = tk.Tk()
        self.window.title(APP_TITLE)
        
        w, h = MAIN_WINDOW_SIZE
        self._center_window(self.window, w, h)
        self.window.minsize(900, 500)
        
        self.current_grade = 1  # 当前选中的年级（默认一年级）
        self.current_class = None  # 当前选中的班级
        
        # 缓存学生数据
        self._student_cache = {}
        
        self._build_menu()
        self._build_ui()
        self._setup_close_handler()
    
    def _center_window(self, win, width, height):
        """窗口居中"""
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")
    
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
        file_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='文件', menu=file_menu)
        file_menu.add_command(label='导入Excel数据...', command=self._import_excel, accelerator='Ctrl+I')
        file_menu.add_command(label='导出统计报告...', command=self._export_report, accelerator='Ctrl+E')
        file_menu.add_separator()
        file_menu.add_command(label='修改密码...', command=self._change_password)
        file_menu.add_separator()
        file_menu.add_command(label='退出', command=self._on_close, accelerator='Ctrl+Q')
        
        # 数据菜单
        data_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='数据', menu=data_menu)
        data_menu.add_command(label='添加班级...', command=self._add_class)
        data_menu.add_command(label='删除班级', command=self._delete_class)
        data_menu.add_separator()
        data_menu.add_command(label='添加学生...', command=self._add_student)
        data_menu.add_command(label='编辑学生...', command=self._edit_student)
        data_menu.add_command(label='删除学生', command=self._delete_student)
        data_menu.add_separator()
        data_menu.add_command(label='重新计算全部分数', command=self._recalc_all_scores)
        
        # 统计菜单
        stats_menu = tk.Menu(menubar, tearoff=0, font=(TK_FONT, 10))
        menubar.add_cascade(label='统计', menu=stats_menu)
        stats_menu.add_command(label='班级统计', command=lambda: self._show_chart('班级'))
        stats_menu.add_command(label='年级统计', command=lambda: self._show_chart('年级'))
        stats_menu.add_command(label='全校统计', command=lambda: self._show_chart('全校'))
        stats_menu.add_command(label='年级趋势', command=lambda: self._show_chart('趋势'))
        stats_menu.add_command(label='项目分析', command=lambda: self._show_chart('雷达图'))
        
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
        
        for i, gname in enumerate(GRADE_NAMES):
            self.grade_listbox.insert(tk.END, f"  {gname}")
        
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
        self.class_listbox.pack(fill='both', expand=True, padx=4, pady=4)
        self.class_listbox.bind('<<ListboxSelect>>', self._on_class_select)
    
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
        """右键菜单"""
        self.context_menu = tk.Menu(self.window, tearoff=0, font=(TK_FONT, 10))
        self.context_menu.add_command(label='编辑学生', command=self._edit_student)
        self.context_menu.add_command(label='删除学生', command=self._delete_student)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='重新计算分数', command=self._recalc_current)
        
        self.tree.bind('<Button-3>', self._show_context_menu)
    
    def _show_context_menu(self, event):
        """显示右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
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
        # 清空
        for item in self.tree.get_children():
            self.tree.delete(item)
        
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
        
        for s in students:
            self._insert_student_row(s)
        
        # 更新统计
        self._update_class_stats(students)
        self._update_status(f"当前班级: {class_data.get('name', '')} | 学生数: {len(students)}")
    
    def _insert_student_row(self, student):
        """插入学生行"""
        tests = student.get('tests', {})
        scores = student.get('scores', {})
        
        values = [
            self.current_class or '',
            student.get('student_number', ''),
            student.get('name', ''),
            student.get('student_code', ''),
            student.get('gender', ''),
            student.get('height', ''),
            student.get('weight', ''),
            student.get('bmi', ''),
            student.get('bmi_grade', ''),
            student.get('bmi_score', ''),
            tests.get('肺活量', ''),
            tests.get('50米跑', ''),
            tests.get('坐位体前屈', ''),
            tests.get('一分钟跳绳', ''),
            tests.get('仰卧起坐', ''),
            self._format_run_time(tests.get('50*8折返跑')),
            student.get('total_score', ''),
            student.get('total_grade', '')
        ]
        
        # 根据等级设置行颜色
        grade_level = student.get('total_grade', '')
        tags = []
        if grade_level == '优秀':
            tags.append('excellent')
        elif grade_level == '不及格':
            tags.append('fail')
        
        self.tree.insert('', tk.END, values=values, tags=tags, iid=student.get('id', ''))
        
        # 配置 tag 颜色
        self.tree.tag_configure('excellent', background='#e8f5e9')
        self.tree.tag_configure('fail', background='#ffebee')
    
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
    
    # ========== 菜单命令 ==========
    def _import_excel(self):
        """导入Excel数据"""
        filepath = filedialog.askopenfilename(
            title='选择Excel文件',
            filetypes=[('Excel文件', '*.xlsx *.xls'), ('所有文件', '*.*')]
        )
        if not filepath:
            return
        
        self._update_status('正在导入...')
        self.window.update()
        
        result = import_from_excel(filepath)
        
        if result['success']:
            # 合并导入的数据
            classes = result['data'].get('classes', {})
            for cid, cdata in classes.items():
                # 如果班级已存在，询问是否覆盖
                existing = self.dm.get_class(cid)
                if existing and existing.get('students'):
                    if messagebox.askyesno('确认', f"班级 {cdata.get('name', cid)} 已有数据，是否覆盖？"):
                        self.dm.import_students(cid, cdata.get('students', []))
                else:
                    # 确保班级存在
                    if not existing:
                        self.dm.add_class(cid, cdata.get('grade', 1), cdata.get('name', f'班级{cid}'))
                    self.dm.import_students(cid, cdata.get('students', []))
            
            messagebox.showinfo('导入完成', result['message'])
            self._refresh_class_list()
            if self.current_class:
                self._refresh_student_table()
        else:
            messagebox.showerror('导入失败', result['message'])
        
        self._update_status('就绪')
    
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
    
    def _add_class(self):
        """添加班级"""
        dialog = tk.Toplevel(self.window)
        dialog.title('添加班级')
        dialog.geometry('300x200')
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        self._center_window(dialog, 300, 200)
        
        frame = tk.Frame(dialog, bg='white')
        frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        tk.Label(frame, text='添加班级', font=(TK_FONT, 13, 'bold'), bg='white').pack(pady=(0, 15))
        
        tk.Label(frame, text='年级:', bg='white').pack(anchor='w')
        grade_var = tk.StringVar(value='一年级')
        grade_combo = ttk.Combobox(frame, textvariable=grade_var, values=GRADE_NAMES, state='readonly')
        grade_combo.pack(fill='x', pady=(2, 10))
        
        tk.Label(frame, text='班级编号 (如101):', bg='white').pack(anchor='w')
        class_id_entry = tk.Entry(frame)
        class_id_entry.pack(fill='x', ipady=4, pady=(2, 10))
        
        def do_add():
            grade_name = grade_var.get()
            cid = class_id_entry.get().strip()
            if not cid:
                messagebox.showwarning('提示', '请输入班级编号', parent=dialog)
                return
            
            from config import CN_TO_NUM
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
        
        tk.Button(
            frame, text='添加', command=do_add,
            bg='#1a73e8', fg='white', font=(TK_FONT, 10, 'bold'),
            relief='flat', padx=20, pady=6
        ).pack()
    
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
        student_id = sel[0]
        self._student_dialog(mode='edit', student_id=student_id)
    
    def _delete_student(self):
        """删除学生"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('提示', '请先选择学生')
            return
        
        if messagebox.askyesno('确认删除', '确定要删除该学生吗？'):
            for sid in sel:
                self.dm.delete_student(self.current_class, sid)
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
        self._center_window(dialog, 500, 650)
        
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
        tk.Label(scroll_frame, text='添加学生' if mode == 'add' else '编辑学生', 
                font=(TK_FONT, 14, 'bold'), bg='white', fg='#1976d2').grid(
            row=row, column=0, columnspan=2, pady=(15, 10))
        row += 1
        
        # 基本信息
        v_student_number = add_field('学号:', 'student_number', row, student_data.get('student_number', ''))
        row += 1
        v_name = add_field('姓名:', 'name', row, student_data.get('name', ''))
        row += 1
        v_student_code = add_field('学籍号:', 'student_code', row, student_data.get('student_code', ''))
        row += 1
        v_gender = add_field('性别:', 'gender', row, student_data.get('gender', '男'))
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
                except:
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
                        import re
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
            
            # 计算BMI和评分
            if data['height'] and data['weight']:
                bmi, bmi_grade, bmi_score = calc_bmi_score(
                    data['height'], data['weight'], data['gender'], self.current_grade or 1
                )
                data['bmi'] = bmi
                data['bmi_grade'] = bmi_grade
                data['bmi_score'] = bmi_score
            
            # 计算总分
            score_result = calc_total_score(data, self.current_grade or 1)
            data['scores'] = score_result.get('item_scores', {})
            data['total_score'] = score_result.get('total_score', 0)
            data['total_grade'] = score_result.get('total_grade', '')
            
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
                score_result = calc_total_score(s, grade)
                h = s.get('height')
                w = s.get('weight')
                if h and w:
                    s['bmi'], s['bmi_grade'], s['bmi_score'] = calc_bmi_score(h, w, s.get('gender', '男'), grade)
                else:
                    s['bmi'], s['bmi_grade'], s['bmi_score'] = (None, '', 0)
                s['scores'] = score_result.get('item_scores', {})
                s['total_score'] = score_result.get('total_score', 0)
                s['total_grade'] = score_result.get('total_grade', '')
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
        for sid in sel:
            for s in students:
                if s.get('id') == sid:
                    grade = self.current_grade or 1
                    score_result = calc_total_score(s, grade)
                    h = s.get('height')
                    w = s.get('weight')
                    if h and w:
                        s['bmi'], s['bmi_grade'], s['bmi_score'] = calc_bmi_score(h, w, s.get('gender', '男'), grade)
                    else:
                        s['bmi'], s['bmi_grade'], s['bmi_score'] = (None, '', 0)
                    s['scores'] = score_result.get('item_scores', {})
                    s['total_score'] = score_result.get('total_score', 0)
                    s['total_grade'] = score_result.get('total_grade', '')
        
        self.dm.import_students(self.current_class, students)
        self._refresh_student_table()
    
    # ========== 统计图表 ==========
    def _show_chart(self, chart_type):
        """显示统计图表"""
        dialog = tk.Toplevel(self.window)
        dialog.title(f"统计分析 - {chart_type}")
        dialog.geometry('800x600')
        dialog.resizable(True, True)
        dialog.transient(self.window)
        self._center_window(dialog, 800, 600)
        
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
