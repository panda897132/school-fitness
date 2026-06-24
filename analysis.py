"""三层分析引擎 — 班级分析/年级分析/全校分析

对标 Excel 模板《小学体测自动算分表(修改).xlsx》的分析体系
基于《国家学生体质健康标准（2014修订版）》
"""

from config import GRADE_NAMES, GRADE_ITEMS, ITEM_WEIGHTS


# ============================================================
#  工具函数
# ============================================================

def _is_valid_student(s):
    """判断学生数据是否完整有效：有性别+身高+体重+至少一个测试项目"""
    if not s.get('gender'):
        return False
    if s.get('height') is None or s.get('weight') is None:
        return False
    if s.get('height', 0) <= 0 or s.get('weight', 0) <= 0:
        return False
    # 至少有一个有效测试值
    tests = s.get('tests', {})
    if not tests:
        scores = s.get('scores', {})
        return any(v is not None and v > 0 for v in scores.values())
    return any(v is not None for v in tests.values())


def safe_rate(numerator, denominator):
    """安全除法，返回百分比字符串，除零返回0"""
    if denominator == 0:
        return 0
    return round(numerator / denominator * 100, 1)


def _count_distribution(students, key, categories):
    """统计某个 key 在 categories 中的分布
    
    Returns: {cat: count, ...} + effective_total (有该key的人数)
    """
    dist = {cat: 0 for cat in categories}
    effective = 0
    male_dist = {cat: 0 for cat in categories}
    female_dist = {cat: 0 for cat in categories}
    male_eff = 0
    female_eff = 0
    
    for s in students:
        val = s.get(key)
        if val is None or val == '':
            continue
        val = str(val)
        gender = s.get('gender', '男')
        effective += 1
        
        if val in dist:
            dist[val] += 1
        if val in male_dist:
            if gender == '男':
                male_dist[val] += 1
                male_eff += 1
            else:
                female_dist[val] += 1
                female_eff += 1
    
    return {
        'distribution': dist,
        'effective_total': effective,
        'male': {'distribution': male_dist, 'effective_total': male_eff},
        'female': {'distribution': female_dist, 'effective_total': female_eff},
    }


def _count_jump_rope_bonus(students):
    """统计跳绳附加分分布

    返回: {distribution: {0分|1-5分|6-10分|11-15分|16-20分: count},
            effective_total, avg_bonus, max_bonus,
            has_bonus_count, has_bonus_rate}
    """
    categories = ['0分', '1-5分', '6-10分', '11-15分', '16-20分']
    dist = {c: 0 for c in categories}
    total_bonus = 0
    max_bonus = 0
    has_bonus = 0
    effective = 0

    for s in students:
        if 'jump_rope_bonus' not in s:
            continue
        bonus = s.get('jump_rope_bonus', 0)
        if bonus is None or bonus == '':
            continue
        bonus = int(bonus)
        effective += 1
        total_bonus += bonus
        if bonus > max_bonus:
            max_bonus = bonus
        if bonus > 0:
            has_bonus += 1
        if bonus == 0:
            dist['0分'] += 1
        elif bonus <= 5:
            dist['1-5分'] += 1
        elif bonus <= 10:
            dist['6-10分'] += 1
        elif bonus <= 15:
            dist['11-15分'] += 1
        else:
            dist['16-20分'] += 1

    return {
        'distribution': dist,
        'effective_total': effective,
        'avg_bonus': round(total_bonus / effective, 1) if effective else 0,
        'max_bonus': max_bonus,
        'has_bonus_count': has_bonus,
        'has_bonus_rate': safe_rate(has_bonus, effective),
    }


