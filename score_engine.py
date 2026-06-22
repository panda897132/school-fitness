"""评分计算引擎 — 基于《国家学生体质健康标准（2014修订版）》"""

import json
import os
import re
from config import DATA_DIR, STANDARDS_FILE

# 加载评分标准
_standards = None

def _load_standards():
    global _standards
    if _standards is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), STANDARDS_FILE)
        with open(path, 'r', encoding='utf-8') as f:
            _standards = json.load(f)
    return _standards


def _parse_bmi_range(range_str):
    """解析BMI范围字符串，返回 (min_val, max_val, inclusive_min, inclusive_max)
    
    支持格式:
    - "13.4< x ≤18.1" → (13.4, 18.1, False, True)
    - "≤13.4" → (None, 13.4, True, True)
    - "≥20.4" → (20.4, None, True, True)
    - "18.1 < x < 20.4" → (18.1, 20.4, False, False)
    """
    if range_str is None:
        return None, None, False, False
    
    s = range_str.replace(' ', '')
    
    # Match patterns
     
     # Pattern: ≤value  or  <value
    m = re.match(r'^([≤<])\s*([\d.]+)$', s)
    if m:
        sign = m.group(1)
        val = float(m.group(2))
        return None, val, True, (sign == '≤')
    
    # Pattern: ≥value  or  >value
    m = re.match(r'^([≥>])\s*([\d.]+)$', s)
    if m:
        sign = m.group(1)
        val = float(m.group(2))
        return val, None, (sign == '≥'), True
    
    # Try simpler patterns
    m = re.match(r'^<([\d.]+)$', s)
    if m:
        return None, float(m.group(1)), True, False
    m = re.match(r'^≤([\d.]+)$', s)
    if m:
        return None, float(m.group(1)), True, True
    m = re.match(r'^>([\d.]+)$', s)
    if m:
        return float(m.group(1)), None, False, True
    m = re.match(r'^≥([\d.]+)$', s)
    if m:
        return float(m.group(1)), None, True, True
    
    # Simple dual-bound patterns first (exact matching)
    # Pattern: a < x < b
    m = re.match(r'^([\d.]+)\s*<\s*x\s*<\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), float(m.group(2)), False, False
    
    # Pattern: a < x ≤ b
    m = re.match(r'^([\d.]+)\s*<\s*x\s*≤\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), float(m.group(2)), False, True
    
    # Pattern: a ≤ x < b
    m = re.match(r'^([\d.]+)\s*≤\s*x\s*<\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), float(m.group(2)), True, False
    
    # Pattern: a ≤ x ≤ b
    m = re.match(r'^([\d.]+)\s*≤\s*x\s*≤\s*([\d.]+)$', s)
    if m:
        return float(m.group(1)), float(m.group(2)), True, True
    
    # Fallback: complex regex for edge cases (e.g., "≤a < x ≤ b")
    m = re.match(r'^([≤<]?)\s*([\d.]+)\s*[<≤]\s*x\s*[<≤]\s*([\d.]+)\s*([≤]?)$', s)
    if m:
        lo_sign = m.group(1)
        lo_val = float(m.group(2))
        hi_val = float(m.group(3))
        hi_sign = m.group(4)
        lo_inclusive = (lo_sign == '≤')
        hi_inclusive = (hi_sign == '≤')
        return lo_val, hi_val, lo_inclusive, hi_inclusive
    
    return None, None, False, False


def _bmi_in_range(bmi_val, lo, hi, lo_inclusive, hi_inclusive):
    """检查BMI值是否在范围内"""
    # 解析失败时上下界均为 None，应视为不匹配而非匹配
    if lo is None and hi is None:
        return False
    if lo is not None:
        if lo_inclusive:
            if bmi_val < lo:
                return False
        else:
            if bmi_val <= lo:
                return False
    if hi is not None:
        if hi_inclusive:
            if bmi_val > hi:
                return False
        else:
            if bmi_val >= hi:
                return False
    return True


def calc_bmi_score(height, weight, gender, grade):
    """计算BMI得分和等级
    
    Args:
        height: 身高(cm)
        weight: 体重(kg)
        gender: '男' or '女'
        grade: 年级数字 1-6
    
    Returns:
        (bmi_value, bmi_grade, bmi_score)
        bmi_grade: '正常'/'低体重'/'超重'/'肥胖'
    """
    if height is None or weight is None or height <= 0 or weight <= 0:
        return None, None, 0
    
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 1)
    
    standards = _load_standards()
    grade_key = str(grade)
    
    if grade_key not in standards:
        return bmi, None, 0
    
    bmi_list = standards[grade_key].get('bmi', [])
    
    gender_key = 'male_range' if gender == '男' else 'female_range'
    
    # 查找匹配的BMI范围（单次遍历，同时记录"正常"范围的边界）
    normal_lo = normal_hi = None
    normal_lo_inc = normal_hi_inc = False
    
    for entry in bmi_list:
        range_str = entry.get(gender_key)
        if range_str is None:
            continue
        lo, hi, lo_inc, hi_inc = _parse_bmi_range(range_str)
        
        if _bmi_in_range(bmi, lo, hi, lo_inc, hi_inc):
            grade_rank = entry.get('grade_rank', '')
            bmi_score = entry.get('bmi_score')
            if bmi_score is None or bmi_score == 0:
                bmi_score = entry.get('score', 0) or 0
            return bmi, grade_rank, bmi_score
        
        # 记录"正常"范围边界用于溢出判断
        if entry.get('grade_rank') == '正常':
            normal_lo, normal_hi = lo, hi
            normal_lo_inc, normal_hi_inc = lo_inc, hi_inc
    
    # 没有精确匹配：检查是否超出"正常"范围（低体重/肥胖）
    if normal_lo is not None and bmi <= normal_lo:
        for e in bmi_list:
            if e.get('grade_rank') == '低体重':
                return bmi, '低体重', e.get('bmi_score', 80)
        return bmi, '低体重', 80
    if normal_hi is not None and bmi >= normal_hi:
        for e in bmi_list:
            if e.get('grade_rank') == '肥胖':
                return bmi, '肥胖', e.get('bmi_score', 60)
        return bmi, '肥胖', 60
    
    return bmi, '正常', 100


def _parse_value(val_str):
    """解析评分标准中的值"""
    if val_str is None:
        return None
    s = str(val_str).strip()
    # Try as number
    try:
        return float(s)
    except ValueError:
        pass
    # Try time format like 1'36 → seconds
    m = re.match(r"(\d+)'(\d+)", s)
    if m:
        return float(m.group(1)) * 60 + float(m.group(2))
    return s


def _normalize_item_name(item_name, grade):
    """规范化项目名称，兼容 50x8 和 50*8 等别名"""
    from config import ITEM_NAME_ALIASES
    if item_name in ITEM_NAME_ALIASES:
        return ITEM_NAME_ALIASES[item_name]
    return item_name


def calc_item_score(value, gender, grade, item_name):
    """计算单项得分
    
    Args:
        value: 测试原始值
        gender: '男' or '女'
        grade: 年级数字 1-6
        item_name: 项目名称
    
    Returns:
        得分 (0-100)
    """
    if value is None:
        return 0
    
    # 折返跑项目：自动检测分.秒格式并转为纯秒数
    # 如 1.43 → 1分43秒 → 103秒
    SHUTTLE_MIN_SECONDS = 0.5
    SHUTTLE_MAX_SECONDS = 10.0
    if '折返跑' in item_name and isinstance(value, (int, float)) and SHUTTLE_MIN_SECONDS <= value < SHUTTLE_MAX_SECONDS:
        minutes = int(value)
        seconds_part = round((value - minutes) * 100)
        if 0 <= seconds_part < 60:
            value = minutes * 60 + seconds_part
    
    LOWER_IS_BETTER_KEYWORDS = ['50米', '折返跑', '跑']
    is_running = any(kw in item_name for kw in LOWER_IS_BETTER_KEYWORDS)
    
    item_name = _normalize_item_name(item_name, grade)
    
    standards = _load_standards()
    grade_key = str(grade)
    
    if grade_key not in standards:
        return 0
    
    scoring = standards[grade_key].get('scoring', {})
    if item_name not in scoring:
        return 0
    
    gender_key = 'male' if gender == '男' else 'female'
    score_table = scoring[item_name].get(gender_key, {})
    
    if not score_table:
        return 0
    
    # Parse all score thresholds
    # For items where higher is better (肺活量, 坐位体前屈, 一分钟跳绳, 仰卧起坐)
    # For items where lower is better (50米跑, 50*8折返跑)
    # Sort by parsed value to determine direction
    
    parsed = []
    for score_str, val_str in score_table.items():
        pv = _parse_value(val_str)
        if pv is not None:
            parsed.append((int(score_str), pv))
    
    if not parsed:
        return 0
    
    # 只有一个标准时直接返回该分数，无需方向判断
    if len(parsed) == 1:
        return parsed[0][0]
    
    # 语义判断方向：跑步/竞速类项目值越低分数越高
    higher_is_better = not is_running
    
    # 跑步类项目值为0表示未测试，直接返回0分
    if not higher_is_better and value <= 0:
        return 0
    
    # Find the matching score
    if higher_is_better:
        # Value above highest threshold → 100分
        max_score_entry = max(parsed, key=lambda x: x[1])
        if value >= max_score_entry[1]:
            return max_score_entry[0]
        # Value below lowest threshold → 最后得分
        min_score_entry = min(parsed, key=lambda x: x[0])
        if value <= min(parsed, key=lambda x: x[1])[1]:
            return min_score_entry[0]
        # Find closest threshold
        for score, threshold in sorted(parsed, key=lambda x: -x[1]):
            if value >= threshold:
                return score
        return 0
    else:
        # Lower is better
        min_score_entry = min(parsed, key=lambda x: x[1])
        if value <= min_score_entry[1]:
            return min_score_entry[0]
        # Value above worst threshold → 最低分
        worst_score_entry = min(parsed, key=lambda x: x[0])
        if value >= max(parsed, key=lambda x: x[1])[1]:
            return worst_score_entry[0]
        # Find closest threshold
        for score, threshold in sorted(parsed, key=lambda x: x[1]):
            if value <= threshold:
                return score
        return 0


def calc_total_score(student_data, grade):
    """计算综合总分和等级
    
    Args:
        student_data: dict with keys:
            - height, weight, gender, bmi (or will be calculated)
            - tests: dict of item_name → value
        grade: 年级数字 1-6
    
    Returns:
        dict with:
            - bmi, bmi_grade, bmi_score
            - item_scores: dict of item_name → score
            - total_score, total_grade
    """
    from config import ITEM_WEIGHTS
    
    gender = student_data.get('gender', '男')
    height = student_data.get('height')
    weight = student_data.get('weight')
    tests = student_data.get('tests', {})

    # 空值保护：缺少关键字段时返回不完整标记
    if not gender or height is None or weight is None:
        return {'item_scores': {}, 'total_score': 0, 'total_grade': '数据不完整'}
    
    result = {'item_scores': {}, 'jump_rope_bonus': 0}
    
    # Calculate BMI (use pre-computed if available from student_data)
    if 'bmi_score' in student_data and student_data['bmi_score'] is not None:
        bmi_val = student_data.get('bmi')
        bmi_grade = student_data.get('bmi_grade', '')
        bmi_score = student_data['bmi_score']
    else:
        bmi_val, bmi_grade, bmi_score = calc_bmi_score(height, weight, gender, grade)
    result['bmi'] = bmi_val
    result['bmi_grade'] = bmi_grade
    result['bmi_score'] = bmi_score
    
    # Calculate each item score
    weights = ITEM_WEIGHTS.get(grade, {})
    total_weighted = 0.0
    
    for item_name, value in tests.items():
        if value is None:
            result['item_scores'][item_name] = 0
            continue
        score = calc_item_score(value, gender, grade, item_name)
        result['item_scores'][item_name] = score
        
        weight = weights.get(item_name, 0)
        
        # 一分钟跳绳附加分：超过100分阈值后每多2个加1分，最高20分
        if item_name == '一分钟跳绳':
            bonus = calc_jump_rope_bonus(value, gender, grade)
            result['jump_rope_bonus'] = bonus
            effective_score = min(score, 100) + bonus  # 有效得分最高120
            total_weighted += effective_score * weight / 100.0
        else:
            total_weighted += score * weight / 100.0
    
    # Add BMI weighted score
    bmi_weight = weights.get('BMI', 15)
    total_weighted += bmi_score * bmi_weight / 100.0
    
    total_score = round(total_weighted, 1)
    result['total_score'] = total_score
    
    # Determine grade level
    if total_score >= 90:
        result['total_grade'] = '优秀'
    elif total_score >= 80:
        result['total_grade'] = '良好'
    elif total_score >= 60:
        result['total_grade'] = '及格'
    else:
        result['total_grade'] = '不及格'
    
    return result


def get_jump_rope_100_threshold(gender, grade):
    """获取一分钟跳绳100分对应的次数阈值"""
    standards = _load_standards()
    grade_key = str(grade)
    if grade_key not in standards:
        return None
    scoring = standards[grade_key].get('scoring', {})
    jr = scoring.get('一分钟跳绳', {})
    gender_key = 'male' if gender == '男' else 'female'
    return int(jr.get(gender_key, {}).get('100', 0))


def calc_jump_rope_bonus(count, gender, grade):
    """计算一分钟跳绳附加分

    国家学生体质健康标准（2014修订版）：
    一分钟跳绳为高优指标，学生成绩超过单项评分100分后，
    每多跳2个加1分，最高加20分。

    Returns:
        bonus (0-20 整数)
    """
    if count is None or count <= 0:
        return 0
    threshold = get_jump_rope_100_threshold(gender, grade)
    if threshold is None or count <= threshold:
        return 0
    bonus = int((count - threshold) // 2)
    return min(bonus, 20)


def apply_scores_to_student(student_data, grade):
    """一站式计算学生全部得分并原地回填到 student_data 字典"""
    h = student_data.get('height')
    w = student_data.get('weight')
    gender = student_data.get('gender', '男')
    
    if h is not None and w is not None:
        student_data['bmi'], student_data['bmi_grade'], student_data['bmi_score'] = \
            calc_bmi_score(h, w, gender, grade)
    else:
        student_data['bmi'], student_data['bmi_grade'], student_data['bmi_score'] = (None, '', 0)
    
    result = calc_total_score(student_data, grade)
    student_data['scores'] = result.get('item_scores', {})
    student_data['jump_rope_bonus'] = result.get('jump_rope_bonus', 0)
    student_data['total_score'] = result.get('total_score', 0)
    student_data['total_grade'] = result.get('total_grade', '')
    return student_data
