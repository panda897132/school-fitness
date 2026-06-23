"""常量配置 — 诸葛镇中心小学学生体质健康管理系统"""

import os
import platform
import subprocess
import sys

_APP_VERSION = "1.0.15"

# 源码运行时自动从 git tag 获取版本号（打包时 CI 会改写此文件）
if not getattr(sys, 'frozen', False):
    try:
        _tag = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, timeout=2,
            cwd=os.path.dirname(__file__)
        ).stdout.strip()
        if _tag.startswith('v'):
            _APP_VERSION = _tag[1:]
    except Exception:
        pass

APP_VERSION = _APP_VERSION
APP_REPO = "panda897132/school-fitness"

SCHOOL_NAME = "诸葛镇中心小学"
APP_TITLE = f"{SCHOOL_NAME} — 学生体质健康管理系统"
DEFAULT_USERNAME = "admin"
# 密码不再以明文常量定义，首次启动时自动生成随机密码并由 data_manager 打印到终端

# 年级定义
GRADE_NAMES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]
GRADE_NUMS = [1, 2, 3, 4, 5, 6]

CN_TO_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
NUM_TO_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}

# 各年级测试项目
GRADE_ITEMS = {
    1: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳"],
    2: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳"],
    3: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳", "仰卧起坐"],
    4: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳", "仰卧起坐"],
    5: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳", "仰卧起坐", "50*8折返跑"],
    6: ["肺活量", "50米跑", "坐位体前屈", "一分钟跳绳", "仰卧起坐", "50*8折返跑"],
}

# 项目名称规范化映射
ITEM_NAME_ALIASES = {
    "50x8折返跑": "50*8折返跑",
    "50×8折返跑": "50*8折返跑",
    "50X8折返跑": "50*8折返跑",
}

# 项目权重(百分比)
ITEM_WEIGHTS = {
    1: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 30, "一分钟跳绳": 20, "BMI": 15},
    2: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 30, "一分钟跳绳": 20, "BMI": 15},
    3: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 20, "一分钟跳绳": 20, "仰卧起坐": 10, "BMI": 15},
    4: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 20, "一分钟跳绳": 20, "仰卧起坐": 10, "BMI": 15},
    5: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 10, "一分钟跳绳": 10, "仰卧起坐": 20, "50*8折返跑": 10, "BMI": 15},
    6: {"肺活量": 15, "50米跑": 20, "坐位体前屈": 10, "一分钟跳绳": 10, "仰卧起坐": 20, "50*8折返跑": 10, "BMI": 15},
}

# 等级定义
GRADE_LEVELS = {
    "优秀": (90, 100),
    "良好": (80, 89),
    "及格": (60, 79),
    "不及格": (0, 59),
}

# 跳绳附加分上限（国家学生体质健康标准）
JUMP_ROPE_BONUS_MAX = 20

# 窗口默认尺寸
LOGIN_WINDOW_SIZE = (500, 350)
MAIN_WINDOW_SIZE = (1200, 750)

# 主题颜色
COLOR_PRIMARY = '#1976d2'
COLOR_PRIMARY_DARK = '#1565c0'
COLOR_ACCENT = '#1a73e8'
COLOR_SUCCESS = '#4CAF50'
COLOR_DANGER = '#F44336'
COLOR_WARNING = '#FF9800'
COLOR_NEUTRAL = '#9E9E9E'
COLOR_BG_LIGHT = '#f5f5f5'
COLOR_BG_WHITE = 'white'
COLOR_BG_HEADER = '#e3f2fd'
COLOR_TEXT_LIGHT = '#999'
COLOR_TEXT_MUTED = '#666'

# 字体预设 — 在 TK_FONT 定义之后
# (见下方 TK_FONT 后的字体常量)

# 数据目录
DATA_DIR = "data"
STUDENTS_FILE = "data/students.json"
STANDARDS_FILE = "data/scoring_standards.json"
CONFIG_FILE = "data/app_config.json"

# 学生表格列定义（对齐模板格式：每个测试项目后紧跟得分列）
STUDENT_COLUMNS = [
    ("序号", 40),
    ("姓名", 80),
    ("性别", 50),
    ("身高", 70),
    ("体重", 70),
    ("BMI", 60),
    ("BMI得分", 60),
    ("肺活量", 70),
    ("肺活量得分", 60),
    ("50米跑", 70),
    ("50米跑得分", 60),
    ("坐位体前屈", 80),
    ("坐位体前屈得分", 60),
    ("一分钟跳绳", 80),
    ("一分钟跳绳得分", 60),
    ("跳绳附加分", 60),
    ("仰卧起坐", 70),
    ("仰卧起坐得分", 60),
    ("50*8折返跑", 80),
    ("50*8折返跑得分", 60),
    ("总成绩", 60),
    ("等级", 60),
]

# Tkinter 字体（按平台自动选择合适的中文字体）
_system = platform.system()
if _system == 'Windows':
    TK_FONT = 'Microsoft YaHei'
elif _system == 'Darwin':
    TK_FONT = 'PingFang SC'
else:
    TK_FONT = 'Noto Sans CJK JP'

# 字体预设（依赖 TK_FONT）
FONT_BOLD_14 = (TK_FONT, 14, 'bold')
FONT_BOLD_13 = (TK_FONT, 13, 'bold')
FONT_BOLD_12 = (TK_FONT, 12, 'bold')
FONT_BOLD_11 = (TK_FONT, 11, 'bold')
FONT_BOLD_10 = (TK_FONT, 10, 'bold')
FONT_NORMAL_11 = (TK_FONT, 11)
FONT_NORMAL_10 = (TK_FONT, 10)
FONT_NORMAL_9 = (TK_FONT, 9)
FONT_SMALL_8 = (TK_FONT, 8)

# matplotlib 中文字体候选
FONT_CANDIDATES = [
    "SimHei", "Microsoft YaHei",
    "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Serif CJK SC",
    "AR PL UMing CN", "AR PL UKai CN",
    "WenQuanYi Micro Hei", "DejaVu Sans"
]