def _count_item_grades(students, item_name, grade):
    """统计某项目的等级分布（单次遍历）

    对于BMI：等级为 正常/超重/低体重/肥胖
    对于测试项目：通过 scores[item_name] 映射到 优秀/良好/及格/不及格

    返回: {优秀/良好/及格/不及格: count, effective_total, excellence_rate}
    或者: {正常/超重/低体重/肥胖: count, effective_total, obesity_rate}
    """
    if item_name == 'BMI':
        categories = ['正常', '超重', '低体重', '肥胖']
    else:
        categories = ['优秀', '良好', '及格', '不及格']

    dist = {cat: 0 for cat in categories}
    male_dist = {cat: 0 for cat in categories}
    female_dist = {cat: 0 for cat in categories}
    effective = male_eff = female_eff = 0

    for s in students:
        if item_name == 'BMI':
            g = s.get('bmi_grade', '')
        else:
            sc = s.get('scores', {}).get(item_name)
            if sc is None or sc <= 0:
                continue
            if sc >= 90:
                g = '优秀'
            elif sc >= 80:
                g = '良好'
            elif sc >= 60:
                g = '及格'
            else:
                g = '不及格'

        if g in dist:
            dist[g] += 1
            effective += 1
            if s.get('gender') == '男':
                male_dist[g] += 1
                male_eff += 1
            else:
                female_dist[g] += 1
                female_eff += 1
    
    result = {
        'item_name': item_name,
        'distribution': dist,
        'effective_total': effective,
        'male': {'distribution': male_dist, 'effective_total': male_eff},
        'female': {'distribution': female_dist, 'effective_total': female_eff},
    }

    if item_name == 'BMI':
        result['obesity_rate'] = safe_rate(dist.get('肥胖', 0), effective)
        result['male']['obesity_rate'] = safe_rate(male_dist.get('肥胖', 0), male_eff)
        result['female']['obesity_rate'] = safe_rate(female_dist.get('肥胖', 0), female_eff)
    else:
        excellence = dist.get('优秀', 0) + dist.get('良好', 0)
        result['excellence_rate'] = safe_rate(excellence, effective)
        male_exc = male_dist.get('优秀', 0) + male_dist.get('良好', 0)
        female_exc = female_dist.get('优秀', 0) + female_dist.get('良好', 0)
        result['male']['excellence_rate'] = safe_rate(male_exc, male_eff)
        result['female']['excellence_rate'] = safe_rate(female_exc, female_eff)
    
    return result


# ============================================================
#  班级分析
# ============================================================

