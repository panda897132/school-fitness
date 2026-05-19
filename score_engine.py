"""评分计算引擎 — 基于《国家学生体质健康标准（2014修订版）》"""

import json
import os
from config import DATA_DIR, STANDARDS_FILE, GRADE_LEVELS, CN_TO_NUM

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
    import re
    
    # Pattern: a < x ≤ b  or  a ≤ x ≤ b  etc.
    m = re.match(r'^([≤<]?)\s*([\d.]+)\s*[<≤]\s*x\s*[<≤]\s*([\d.]+)\s*([≤]?)$', s)
    if m:
        lo_sign = m.group(1)
        lo_val = float(m.group(2))
        hi_val = float(m.group(3))
        hi_sign = m.group(4)
        lo_inclusive = (lo_sign == '≤')
        hi_inclusive = (hi_sign == '≤')
        return lo_val, hi_val, lo_inclusive, hi_inclusive
    
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
    
    return None, None, False, False


def _bmi_in_range(bmi_val, lo, hi, lo_inclusive, hi_inclusive):
    """检查BMI值是否在范围内"""
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
    if height is None or weight is None or height <= 0:
        return None, None, 0
    
    height_m = height / 100.0
    bmi = round(weight / (height_m ** 2), 1)
    
    standards = _load_standards()
    grade_key = str(grade)
    
    if grade_key not in standards:
        return bmi, None, 0
    
    bmi_list = standards[grade_key].get('bmi', [])
    
    gender_key = 'male_range' if gender == '男' else 'female_range'
    
    # 查找匹配的BMI范围
    for entry in bmi_list:
        range_str = entry.get(gender_key)
        if range_str is None:
            continue
        lo, hi, lo_inc, hi_inc = _parse_bmi_range(range_str)
        if _bmi_in_range(bmi, lo, hi, lo_inc, hi_inc):
            grade_rank = entry.get('grade_rank', '')
            bmi_score = entry.get('bmi_score', 0) or 0
            return bmi, grade_rank, bmi_score
    
    # 如果没有匹配，检查极端情况
    # 低体重 (低于正常范围下限)
    # 肥胖 (高于正常范围上限)
    for entry in bmi_list:
        if entry.get('grade_rank') == '正常':
            range_str = entry.get(gender_key)
            if range_str:
                lo, hi, lo_inc, hi_inc = _parse_bmi_range(range_str)
                if lo is not None and bmi <= lo:
                    # 低体重
                    for e in bmi_list:
                        if e.get('grade_rank') == '低体重':
                            return bmi, '低体重', e.get('bmi_score', 80)
                    return bmi, '低体重', 80
                if hi is not None and bmi >= hi:
                    # 肥胖
                    for e in bmi_list:
                        if e.get('grade_rank') == '肥胖':
                            return bmi, '肥胖', e.get('bmi_score', 60)
                    return bmi, '肥胖', 60
            break
    
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
    import re
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
    
    # Determine direction: check if higher score → higher value or lower value
    if len(parsed) >= 2:
        first_val = parsed[0][1]
        last_val = parsed[-1][1]
        # For 肺活量/坐位体前屈/跳绳/仰卧起坐: higher value = higher score
        # For 50米跑/折返跑: lower value = higher score
        higher_is_better = first_val > last_val
    
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
    
    result = {'item_scores': {}}
    
    # Calculate BMI
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
