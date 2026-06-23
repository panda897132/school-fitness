"""分析对话框 — 从 MainWindow 拆分出的独立模块"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import (
    GRADE_NAMES, GRADE_ITEMS, TK_FONT, NUM_TO_CN,
    COLOR_PRIMARY, COLOR_PRIMARY_DARK, COLOR_ACCENT,
    COLOR_BG_LIGHT, COLOR_BG_WHITE, COLOR_BG_HEADER,
    COLOR_TEXT_LIGHT, COLOR_TEXT_MUTED,
)
from utils import center_window, get_grade_level, calc_item_stats, compute_grade_distribution
from charts import ChartBuilder
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def _get_students_for_round(all_classes, round_index):
    """获取某轮次所有班级的学生列表（共用辅助函数）"""
    students = []
    for cid, cdata in all_classes.items():
        rounds = cdata.get('test_rounds', [])
        if round_index < len(rounds):
            students.extend(rounds[round_index].get('students', []))
    return students


# ============================================================
#  班级分析
# ============================================================

def show_class_analysis(mw):
    """显示班级项目分析（单项+总成绩的等级占比）"""
    if not mw.current_class:
        return
    class_data = mw.dm.get_class(mw.current_class)
    if not class_data:
        return
    students = mw.dm.get_students(mw.current_class)
    if not students:
        messagebox.showinfo('提示', '该班级暂无学生数据')
        return

    class_name = class_data.get('name', mw.current_class)
    grade_num = class_data.get('grade', 1)
    grade_name = GRADE_NAMES[grade_num - 1] if 1 <= grade_num <= 6 else str(grade_num)
    items = GRADE_ITEMS.get(grade_num, [])

    dialog = tk.Toplevel(mw.window)
    dialog.title(f'{class_name} — 项目分析')
    dialog.geometry('760x420')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 760, 420)

    header = tk.Frame(dialog, bg=COLOR_PRIMARY)
    header.pack(fill='x')
    tk.Label(header, text=f'{class_name} ({grade_name}) — 项目分析',
             font=(TK_FONT, 13, 'bold'), bg=COLOR_PRIMARY, fg='white', pady=10).pack()

    tree_frame = tk.Frame(dialog)
    tree_frame.pack(fill='both', expand=True, padx=8, pady=8)

    cols = ('项目', '总人数', '优秀', '优秀%', '良好', '良好%', '及格', '及格%', '不及格', '不及格%')
    col_widths = (120, 60, 55, 55, 55, 55, 55, 55, 55, 55)

    tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=len(items) + 4)
    for c, w in zip(cols, col_widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=40)

    sb = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side='left', fill='both', expand=True)
    sb.pack(side='right', fill='y')

    for item in items:
        stats, valid = calc_item_stats(students, item)
        tree.insert('', tk.END, values=(
            item, valid,
            stats['优秀'][0], stats['优秀'][1],
            stats['良好'][0], stats['良好'][1],
            stats['及格'][0], stats['及格'][1],
            stats['不及格'][0], stats['不及格'][1],
        ))

    total_stats, total_valid = calc_item_stats(students, 'total_score')
    tree.insert('', tk.END, values=(
        '📌 总成绩', total_valid,
        total_stats['优秀'][0], total_stats['优秀'][1],
        total_stats['良好'][0], total_stats['良好'][1],
        total_stats['及格'][0], total_stats['及格'][1],
        total_stats['不及格'][0], total_stats['不及格'][1],
    ), tags=('total',))
    tree.tag_configure('total', background='#e3f2fd', font=(TK_FONT, 10, 'bold'))

    tk.Button(dialog, text='关闭', command=dialog.destroy, width=12,
              bg=COLOR_PRIMARY, fg='white', font=(TK_FONT, 10)).pack(pady=(0, 10))


def show_class_full_analysis(mw):
    """班级综合分析（图表+数据）"""
    if not mw.current_class:
        return
    class_data = mw.dm.get_class(mw.current_class)
    if not class_data:
        return
    students = mw.dm.get_students(mw.current_class)
    if not students:
        messagebox.showinfo('提示', '该班级暂无学生数据')
        return

    class_name = class_data.get('name', mw.current_class)
    grade_num = class_data.get('grade', 1)
    grade_name = GRADE_NAMES[grade_num - 1] if 1 <= grade_num <= 6 else str(grade_num)
    items = GRADE_ITEMS.get(grade_num, [])

    total = len(students)
    dist = compute_grade_distribution(students)
    counts = dist['counts']
    avg = dist['avg_score']
    pass_count = dist['pass_count']

    d_stats = {
        'total': total,
        '优秀': counts['优秀'], '良好': counts['良好'],
        '及格': counts['及格'], '不及格': counts['不及格'],
        '优秀率': round(counts['优秀'] / total * 100, 1) if total else 0,
        '良好率': round(counts['良好'] / total * 100, 1) if total else 0,
        '及格率': round(pass_count / total * 100, 1) if total else 0,
        '不及格率': round(counts['不及格'] / total * 100, 1) if total else 0,
        'avg_score': avg,
    }

    if mw._class_analysis_dialog and mw._class_analysis_dialog.winfo_exists():
        mw._class_analysis_dialog.lift()
        mw._class_analysis_dialog.focus_force()
        return

    dialog = tk.Toplevel(mw.window)
    dialog.title(f'班级分析 - {class_name}')
    dialog.geometry('900x700')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 900, 700)
    mw._class_analysis_dialog = dialog
    dialog.protocol('WM_DELETE_WINDOW', lambda: (setattr(mw, '_class_analysis_dialog', None), dialog.destroy()))
    dialog.bind('<Destroy>', lambda e: setattr(mw, '_class_analysis_dialog', None))

    notebook = ttk.Notebook(dialog)
    notebook.pack(fill='both', expand=True, padx=5, pady=5)

    # ---- Tab 1: 概览 ----
    overview_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(overview_frame, text='概览')

    summary_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
    summary_frame.pack(fill='x', padx=20, pady=15)

    tk.Label(summary_frame, text=f'{class_name} ({grade_name}) — 综合数据概览',
             font=(TK_FONT, 14, 'bold'), bg=COLOR_BG_WHITE, fg=COLOR_PRIMARY).pack(anchor='w')

    stats_text = (
        f"学生总数：{total}人\n"
        f"优良率：{d_stats['优秀率'] + d_stats['良好率']}%\n"
        f"及格率：{d_stats['及格率']}%\n"
        f"优秀率：{d_stats['优秀率']}%  |  良好率：{d_stats['良好率']}%  |  不及格率：{d_stats['不及格率']}%\n"
        f"优秀：{counts['优秀']}人  |  良好：{counts['良好']}人  |  及格：{counts['及格']}人  |  不及格：{counts['不及格']}人"
    )
    tk.Label(summary_frame, text=stats_text, font=(TK_FONT, 11), bg=COLOR_BG_WHITE,
             justify='left', anchor='w').pack(anchor='w', pady=(8, 0))

    chart_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
    chart_frame.pack(fill='both', expand=True, padx=20, pady=10)
    canvas1 = ChartBuilder.create_pie_chart(chart_frame, d_stats, title=f'{class_name}等级分布')
    canvas1.get_tk_widget().pack(fill='both', expand=True)
    canvas1.draw()

    # ---- Tab 2: 各项目得分 ----
    score_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(score_frame, text='各项目得分')

    item_excel = {}
    for item in items:
        total_cnt = 0
        exc_cnt = 0
        for s in students:
            sc = s.get('scores', {}).get(item, 0) or 0
            if sc > 0:
                total_cnt += 1
                if sc >= 80:
                    exc_cnt += 1
        item_excel[item] = round(exc_cnt / total_cnt * 100, 1) if total_cnt else 0

    if not any(v > 0 for v in item_excel.values()):
        tk.Label(score_frame, text='暂无评分数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
    else:
        canvas2 = ChartBuilder.create_radar_chart(score_frame, item_excel, title=f'{class_name}各项目优良率')
        canvas2.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas2.draw()

    # ---- Tab 3: 项目分班级 ----
    project_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(project_frame, text='项目分班级')

    tree_frame = tk.Frame(project_frame, height=180)
    tree_frame.pack(fill='x', padx=8, pady=(8, 0))
    tree_frame.pack_propagate(False)

    cols = ('项目', '总人数', '优秀', '优秀%', '良好', '良好%', '及格', '及格%', '不及格', '不及格%')
    col_widths = (120, 60, 55, 55, 55, 55, 55, 55, 55, 55)

    tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=6)
    for c, w in zip(cols, col_widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=40)

    sb = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side='left', fill='x', expand=True)
    sb.pack(side='right', fill='y')

    for item in items:
        stats, valid = calc_item_stats(students, item)
        tree.insert('', tk.END, values=(
            item, valid,
            stats['优秀'][0], stats['优秀'][1],
            stats['良好'][0], stats['良好'][1],
            stats['及格'][0], stats['及格'][1],
            stats['不及格'][0], stats['不及格'][1],
        ))

    total_stats, total_valid = calc_item_stats(students, 'total_score')
    tree.insert('', tk.END, values=(
        '📌 总成绩', total_valid,
        total_stats['优秀'][0], total_stats['优秀'][1],
        total_stats['良好'][0], total_stats['良好'][1],
        total_stats['及格'][0], total_stats['及格'][1],
        total_stats['不及格'][0], total_stats['不及格'][1],
    ), tags=('total',))
    tree.tag_configure('total', background='#e3f2fd', font=(TK_FONT, 10, 'bold'))

    # 项目等级分布图
    chart_f = tk.Frame(project_frame, bg=COLOR_BG_WHITE)
    chart_f.pack(fill='both', expand=True, padx=8, pady=5)
    item_stats_list = []
    for item in items:
        stats, valid = calc_item_stats(students, item)
        item_stats_list.append((item, {
            '优秀': stats['优秀'][0], '良好': stats['良好'][0],
            '及格': stats['及格'][0], '不及格': stats['不及格'][0],
        }))
    if item_stats_list:
        c = ChartBuilder.create_bar_chart(chart_f, item_stats_list,
            title=f'{class_name}各项目等级分布')
        c.get_tk_widget().pack(fill='both', expand=True)
        c.draw()

    # ---- 导出按钮 ----
    btn_frame = tk.Frame(dialog, bg=COLOR_BG_LIGHT)
    btn_frame.pack(fill='x', side='bottom', padx=8, pady=6)

    def _export_class_data():
        from excel_io import export_statistics_report
        filepath = filedialog.asksaveasfilename(
            title='导出班级分析报告',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')],
            parent=dialog
        )
        if not filepath:
            return
        success, msg = export_statistics_report(mw.dm, filepath, scope='班级', class_id=mw.current_class)
        if success:
            messagebox.showinfo('导出成功', msg, parent=dialog)
        else:
            messagebox.showerror('导出失败', msg, parent=dialog)

    tk.Button(btn_frame, text='📤 导出数据', command=_export_class_data,
              bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 10, 'bold'),
              relief='flat', padx=15, pady=5, cursor='hand2').pack(side='right', padx=5)
    tk.Button(btn_frame, text='关闭', command=dialog.destroy,
              bg=COLOR_NEUTRAL, fg='white', font=(TK_FONT, 10),
              relief='flat', padx=15, pady=5, cursor='hand2').pack(side='right', padx=5)


# ============================================================
#  测试对比
# ============================================================

def _build_test_comparison_table(notebook, mw, grade=None, title='测试对比'):
    """构建测试轮次对比标签页（共用的内部函数）"""
    all_classes = mw.dm.get_all_classes()
    if grade:
        all_classes = {cid: cdata for cid, cdata in all_classes.items()
                      if cdata.get('grade') == grade}

    max_rounds = max((len(cdata.get('test_rounds', [])) for cdata in all_classes.values()), default=0)
    if max_rounds < 2:
        comp_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
        notebook.add(comp_frame, text='测试对比')
        tk.Label(comp_frame, text='暂无多次测试数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
        return

    comp_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(comp_frame, text='测试对比')

    round_stats = []
    for ri in range(max_rounds):
        students = []
        for cid, cdata in all_classes.items():
            rounds = cdata.get('test_rounds', [])
            if ri < len(rounds):
                students.extend(rounds[ri].get('students', []))

        total = len(students)
        dist = compute_grade_distribution(students)
        counts = dist['counts']
        pc = dist['pass_count']
        excel = round((counts['优秀'] + counts['良好']) / total * 100, 1) if total else 0
        round_stats.append({'round': ri + 1, 'total': total, 'excel': excel,
                           'pass_rate': round(pc / total * 100, 1) if total else 0, 'counts': counts})

    r_labels = [f"第{rs['round']}次" for rs in round_stats]

    tbl = tk.Frame(comp_frame, bg=COLOR_BG_WHITE)
    tbl.pack(fill='x', padx=10, pady=8)
    cols = ('轮次', '人数', '优良率', '及格率', '优秀', '良好', '及格', '不及格')
    widths = (55, 45, 60, 55, 45, 45, 45, 55)
    tree = ttk.Treeview(tbl, columns=cols, show='headings', height=len(round_stats) + 1)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=35)
    for rs in round_stats:
        tree.insert('', tk.END, values=(f"第{rs['round']}次", rs['total'], f"{rs['excel']}%",
                    f"{rs['pass_rate']}%", rs['counts']['优秀'], rs['counts']['良好'],
                    rs['counts']['及格'], rs['counts']['不及格']))
    tree.pack(fill='x')

    chart_frame = tk.Frame(comp_frame, bg=COLOR_BG_WHITE)
    chart_frame.pack(fill='both', expand=True, padx=10, pady=5)

    fig = Figure(figsize=(10, 4), dpi=100)
    ax1 = fig.add_subplot(121)
    r_avgs = [rs['excel'] for rs in round_stats]
    ax1.plot(r_labels, r_avgs, 'o-', color='#1976d2', linewidth=2, markersize=8)
    for i, v in enumerate(r_avgs):
        ax1.text(i, v + 0.5, str(v), ha='center', fontsize=9)
    ax1.set_title('优良率变化', fontsize=12, fontweight='bold')
    ax1.set_ylabel('优良率(%)')
    ax1.set_ylim(bottom=max(0, min(r_avgs) - 5), top=min(105, max(r_avgs) + 8))

    ax2 = fig.add_subplot(122)
    cats = ['优秀', '良好', '及格', '不及格']
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336']
    x = range(len(r_labels))
    bottom = [0] * len(r_labels)
    for cat, c in zip(cats, colors):
        vals = [rs['counts'][cat] for rs in round_stats]
        bars = ax2.bar(x, vals, bottom=bottom, label=cat, color=c, alpha=0.85)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                        str(val), ha='center', va='center', fontsize=9, fontweight='bold', color='white')
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax2.set_xticks(x)
    ax2.set_xticklabels(r_labels, fontsize=9)
    ax2.set_title('等级分布变化', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)
    fig.subplots_adjust(bottom=0.15, wspace=0.3)
    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    canvas.draw()


def show_test_comparison(mw):
    """多次测试数据对比"""
    if not mw.current_class:
        return
    rounds = mw.dm.get_test_rounds(mw.current_class)
    if len(rounds) < 2:
        messagebox.showinfo('提示', '该班级仅有1次测试数据，无法对比')
        return

    class_data = mw.dm.get_class(mw.current_class)
    class_name = class_data.get('name', mw.current_class)
    grade_num = class_data.get('grade', 1)

    round_stats = []
    for i, r in enumerate(rounds):
        students = r.get('students', [])
        total = len(students)
        dist = compute_grade_distribution(students)
        counts = dist['counts']
        pc = dist['pass_count']
        excel = round((counts['优秀'] + counts['良好']) / total * 100, 1) if total else 0
        round_stats.append({
            'round': i + 1, 'total': total, 'excel': excel,
            'pass_rate': round(pc / total * 100, 1) if total else 0,
            'counts': counts,
        })

    dialog = tk.Toplevel(mw.window)
    dialog.title(f'测试对比 - {class_name}')
    dialog.geometry('920x720')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 920, 720)

    notebook = ttk.Notebook(dialog)
    notebook.pack(fill='both', expand=True, padx=5, pady=5)

    items = GRADE_ITEMS.get(grade_num, [])

    # ---- Tab 1: 概览对比 ----
    ov = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(ov, text='概览对比')

    tbl_frame = tk.Frame(ov, bg=COLOR_BG_WHITE)
    tbl_frame.pack(fill='x', padx=15, pady=10)

    cols = ('轮次', '人数', '优良率', '及格率', '优秀', '良好', '及格', '不及格')
    widths = (60, 50, 70, 60, 50, 50, 50, 55)
    tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=len(round_stats) + 1)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=40)
    for rs in round_stats:
        tree.insert('', tk.END, values=(
            f"第{rs['round']}次", rs['total'], f"{rs['excel']}%", f"{rs['pass_rate']}%",
            rs['counts']['优秀'], rs['counts']['良好'],
            rs['counts']['及格'], rs['counts']['不及格']
        ))
    tree.pack(fill='x')

    chart_frame = tk.Frame(ov, bg=COLOR_BG_WHITE)
    chart_frame.pack(fill='both', expand=True, padx=15, pady=5)

    fig = Figure(figsize=(10, 4.5), dpi=100)
    r_labels = [f"第{rs['round']}次" for rs in round_stats]

    ax1 = fig.add_subplot(121)
    r_avgs = [rs['excel'] for rs in round_stats]
    ax1.plot(r_labels, r_avgs, 'o-', color='#1976d2', linewidth=2, markersize=8)
    for i, v in enumerate(r_avgs):
        ax1.text(i, v + 0.5, str(v), ha='center', fontsize=10)
    ax1.set_title('优良率变化', fontsize=13, fontweight='bold')
    ax1.set_ylabel('优良率(%)')
    ax1.set_ylim(bottom=max(0, min(r_avgs) - 5), top=min(105, max(r_avgs) + 8))

    ax2 = fig.add_subplot(122)
    cats = ['优秀', '良好', '及格', '不及格']
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336']
    x = range(len(r_labels))
    bottom = [0] * len(r_labels)
    for cat, color in zip(cats, colors):
        vals = [rs['counts'][cat] for rs in round_stats]
        bars = ax2.bar(x, vals, bottom=bottom, label=cat, color=color, alpha=0.85)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                        str(val), ha='center', va='center', fontsize=9, fontweight='bold', color='white')
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax2.set_xticks(x)
    ax2.set_xticklabels(r_labels, fontsize=9)
    ax2.set_title('等级分布变化', fontsize=13, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)
    fig.subplots_adjust(bottom=0.12, wspace=0.3)
    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    canvas.draw()

    # ---- Tab 2: 项目对比 ----
    item_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(item_frame, text='项目对比')

    item_data = {}
    for item in items:
        item_data[item] = []
        for r in rounds:
            total_cnt = 0
            exc_cnt = 0
            for s in r.get('students', []):
                sc = s.get('scores', {}).get(item, 0) or 0
                if sc > 0:
                    total_cnt += 1
                    if sc >= 80:
                        exc_cnt += 1
            item_data[item].append(round(exc_cnt / total_cnt * 100, 1) if total_cnt else 0)

    fig2 = Figure(figsize=(9, 5), dpi=100)
    ax3 = fig2.add_subplot(111)
    line_styles = ['o-', 's--', '^-.', 'd:', 'v-', 'p--', 'h-.', '8:']
    for j, item in enumerate(items):
        style = line_styles[j % len(line_styles)]
        ax3.plot(r_labels, item_data[item], style, linewidth=2, markersize=7, label=item)
        for i, v in enumerate(item_data[item]):
            ax3.text(i, v + 0.5, str(v), ha='center', fontsize=8)
    ax3.set_title('各项目优良率对比', fontsize=13, fontweight='bold')
    ax3.set_ylabel('优良率(%)')
    ax3.legend(loc='upper right', fontsize=8)
    ax3.grid(True, alpha=0.3)
    fig2.subplots_adjust(bottom=0.12)
    fig2.tight_layout()
    canvas2 = FigureCanvasTkAgg(fig2, master=item_frame)
    canvas2.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
    canvas2.draw()

    # ---- Tab 3: 学生对比 ----
    stu_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(stu_frame, text='学生对比')

    stu_map = {}
    for i, r in enumerate(rounds):
        for s in r.get('students', []):
            name = s.get('name', '')
            if name not in stu_map:
                stu_map[name] = {'name': name, 'gender': s.get('gender', '')}
            stu_map[name][f'round{i + 1}'] = s.get('total_score', 0) or 0

    if not stu_map:
        tk.Label(stu_frame, text='暂无学生数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
    else:
        stu_tree_frame = tk.Frame(stu_frame)
        stu_tree_frame.pack(fill='both', expand=True, padx=8, pady=8)

        stu_cols = ('姓名', '性别') + tuple(f'第{i + 1}次' for i in range(len(rounds))) + ('变化',)
        stu_widths = (70, 40) + tuple(50 for _ in range(len(rounds))) + (50,)

        stu_tree = ttk.Treeview(stu_tree_frame, columns=stu_cols, show='headings',
                                height=min(20, len(stu_map) + 1))
        for c, w in zip(stu_cols, stu_widths):
            stu_tree.heading(c, text=c, anchor='center')
            stu_tree.column(c, width=w, anchor='center', minwidth=35)

        sb2 = tk.Scrollbar(stu_tree_frame, orient='vertical', command=stu_tree.yview)
        stu_tree.configure(yscrollcommand=sb2.set)
        stu_tree.pack(side='left', fill='both', expand=True)
        sb2.pack(side='right', fill='y')

        for name, data in stu_map.items():
            vals = [data.get(f'round{i + 1}', '—') for i in range(len(rounds))]
            first = data.get('round1', 0) or 0
            last_key = f'round{len(rounds)}'
            last = data.get(last_key, 0) or 0
            if first > 0 and last > 0:
                diff = last - first
                diff_str = f'+{diff}' if diff > 0 else str(diff)
            else:
                diff_str = '—'

            row_vals = [data.get('name', name), data.get('gender', '')]
            for v in vals:
                row_vals.append(v if v != 0 else '—')
            row_vals.append(diff_str)
            stu_tree.insert('', tk.END, values=tuple(row_vals))

    tk.Button(dialog, text='关闭', command=dialog.destroy, width=12,
              bg=COLOR_PRIMARY, fg='white', font=(TK_FONT, 10)).pack(pady=(0, 10))


def show_aggregate_test_comparison(mw, grade=None, title='测试对比'):
    """聚合测试对比（全校或某年级）"""
    all_classes = mw.dm.get_all_classes()
    if grade:
        all_classes = {cid: cdata for cid, cdata in all_classes.items()
                      if cdata.get('grade') == grade}

    max_rounds = max((len(cdata.get('test_rounds', [])) for cdata in all_classes.values()), default=0)
    if max_rounds < 2:
        messagebox.showinfo('提示', '暂不足2次测试数据，无法对比')
        return

    round_stats = []
    for ri in range(max_rounds):
        students = []
        for cid, cdata in all_classes.items():
            rounds = cdata.get('test_rounds', [])
            if ri < len(rounds):
                students.extend(rounds[ri].get('students', []))

        total = len(students)
        dist = compute_grade_distribution(students)
        counts = dist['counts']
        pc = dist['pass_count']
        excel = round((counts['优秀'] + counts['良好']) / total * 100, 1) if total else 0
        round_stats.append({
            'round': ri + 1, 'total': total, 'excel': excel,
            'pass_rate': round(pc / total * 100, 1) if total else 0,
            'counts': counts,
        })

    dialog = tk.Toplevel(mw.window)
    dialog.title(title)
    dialog.geometry('920x720')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 920, 720)

    notebook = ttk.Notebook(dialog)
    notebook.pack(fill='both', expand=True, padx=5, pady=5)

    r_labels = [f"第{rs['round']}次" for rs in round_stats]

    # ---- Tab 1: 概览对比 ----
    ov = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(ov, text='概览对比')

    tbl_frame = tk.Frame(ov, bg=COLOR_BG_WHITE)
    tbl_frame.pack(fill='x', padx=15, pady=10)

    cols = ('轮次', '人数', '优良率', '及格率', '优秀', '良好', '及格', '不及格')
    widths = (60, 50, 70, 60, 50, 50, 50, 55)
    tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', height=len(round_stats) + 1)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=40)
    for rs in round_stats:
        tree.insert('', tk.END, values=(
            f"第{rs['round']}次", rs['total'], f"{rs['excel']}%", f"{rs['pass_rate']}%",
            rs['counts']['优秀'], rs['counts']['良好'],
            rs['counts']['及格'], rs['counts']['不及格']
        ))
    tree.pack(fill='x')

    chart_frame = tk.Frame(ov, bg=COLOR_BG_WHITE)
    chart_frame.pack(fill='both', expand=True, padx=15, pady=5)

    fig = Figure(figsize=(10, 4.5), dpi=100)
    ax1 = fig.add_subplot(121)
    r_avgs = [rs['excel'] for rs in round_stats]
    ax1.plot(r_labels, r_avgs, 'o-', color='#1976d2', linewidth=2, markersize=8)
    for i, v in enumerate(r_avgs):
        ax1.text(i, v + 0.5, str(v), ha='center', fontsize=10)
    ax1.set_title('优良率变化', fontsize=13, fontweight='bold')
    ax1.set_ylabel('优良率(%)')
    ax1.set_ylim(bottom=max(0, min(r_avgs) - 5), top=min(105, max(r_avgs) + 8))

    ax2 = fig.add_subplot(122)
    cats = ['优秀', '良好', '及格', '不及格']
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336']
    x = range(len(r_labels))
    bottom = [0] * len(r_labels)
    for cat, c in zip(cats, colors):
        vals = [rs['counts'][cat] for rs in round_stats]
        bars = ax2.bar(x, vals, bottom=bottom, label=cat, color=c, alpha=0.85)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                        str(val), ha='center', va='center', fontsize=9, fontweight='bold', color='white')
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax2.set_xticks(x)
    ax2.set_xticklabels(r_labels, fontsize=9)
    ax2.set_title('等级分布变化', fontsize=13, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=8)
    fig.subplots_adjust(bottom=0.12, wspace=0.3)
    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    canvas.draw()

    # ---- Tab 2: 项目对比（各轮次各项目优良率） ----
    item_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(item_frame, text='项目对比')

    # 收集所有年级的测试项目
    all_items = []
    if grade:
        all_items = GRADE_ITEMS.get(grade, [])
    else:
        for cid, cdata in all_classes.items():
            g = cdata.get('grade', 1)
            all_items.extend(GRADE_ITEMS.get(g, []))
        all_items = list(dict.fromkeys(all_items))  # 去重保持顺序

    if all_items:
        item_data = {}
        for item in all_items:
            item_data[item] = []
            for ri in range(max_rounds):
                students = _get_students_for_round(all_classes, ri)
                total_cnt = 0
                exc_cnt = 0
                for s in students:
                    sc = s.get('scores', {}).get(item, 0) or 0
                    if sc > 0:
                        total_cnt += 1
                        if sc >= 80:
                            exc_cnt += 1
                item_data[item].append(round(exc_cnt / total_cnt * 100, 1) if total_cnt else 0)

        fig3 = Figure(figsize=(9, 5), dpi=100)
        ax4 = fig3.add_subplot(111)
        line_styles = ['o-', 's--', '^-.', 'd:', 'v-', 'p--', 'h-.', '8:']
        for j, item in enumerate(all_items):
            style = line_styles[j % len(line_styles)]
            ax4.plot(r_labels, item_data[item], style, linewidth=2, markersize=7,
                     label=item)
            for i, v in enumerate(item_data[item]):
                ax4.text(i, v + 0.5, str(v), ha='center', fontsize=8)
        ax4.set_title('各项目优良率对比', fontsize=13, fontweight='bold')
        ax4.set_ylabel('优良率(%)')
        ax4.legend(loc='upper right', fontsize=8)
        ax4.grid(True, alpha=0.3)
        fig3.subplots_adjust(bottom=0.12)
        fig3.tight_layout()
        canvas3 = FigureCanvasTkAgg(fig3, master=item_frame)
        canvas3.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        canvas3.draw()
    else:
        tk.Label(item_frame, text='暂无项目数据', bg=COLOR_BG_WHITE,
                 font=(TK_FONT, 12)).pack(expand=True)

    tk.Button(dialog, text='关闭', command=dialog.destroy, width=12,
              bg=COLOR_PRIMARY, fg='white', font=(TK_FONT, 10)).pack(pady=(0, 10))


# ============================================================
#  年级分析
# ============================================================

def show_grade_analysis(mw, grade=None, show_selector=True):
    """年级综合分析"""
    if grade is None:
        grade = mw.current_grade
        show_selector = True
    if not grade:
        messagebox.showwarning('提示', '请先选择年级')
        return

    gname = GRADE_NAMES[grade - 1]

    if mw._grade_analysis_dialog and mw._grade_analysis_dialog.winfo_exists():
        mw._grade_analysis_dialog.lift()
        mw._grade_analysis_dialog.focus_force()
        return

    dialog = tk.Toplevel(mw.window)
    dialog.title(f'年级分析 - {gname}')
    dialog.geometry('900x700')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 900, 700)
    mw._grade_analysis_dialog = dialog
    dialog.protocol('WM_DELETE_WINDOW', lambda: (setattr(mw, '_grade_analysis_dialog', None), dialog.destroy()))
    dialog.bind('<Destroy>', lambda e: setattr(mw, '_grade_analysis_dialog', None))

    if show_selector:
        selector = tk.Frame(dialog, bg=COLOR_BG_LIGHT)
        selector.pack(fill='x', padx=10, pady=(8, 4))
        tk.Label(selector, text='选择年级：', font=(TK_FONT, 11), bg=COLOR_BG_LIGHT).pack(side='left', padx=(0, 8))
        grade_var = tk.StringVar(value=gname)
        grade_combo = ttk.Combobox(selector, textvariable=grade_var, values=GRADE_NAMES,
                                    state='readonly', width=12, font=(TK_FONT, 11))
        grade_combo.current(grade - 1)
        grade_combo.pack(side='left')

    content = tk.Frame(dialog, bg=COLOR_BG_WHITE)
    content.pack(fill='both', expand=True)

    def _render(g):
        for w in content.winfo_children():
            w.destroy()

        gn = GRADE_NAMES[g - 1]
        stats = mw.dm.get_statistics(grade=g)

        if stats['total'] == 0:
            tk.Label(content, text=f'{gn}暂无数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 14)).pack(expand=True)
            return

        notebook = ttk.Notebook(content)
        notebook.pack(fill='both', expand=True)

        # Tab 1: 概览
        overview_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
        notebook.add(overview_frame, text='概览')
        summary_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
        summary_frame.pack(fill='x', padx=20, pady=15)
        tk.Label(summary_frame, text=f'{gn} — 综合数据概览',
                 font=(TK_FONT, 14, 'bold'), bg=COLOR_BG_WHITE, fg=COLOR_PRIMARY).pack(anchor='w')
        st = (
            f"学生总数：{stats['total']}人\n"
            f"优良率：{stats['优秀率'] + stats['良好率']}%\n"
            f"及格率：{stats['及格率']}%\n"
            f"优秀率：{stats['优秀率']}%  |  良好率：{stats['良好率']}%  |  不及格率：{stats['不及格率']}%\n"
            f"优秀：{stats['优秀']}人  |  良好：{stats['良好']}人  |  及格：{stats['及格']}人  |  不及格：{stats['不及格']}人"
        )
        tk.Label(summary_frame, text=st, font=(TK_FONT, 11), bg=COLOR_BG_WHITE,
                 justify='left', anchor='w').pack(anchor='w', pady=(8, 0))
        chart_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
        chart_frame.pack(fill='both', expand=True, padx=20, pady=10)
        c1 = ChartBuilder.create_pie_chart(chart_frame, stats, title=f'{gn}等级分布')
        c1.get_tk_widget().pack(fill='both', expand=True)
        c1.draw()

        # Tab 2: 各项目得分
        items_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
        notebook.add(items_frame, text='各项目得分')
        items = GRADE_ITEMS.get(g, [])
        all_classes = mw.dm.get_classes_by_grade(g)
        item_total = {item: 0 for item in items}
        item_excel = {item: 0 for item in items}
        for cid in all_classes:
            for s in mw.dm.get_students(cid):
                scores = s.get('scores', {})
                for item in items:
                    sc = scores.get(item, 0) or 0
                    if sc > 0:
                        item_total[item] += 1
                        if sc >= 80:
                            item_excel[item] += 1
        excel_rates = {}
        for item in items:
            excel_rates[item] = round(item_excel[item] / item_total[item] * 100, 1) if item_total[item] else 0
        if not any(v > 0 for v in excel_rates.values()):
            tk.Label(items_frame, text='暂无评分数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
        else:
            c2 = ChartBuilder.create_radar_chart(items_frame, excel_rates, title=f'{gn}各项目优良率')
            c2.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
            c2.draw()

        # Tab 3: 班级对比
        class_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
        notebook.add(class_frame, text='班级对比')
        classes = mw.dm.get_classes_by_grade(g)
        if not classes:
            tk.Label(class_frame, text='暂无班级数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
        else:
            sl = []
            for cid in sorted(classes.keys()):
                cdata = classes[cid]
                cstudents = mw.dm.get_students(cid)
                counts = compute_grade_distribution(cstudents)['counts']
                sl.append((cdata.get('name', cid), counts))
            c3 = ChartBuilder.create_bar_chart(class_frame, sl, title=f'{gn}各班等级分布')
            c3.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
            c3.draw()

    _render(grade)

    if show_selector:
        def _on_grade_change(event=None):
            selected = grade_var.get()
            if selected in GRADE_NAMES:
                dialog.title(f'年级分析 - {selected}')
                _render(GRADE_NAMES.index(selected) + 1)
        grade_combo.bind('<<ComboboxSelected>>', _on_grade_change)

    # ---- 底部按钮 ----
    btn_frame = tk.Frame(dialog, bg=COLOR_BG_LIGHT)
    btn_frame.pack(fill='x', side='bottom', padx=8, pady=6)

    tk.Button(btn_frame, text='关闭', command=dialog.destroy,
              bg=COLOR_NEUTRAL, fg='white', font=(TK_FONT, 10),
              relief='flat', padx=15, pady=5, cursor='hand2').pack(side='right', padx=5)


# ============================================================
#  全校分析
# ============================================================

def _build_bmi_by_grade_tab(notebook, mw):
    """构建BMI分年级横向对比标签页"""
    frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(frame, text='BMI分年级')

    cats = ['正常', '超重', '低体重', '肥胖']
    grade_bmi_data = {}
    has_data = False

    for g in range(1, 7):
        all_classes = mw.dm.get_classes_by_grade(g)
        if not all_classes:
            continue
        students = []
        for cid in all_classes:
            students.extend(mw.dm.get_students(cid))
        if not students:
            continue

        dist = {cat: 0 for cat in cats}
        valid = 0
        for s in students:
            bg = s.get('bmi_grade', '')
            if bg in dist:
                dist[bg] += 1
                valid += 1

        if valid > 0:
            grade_bmi_data[g] = {
                'name': GRADE_NAMES[g - 1],
                '正常': dist['正常'], '超重': dist['超重'],
                '低体重': dist['低体重'], '肥胖': dist['肥胖'],
                '有效': valid,
                '肥胖率': f"{round(dist['肥胖'] / valid * 100, 1)}%"
            }
            has_data = True

    if not has_data:
        tk.Label(frame, text='暂无BMI数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)
        return

    tree_container = tk.Frame(frame, bg=COLOR_BG_WHITE)
    tree_container.pack(fill='both', expand=True, padx=5, pady=5)

    cols = ('年级', '有效总数', '正常', '超重', '低体重', '肥胖', '肥胖率')
    widths = (70, 70, 55, 55, 60, 55, 65)

    tree = ttk.Treeview(tree_container, columns=cols, show='headings', height=7)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c, anchor='center')
        tree.column(c, width=w, anchor='center', minwidth=50)

    for g in range(1, 7):
        if g in grade_bmi_data:
            d = grade_bmi_data[g]
            tree.insert('', tk.END, values=(d['name'], d['有效'], d['正常'], d['超重'],
                                            d['低体重'], d['肥胖'], d['肥胖率']))

    vsb = tk.Scrollbar(tree_container, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side='left', fill='both', expand=True)
    vsb.pack(side='right', fill='y')

    chart_f = tk.Frame(frame, bg=COLOR_BG_WHITE)
    chart_f.pack(fill='both', expand=True, padx=5, pady=5)
    bmi_stats_list = []
    for g in range(1, 7):
        if g in grade_bmi_data:
            d = grade_bmi_data[g]
            rate = round(d['肥胖'] / d['有效'] * 100, 1) if d['有效'] else 0
            bmi_stats_list.append((d['name'], rate))
    if bmi_stats_list:
        # 转成 dict 格式给 create_line_chart
        obese_dict = {name: rate for name, rate in bmi_stats_list}
        c = ChartBuilder.create_line_chart(chart_f, obese_dict, title='各年级肥胖率趋势')
        c.get_tk_widget().pack(fill='both', expand=True)
        c.draw()


def _build_item_grade_distribution_tab(notebook, mw):
    """构建各项目分年级等级分布标签页"""
    frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(frame, text='项目分年级')

    sub_nb = ttk.Notebook(frame)
    sub_nb.pack(fill='both', expand=True, padx=2, pady=2)

    cats = ['优秀', '良好', '及格', '不及格']

    for grade_num in range(1, 7):
        items = GRADE_ITEMS.get(grade_num, [])
        for item_name in items:
            existing_tabs = {sub_nb.tab(i, 'text'): i for i in range(sub_nb.index('end'))}
            if item_name in existing_tabs:
                continue

            item_frame = tk.Frame(sub_nb, bg=COLOR_BG_WHITE)
            sub_nb.add(item_frame, text=item_name)

            cols = ('年级', '有效总数', '优良率', '优秀', '良好', '及格', '不及格')
            widths = (70, 65, 60, 50, 50, 50, 55)

            tree = ttk.Treeview(item_frame, columns=cols, show='headings', height=7)
            for c, w in zip(cols, widths):
                tree.heading(c, text=c, anchor='center')
                tree.column(c, width=w, anchor='center', minwidth=45)

            has_data = False
            grade_excel_data = {}
            for g in range(1, 7):
                if item_name not in GRADE_ITEMS.get(g, []):
                    continue
                all_classes = mw.dm.get_classes_by_grade(g)
                if not all_classes:
                    continue

                dist = {cat: 0 for cat in cats}
                valid = 0
                for cid in all_classes:
                    for s in mw.dm.get_students(cid):
                        sc = s.get('scores', {}).get(item_name)
                        if sc is not None and sc > 0:
                            valid += 1
                            if sc >= 90:
                                dist['优秀'] += 1
                            elif sc >= 80:
                                dist['良好'] += 1
                            elif sc >= 60:
                                dist['及格'] += 1
                            else:
                                dist['不及格'] += 1

                if valid > 0:
                    exc = dist['优秀'] + dist['良好']
                    tree.insert('', tk.END, values=(
                        GRADE_NAMES[g - 1], valid, f"{round(exc / valid * 100, 1)}%",
                        dist['优秀'], dist['良好'], dist['及格'], dist['不及格']
                    ))
                    grade_excel_data[GRADE_NAMES[g - 1]] = round(exc / valid * 100, 1)
                    has_data = True

            if has_data:
                vsb = tk.Scrollbar(item_frame, orient='vertical', command=tree.yview)
                tree.configure(yscrollcommand=vsb.set)
                tree.pack(side='top', fill='x', padx=5, pady=(5, 0))
                vsb.pack(side='right', fill='y')

                # 优良率趋势图
                chart_f = tk.Frame(item_frame, bg=COLOR_BG_WHITE)
                chart_f.pack(fill='both', expand=True, padx=5, pady=5)
                if grade_excel_data:
                    c = ChartBuilder.create_line_chart(chart_f, grade_excel_data,
                        title=f'{item_name}各年级优良率趋势')
                    c.get_tk_widget().pack(fill='both', expand=True)
                    c.draw()
            else:
                tk.Label(item_frame, text='暂无数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)


def show_school_analysis(mw):
    """全校综合分析：多维度数据展示"""
    stats = mw.dm.get_statistics()
    if stats['total'] == 0:
        messagebox.showinfo('提示', '暂无数据')
        return

    if mw._school_analysis_dialog and mw._school_analysis_dialog.winfo_exists():
        mw._school_analysis_dialog.lift()
        mw._school_analysis_dialog.focus_force()
        return

    dialog = tk.Toplevel(mw.window)
    dialog.title('全校分析')
    dialog.geometry('960x780')
    dialog.resizable(True, True)
    dialog.transient(mw.window)
    dialog.grab_set()
    center_window(dialog, 960, 780)
    mw._school_analysis_dialog = dialog
    dialog.protocol('WM_DELETE_WINDOW', lambda: (setattr(mw, '_school_analysis_dialog', None), dialog.destroy()))
    dialog.bind('<Destroy>', lambda e: setattr(mw, '_school_analysis_dialog', None))

    notebook = ttk.Notebook(dialog)
    notebook.pack(fill='both', expand=True, padx=5, pady=5)

    # ---- Tab 1: 概览 ----
    overview_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(overview_frame, text='概览')

    summary_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
    summary_frame.pack(fill='x', padx=20, pady=15)

    tk.Label(summary_frame, text='全校综合数据概览',
             font=(TK_FONT, 14, 'bold'), bg=COLOR_BG_WHITE, fg=COLOR_PRIMARY).pack(anchor='w')

    stats_text = (
        f"学生总数：{stats['total']}人\n"
        f"全校优良率：{stats['优秀率'] + stats['良好率']}%\n"
        f"全校及格率：{stats['及格率']}%\n"
        f"优秀率：{stats['优秀率']}%  |  良好率：{stats['良好率']}%  |  不及格率：{stats['不及格率']}%\n"
        f"优秀：{stats['优秀']}人  |  良好：{stats['良好']}人  |  及格：{stats['及格']}人  |  不及格：{stats['不及格']}人"
    )
    tk.Label(summary_frame, text=stats_text, font=(TK_FONT, 11), bg=COLOR_BG_WHITE,
             justify='left', anchor='w').pack(anchor='w', pady=(8, 0))

    chart_frame = tk.Frame(overview_frame, bg=COLOR_BG_WHITE)
    chart_frame.pack(fill='both', expand=True, padx=20, pady=10)
    canvas1 = ChartBuilder.create_pie_chart(chart_frame, stats, title='全校等级占比')
    canvas1.get_tk_widget().pack(fill='both', expand=True)
    canvas1.draw()

    # ---- Tab 2: 年级对比 ----
    grade_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(grade_frame, text='年级对比')

    grade_stats = []
    for g in range(1, 7):
        gs = mw.dm.get_statistics(grade=g)
        if gs['total'] > 0:
            grade_stats.append((GRADE_NAMES[g - 1], {
                '优秀': gs['优秀'], '良好': gs['良好'],
                '及格': gs['及格'], '不及格': gs['不及格']
            }))

    if grade_stats:
        c_grade = ChartBuilder.create_bar_chart(grade_frame, grade_stats, title='各年级等级分布对比')
        c_grade.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        c_grade.draw()
    else:
        tk.Label(grade_frame, text='暂无年级数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)

    # ---- Tab 3: 年级优良率趋势 ----
    trend_frame = tk.Frame(notebook, bg=COLOR_BG_WHITE)
    notebook.add(trend_frame, text='优良率趋势')

    scores = {}
    for g in range(1, 7):
        gs = mw.dm.get_statistics(grade=g)
        if gs['total'] > 0:
            scores[GRADE_NAMES[g - 1]] = gs['优秀率'] + gs['良好率']

    if scores:
        c_trend = ChartBuilder.create_line_chart(trend_frame, scores)
        c_trend.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        c_trend.draw()
    else:
        tk.Label(trend_frame, text='暂无数据', bg=COLOR_BG_WHITE, font=(TK_FONT, 12)).pack(expand=True)

    # ---- Tab 4-7: 详细分析 ----
    _build_test_comparison_table(notebook, mw, title='全校各轮次测试对比')
    _build_bmi_by_grade_tab(notebook, mw)
    _build_item_grade_distribution_tab(notebook, mw)

    # ---- 导出按钮 ----
    btn_frame = tk.Frame(dialog, bg=COLOR_BG_LIGHT)
    btn_frame.pack(fill='x', side='bottom', padx=8, pady=6)

    def _export_school_data():
        from excel_io import export_statistics_report
        filepath = filedialog.asksaveasfilename(
            title='导出全校分析报告',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx')],
            parent=dialog
        )
        if not filepath:
            return
        success, msg = export_statistics_report(mw.dm, filepath, scope='全校')
        if success:
            messagebox.showinfo('导出成功', msg, parent=dialog)
        else:
            messagebox.showerror('导出失败', msg, parent=dialog)

    tk.Button(btn_frame, text='📤 导出数据', command=_export_school_data,
              bg=COLOR_ACCENT, fg='white', font=(TK_FONT, 10, 'bold'),
              relief='flat', padx=15, pady=5, cursor='hand2').pack(side='right', padx=5)
    tk.Button(btn_frame, text='关闭', command=dialog.destroy,
              bg=COLOR_NEUTRAL, fg='white', font=(TK_FONT, 10),
              relief='flat', padx=15, pady=5, cursor='hand2').pack(side='right', padx=5)