def analyze_class(dm, class_id):
    """班级综合分析 — 对标 Excel 模板 '班级分析' 工作表
    
    Args:
        dm: DataManager 实例
        class_id: 班级编号 (如 '401')
    
    Returns:
        dict 包含完整的班级分析数据
    """
    class_data = dm.get_class(str(class_id))
    if not class_data:
        return None
    
    grade = class_data.get('grade', 1)
    class_name = class_data.get('name', str(class_id))
    students = dm.get_students(str(class_id))
    
    # 基本信息
    total = len(students)
    male_count = sum(1 for s in students if s.get('gender') == '男')
    female_count = sum(1 for s in students if s.get('gender') == '女')
    valid_students = [s for s in students if _is_valid_student(s)]
    valid_count = len(valid_students)
    invalid_count = total - valid_count
    validity_rate = safe_rate(valid_count, total)
    
    # 各项目分析
    items = GRADE_ITEMS.get(grade, [])
    item_analyses = []
    
    # BMI 分析
    bmi_analysis = _count_item_grades(valid_students, 'BMI', grade)
    item_analyses.append(bmi_analysis)
    
    # 各测试项目分析
    for item_name in items:
        item_analysis = _count_item_grades(valid_students, item_name, grade)
        item_analyses.append(item_analysis)

    # 跳绳附加分分析
    jump_rope_bonus = _count_jump_rope_bonus(valid_students)

    # 总分等级分析 — 直接统计 total_grade 字段
    tg_result = _count_group_total_grade(valid_students)
    grade_dist = tg_result['distribution']
    grade_eff = tg_result['effective_total']
    total_excellence = grade_dist.get('优秀', 0) + grade_dist.get('良好', 0)
    
    # 各项目均值（单次遍历收集）
    item_averages = {}
    all_items = ['BMI'] + items
    for item_name in all_items:
        item_averages[item_name] = []

    heights = []
    weights = []

    for s in valid_students:
        h = s.get('height')
        w = s.get('weight')
        if h: heights.append(h)
        if w: weights.append(w)
        for item_name in all_items:
            if item_name == 'BMI':
                v = s.get('bmi')
            else:
                scores = s.get('scores', {})
                v = scores.get(item_name)
            if v is not None and v > 0:
                item_averages[item_name].append(v)

    # 计算均值
    for item_name in all_items:
        vals = item_averages[item_name]
        item_averages[item_name] = round(sum(vals) / len(vals), 1) if vals else 0
    
    return {
        'class_id': str(class_id),
        'class_name': class_name,
        'grade': grade,
        'grade_name': GRADE_NAMES[grade - 1] if 1 <= grade <= 6 else str(grade),
        
        # 基本信息
        'total': total,
        'male_count': male_count,
        'female_count': female_count,
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'validity_rate': validity_rate,
        
        # 各项目分析
        'items': item_analyses,
        
        # 跳绳附加分分析
        'jump_rope_bonus': jump_rope_bonus,
        
        # 总分等级分布
        'total_grade': {
            'distribution': grade_dist,
            'effective_total': grade_eff,
            'excellence_rate': safe_rate(total_excellence, grade_eff),
            'male': tg_result['male'],
            'female': tg_result['female'],
        },
        
        # 均值
        'averages': item_averages,
        'avg_height': round(sum(heights) / len(heights), 1) if heights else 0,
        'avg_weight': round(sum(weights) / len(weights), 1) if weights else 0,
        
        # 原始学生数据
        'students': students,
        'valid_students': valid_students,
    }


def _count_group_total_grade(students):
    """统计总分等级分布（含性别）"""
    categories = ['优秀', '良好', '及格', '不及格']
    dist = {cat: 0 for cat in categories}
    male_dist = {cat: 0 for cat in categories}
    female_dist = {cat: 0 for cat in categories}
    effective = 0
    male_eff = 0
    female_eff = 0
    
    for s in students:
        g = s.get('total_grade', '')
        if g in categories:
            dist[g] += 1
            effective += 1
            if s.get('gender') == '男':
                male_dist[g] += 1
                male_eff += 1
            else:
                female_dist[g] += 1
                female_eff += 1
    
    return {
        'distribution': dist,
        'effective_total': effective,
        'male': {'distribution': male_dist, 'effective_total': male_eff},
        'female': {'distribution': female_dist, 'effective_total': female_eff},
    }


# ============================================================
#  年级分析
# ============================================================

