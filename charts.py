"""统计图表 — matplotlib 集成到 Tkinter"""

import warnings
import matplotlib
matplotlib.use('TkAgg')
warnings.filterwarnings('ignore', message='Unable to import Axes3D')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
from config import FONT_CANDIDATES, GRADE_LEVELS
import os

# 设置中文字体
def _setup_chinese_font():
    """配置 matplotlib 中文字体"""
    try:
        # 先尝试已注册的字体名
        available = [f.name for f in fontManager.ttflist]
        
        for font_name in FONT_CANDIDATES:
            if font_name in available:
                plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
                return font_name
        
        # 尝试通过文件路径注册字体
        font_paths = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc',
            '/usr/share/fonts/truetype/arphic/ukai.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/System/Library/Fonts/PingFang.ttc',
            'C:/Windows/Fonts/msyh.ttc',
            'C:/Windows/Fonts/simhei.ttf',
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                fontManager.addfont(path)
                prop = FontProperties(fname=path)
                plt.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
                return prop.get_name()
        
        # 回退
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.unicode_minus'] = False
        return 'sans-serif'
    except Exception:
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.unicode_minus'] = False
        return 'sans-serif'


_font_initialized = False


def _ensure_chinese_font():
    """按需初始化 matplotlib 中文字体（惰性加载）"""
    global _font_initialized
    if _font_initialized:
        return
    _setup_chinese_font()
    _font_initialized = True


# 颜色方案
COLORS = {
    '优秀': '#4CAF50',
    '良好': '#2196F3',
    '及格': '#FF9800',
    '不及格': '#F44336',
}


class ChartBuilder:
    """图表构建器"""
    
    @staticmethod
    def create_bar_chart(parent, stats, title="各等级人数分布"):
        """柱状图：各班各等级人数分布
        
        Args:
            parent: Tkinter 容器
            stats: list of (className, {优秀: n, 良好: n, 及格: n, 不及格: n})
            title: 图表标题
        """
        _ensure_chinese_font()
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        if not stats:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return FigureCanvasTkAgg(fig, master=parent)
        
        classes = [s[0] for s in stats]
        categories = ['优秀', '良好', '及格', '不及格']
        
        x = range(len(classes))
        width = 0.2
        
        for i, cat in enumerate(categories):
            values = [s[1].get(cat, 0) for s in stats]
            bars = ax.bar([xi + i * width for xi in x], values, width, 
                         label=cat, color=COLORS[cat], alpha=0.85)
            # 在柱子上标注数值
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                           str(val), ha='center', va='bottom', fontsize=8)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks([xi + width * 1.5 for xi in x])
        ax.set_xticklabels(classes, fontsize=9)
        ax.set_ylabel('人数')
        ax.legend(loc='upper right')
        ax.set_ylim(bottom=0)
        
        fig.subplots_adjust(bottom=0.18)
        return FigureCanvasTkAgg(fig, master=parent)
    
    @staticmethod
    def create_pie_chart(parent, stats, title="等级占比"):
        """饼图：等级占比"""
        _ensure_chinese_font()
        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        labels = ['优秀', '良好', '及格', '不及格']
        sizes = [stats.get(label, 0) for label in labels]
        colors_list = [COLORS[label] for label in labels]
        
        if sum(sizes) == 0:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return FigureCanvasTkAgg(fig, master=parent)
        
        # 过滤掉0值
        filtered = [(l, s, c) for l, s, c in zip(labels, sizes, colors_list) if s > 0]
        if filtered:
            labels, sizes, colors_list = zip(*filtered)
        else:
            labels, sizes, colors_list = ['无数据'], [1], ['#CCCCCC']
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors_list, autopct='%1.1f%%',
            startangle=90, pctdistance=0.85
        )
        
        # 美化文字
        for t in autotexts:
            t.set_fontsize(10)
            t.set_color('white')
            t.set_fontweight('bold')
        for t in texts:
            t.set_fontsize(11)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        fig.tight_layout()
        return FigureCanvasTkAgg(fig, master=parent)
    
    @staticmethod
    def create_line_chart(parent, grade_scores, title="各年级优良率趋势"):
        """折线图：各年级优良率趋势
        
        Args:
            grade_scores: dict {年级名: 优良率(%)}
        """
        _ensure_chinese_font()
        fig = Figure(figsize=(7, 4.5), dpi=100)
        ax = fig.add_subplot(111)
        
        if not grade_scores:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return FigureCanvasTkAgg(fig, master=parent)
        
        grades = list(grade_scores.keys())
        scores = list(grade_scores.values())
        
        ax.plot(grades, scores, 'o-', color='#2196F3', linewidth=2.5, markersize=8, markerfacecolor='white',
               markeredgewidth=2.5, markeredgecolor='#2196F3')
        
        # 标注数值
        for i, (g, s) in enumerate(zip(grades, scores)):
            ax.annotate(f'{s}%', (i, s), textcoords="offset points", xytext=(0, 12),
                       ha='center', fontsize=10, fontweight='bold')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('优良率(%)')
        ax.set_ylim(max(0, min(scores) - 10), min(100, max(scores) + 10))
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('年级')
        
        fig.subplots_adjust(bottom=0.18)
        return FigureCanvasTkAgg(fig, master=parent)
    
    @staticmethod
    def create_radar_chart(parent, grade_items_avg, title="各项目平均得分"):
        """雷达图：年级各项目平均得分
        
        Args:
            grade_items_avg: dict {项目名: 平均得分}
        """
        _ensure_chinese_font()
        import numpy as np
        fig = Figure(figsize=(6, 5), dpi=100)
        ax = fig.add_subplot(111, polar=True)
        
        if not grade_items_avg:
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', transform=ax.transAxes, fontsize=14)
            return FigureCanvasTkAgg(fig, master=parent)
        
        categories = list(grade_items_avg.keys())
        values = list(grade_items_avg.values())
        N = len(categories)
        
        angles = [n / N * 2 * np.pi for n in range(N)]
        angles += angles[:1]
        values += values[:1]
        
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=9)
        
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=7, color='grey')
        ax.set_rlabel_position(30)
        
        ax.plot(angles, values, 'o-', linewidth=2, color='#2196F3')
        ax.fill(angles, values, alpha=0.15, color='#2196F3')
        
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        fig.tight_layout()
        return FigureCanvasTkAgg(fig, master=parent)
    
    @staticmethod
    def save_chart(fig, filepath):
        """保存图表为PNG"""
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        return True
