"""通用工具函数"""


def center_window(window, width, height):
    """窗口居中"""
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    window.geometry(f'{width}x{height}+{x}+{y}')


def get_grade_level(score):
    """将分数映射为等级标签"""
    if score is None or score == '':
        return None
    try:
        s = float(score)
    except (ValueError, TypeError):
        return None
    if s >= 90:
        return '优秀'
    elif s >= 80:
        return '良好'
    elif s >= 60:
        return '及格'
    else:
        return '不及格'


def calc_item_stats(students, scores_or_key):
    """统计某项目(或总成绩)的等级分布

    Args:
        students: 学生数据列表
        scores_or_key: str ('total_score' 或项目名) 或 callable

    Returns:
        (stats_dict, valid_count)
        stats_dict: {等级: (人数, 百分比字符串)}
    """
    counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
    valid = 0
    for s in students:
        if callable(scores_or_key):
            level = scores_or_key(s)
        elif scores_or_key == 'total_score':
            level = get_grade_level(s.get('total_score'))
        else:
            level = get_grade_level(s.get('scores', {}).get(scores_or_key))
        if level:
            counts[level] += 1
            valid += 1
    stats = {}
    for k in counts:
        pct = f'{counts[k] / valid * 100:.1f}%' if valid > 0 else '—'
        stats[k] = (counts[k], pct)
    return stats, valid


def compute_grade_distribution(students):
    """统计学生列表的总成绩等级分布（单次遍历，无除零风险）

    Args:
        students: 学生数据列表，每个学生应有 'total_grade' 和 'total_score' 字段

    Returns:
        {'total': int, 'counts': {等级: int}, 'pass_count': int,
         'avg_score': float, 'scored_count': int}
        — 零学生时 total=0, counts 全零, avg_score=0
    """
    counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
    total_score = 0
    scored_count = 0

    for s in students:
        g = s.get('total_grade', '')
        if g in counts:
            counts[g] += 1
        ts = s.get('total_score', 0) or 0
        if ts > 0:
            total_score += ts
            scored_count += 1

    total = len(students)
    avg = round(total_score / scored_count, 1) if scored_count > 0 else 0
    pass_count = counts['优秀'] + counts['良好'] + counts['及格']

    return {
        'total': total,
        'counts': counts,
        'pass_count': pass_count,
        'avg_score': avg,
        'scored_count': scored_count,
    }