def analyze_grade(dm, grade):
    """年级综合分析 — 对标 Excel 模板 '年级分析' 工作表
    
    Args:
        dm: DataManager 实例
        grade: 年级数字 1-6
    
    Returns:
        dict 包含完整的年级分析数据
    """
    all_classes = dm.get_classes_by_grade(grade)
    if not all_classes:
        return None
    
    # 收集所有学生
    all_students = []
    for cid, cdata in all_classes.items():
        students = dm.get_students(cid)
        for s in students:
            s['_class_id'] = cid
            s['_class_name'] = cdata.get('name', cid)
        all_students.extend(students)
    
    valid_students = [s for s in all_students if _is_valid_student(s)]
    total = len(all_students)
    valid_count = len(valid_students)
    invalid_count = total - valid_count
    validity_rate = safe_rate(valid_count, total)
    
    male_count = sum(1 for s in all_students if s.get('gender') == '男')
    female_count = sum(1 for s in all_students if s.get('gender') == '女')
    
    # 总分等级分布
    tg_result = _count_group_total_grade(valid_students)
    grade_dist = tg_result['distribution']
    grade_eff = tg_result['effective_total']
    total_excellence = grade_dist.get('优秀', 0) + grade_dist.get('良好', 0)
    
    # BMI 年级汇总
    bmi_analysis = _count_item_grades(valid_students, 'BMI', grade)
    
    # 各测试项目汇总
    items = GRADE_ITEMS.get(grade, [])
    item_analyses = []
    for item_name in items:
        item_analyses.append(_count_item_grades(valid_students, item_name, grade))

    # 跳绳附加分分析
    jump_rope_bonus = _count_jump_rope_bonus(valid_students)
    
    # 逐班分析
    class_analyses = []
    for cid in sorted(all_classes.keys()):
        ca = analyze_class(dm, cid)
        if ca:
            class_analyses.append(ca)
    
    # 计算年级中位数/平均分用于排名
    class_rankings = []
    grade_scores = []
    grade_obesity = 0
    for ca in class_analyses:
        scores = [s.get('total_score', 0) or 0 for s in ca.get('valid_students', [])]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        grade_scores.extend(scores)
        class_rankings.append({
            'class_id': ca['class_id'],
            'class_name': ca['class_name'],
            'total': ca['total'],
            'valid_count': ca['valid_count'],
            'excellence_rate': ca['total_grade']['excellence_rate'],
            'avg_score': avg,
            'obesity_rate': ca['items'][0].get('obesity_rate', 0) if ca['items'] else 0,
        })
    grade_avg_score = round(sum(grade_scores) / len(grade_scores), 1) if grade_scores else 0
    
    # 按优良率排序
    class_rankings.sort(key=lambda x: x['excellence_rate'], reverse=True)
    
    return {
        'grade': grade,
        'grade_name': GRADE_NAMES[grade - 1] if 1 <= grade <= 6 else str(grade),
        'class_count': len(all_classes),
        
        # 总体
        'total': total,
        'male_count': male_count,
        'female_count': female_count,
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'validity_rate': validity_rate,
        
        # 总分等级
        'total_grade': {
            'distribution': grade_dist,
            'effective_total': grade_eff,
            'excellence_rate': safe_rate(total_excellence, grade_eff),
            'avg_score': grade_avg_score,
            'obesity_rate': bmi_analysis.get('obesity_rate', 0),
            'male': tg_result['male'],
            'female': tg_result['female'],
        },
        
        # BMI
        'bmi': bmi_analysis,
        
        # 跳绳附加分分析
        'jump_rope_bonus': jump_rope_bonus,
        
        # 各项目
        'items': item_analyses,
        
        # 逐班明细
        'class_analyses': class_analyses,
        
        # 班级排名
        'class_rankings': class_rankings,
        
        'students': all_students,
        'valid_students': valid_students,
    }


# ============================================================
#  全校分析
# ============================================================

def analyze_school(dm):
    """全校综合分析 — 对标 Excel 模板 '全校分析' 工作表
    
    Args:
        dm: DataManager 实例
    
    Returns:
        dict 包含完整的全校分析数据
    """
    all_classes = dm.get_all_classes()
    
    # 按年级汇总
    grade_summaries = []
    all_students = []
    
    for grade in range(1, 7):
        ga = analyze_grade(dm, grade)
        if ga and ga['total'] > 0:
            grade_summaries.append(ga)
            for s in ga['students']:
                s['_grade'] = grade
                s['_grade_name'] = GRADE_NAMES[grade - 1]
            all_students.extend(ga['students'])
    
    valid_students = [s for s in all_students if _is_valid_student(s)]
    total = len(all_students)
    male_count = sum(1 for s in all_students if s.get('gender') == '男')
    female_count = sum(1 for s in all_students if s.get('gender') == '女')
    valid_count = len(valid_students)
    invalid_count = total - valid_count
    
    # 全校总分等级
    tg_result = _count_group_total_grade(valid_students)
    grade_dist = tg_result['distribution']
    grade_eff = tg_result['effective_total']
    total_excellence = grade_dist.get('优秀', 0) + grade_dist.get('良好', 0)
    
    # 全校 BMI 分布
    school_bmi = _count_item_grades(valid_students, 'BMI', grade=1)

    # 各项目分析（用于导出）：收集所有年级的测试项目
    school_items = [school_bmi]
    all_test_items = set()
    for grade in range(1, 7):
        for item in GRADE_ITEMS.get(grade, []):
            all_test_items.add(item)
    for item_name in sorted(all_test_items):
        school_items.append(_count_item_grades(valid_students, item_name, grade=1))

    # 全校跳绳附加分分析
    school_jump_rope_bonus = _count_jump_rope_bonus(valid_students)

    # 各项目均值 (分年级、分性别)
    def _item_avg_across_grades(item_name, grade_summaries):
        """对某项目计算各年级各性别均值"""
        result = {}
        for gs in grade_summaries:
            g = gs['grade']
            grade_name = gs['grade_name']
            male_vals = []
            female_vals = []
            all_vals = []
            
            for s in gs.get('valid_students', []):
                if item_name == 'BMI':
                    v = s.get('bmi')
                elif item_name == '身高':
                    v = s.get('height')
                elif item_name == '体重':
                    v = s.get('weight')
                else:
                    scores = s.get('scores', {})
                    v = scores.get(item_name)
                
                if v is not None and v > 0:
                    all_vals.append(v)
                    if s.get('gender') == '男':
                        male_vals.append(v)
                    else:
                        female_vals.append(v)
            
            result[grade_name] = {
                'grade': g,
                'male_avg': round(sum(male_vals) / len(male_vals), 1) if male_vals else 0,
                'female_avg': round(sum(female_vals) / len(female_vals), 1) if female_vals else 0,
                'overall_avg': round(sum(all_vals) / len(all_vals), 1) if all_vals else 0,
            }
        return result
    
    # 所有需要统计均值的项目
    avg_items = ['身高', '体重', 'BMI', '肺活量', '50米跑', '坐位体前屈',
                 '一分钟跳绳', '仰卧起坐', '50*8折返跑']
    
    item_averages = {}
    for item_name in avg_items:
        item_averages[item_name] = _item_avg_across_grades(item_name, grade_summaries)
    
    # 各年级 BMI 分布
    bmi_by_grade = {}
    for gs in grade_summaries:
        vs = gs.get('valid_students', [])
        bmi_analysis = _count_item_grades(vs, 'BMI', gs['grade'])
        bmi_by_grade[gs['grade_name']] = bmi_analysis
    
    return {
        # 总体
        'total': total,
        'male_count': male_count,
        'female_count': female_count,
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'validity_rate': safe_rate(valid_count, total),
        'class_count': len(all_classes),
        
        # 总分等级
        'total_grade': {
            'distribution': grade_dist,
            'effective_total': grade_eff,
            'excellence_rate': safe_rate(total_excellence, grade_eff),
            'avg_score': round(sum(s.get('total_score', 0) or 0 for s in valid_students) / grade_eff, 1) if grade_eff else 0,
            'obesity_rate': school_bmi.get('obesity_rate', 0),
            'male': tg_result['male'],
            'female': tg_result['female'],
        },
        
        # 按年级汇总
        'grade_summaries': grade_summaries,
        
        # 各项目均值 (分年级分性别)
        'item_averages': item_averages,
        
        # 各年级 BMI 分布
        'bmi_by_grade': bmi_by_grade,
        
        # 全校 BMI
        'bmi': school_bmi,
        
        # 各项目分析（导出用）
        'items': school_items,
        
        # 全校跳绳附加分分析
        'jump_rope_bonus': school_jump_rope_bonus,
        
        'students': all_students,
        'valid_students': valid_students,
    }
