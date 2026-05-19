"""Excel 导入/导出"""

import os
import re
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from config import CN_TO_NUM, GRADE_ITEMS


def _find_column_index(ws, row_num, name_parts):
    """在工作表某行中查找包含指定文本的列索引
    
    Args:
        ws: 工作表
        row_num: 行号
        name_parts: 要匹配的文本片段列表
    """
    for col in range(1, ws.max_column + 1):
        cell_val = str(ws.cell(row=row_num, column=col).value or '')
        if all(part in cell_val for part in name_parts):
            return col
    return None


def _is_valid_value(val):
    """检查是否为有效值（排除错误值和空值）"""
    if val is None:
        return False
    s = str(val).strip()
    if s == '' or s.startswith('#') or s == 'None':
        return False
    return True


def _parse_run_time(raw):
    """解析跑步时间值
    
    支持三种格式:
    - float (如 1.43 表示 1分43秒)
    - str 时间格式 (如 "1'43")
    - 纯秒数
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        # 检测分钟.秒格式：1.0~10.0 区间，小数部分可解释为秒(0-59)
        if 0.5 <= v < 10.0:
            minutes = int(v)
            seconds_part = round((v - minutes) * 100)
            if 0 <= seconds_part < 60:
                return minutes * 60 + seconds_part
        return v
    # 字符串格式
    raw_str = str(raw).strip()
    m = re.match(r"(\d+)'(\d+)", raw_str)
    if m:
        return float(m.group(1)) * 60 + float(m.group(2))
    try:
        return float(raw_str)
    except (ValueError, TypeError):
        return 0


def import_from_excel(filepath, grade_hint=None, class_prefix=None):
    """从Excel导入学生数据
    
    兼容两种格式：
    1. 旧模板格式：每个年级一个工作表（一年级/二年级/.../六年级）
    2. 新格式：单工作表"学生成绩"，表头含"总成绩"
    
    参数:
        grade_hint: 年级提示（新格式下优先使用，否则自动推断）
        class_prefix: 班级编号前缀（新格式下使用，否则自动生成）
    
    返回:
        {
            "success": True/False,
            "message": "描述",
            "data": {"classes": {"101": {"grade": 1, "name": "一(1)班", "students": [...]}}}
        }
    """
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
    except Exception as e:
        return {"success": False, "message": f"无法打开文件: {e}", "data": None}
    
    grade_sheet_names = {
        '一年级': 1, '二年级': 2, '三年级': 3,
        '四年级': 4, '五年级': 5, '六年级': 6
    }
    
    # 检测是否有旧格式的年级工作表
    has_old_format = any(sn in grade_sheet_names for sn in wb.sheetnames)
    
    if has_old_format:
        return _import_old_format(wb, grade_sheet_names)
    
    # 尝试新格式：检测不含"年级"且含"总成绩"的工作表
    for sheet_name in wb.sheetnames:
        if '年级' in sheet_name:
            continue
        ws = wb[sheet_name]
        header_row = _detect_new_format_header(ws)
        if header_row is not None:
            result = _import_new_format(ws, header_row, grade_hint, class_prefix)
            wb.close()
            return result
    
    wb.close()
    return {"success": False, "message": "未识别的文件格式，请使用模板或新格式Excel", "data": None}


def _detect_new_format_header(ws):
    """检测新格式表头行（含'姓名'和'总成绩'），返回行号或None"""
    for row in range(1, min(ws.max_row + 1, 5)):
        has_name = False
        has_total_score = False
        for col in range(1, ws.max_column + 1):
            val = str(ws.cell(row=row, column=col).value or '').strip()
            if '姓名' in val:
                has_name = True
            if '总成绩' in val:
                has_total_score = True
        if has_name and has_total_score:
            return row
    return None


def _import_new_format(ws, header_row, grade_hint, class_prefix):
    """从新格式工作表导入数据
    
    新格式列结构: 姓名|性别|身高|体重|BMI|成绩|肺活量|成绩|50米跑|成绩|...
    每个测试项目后面跟一个"成绩"列(评分)，我们跳过评分列。
    """
    from config import GRADE_ITEMS, NUM_TO_CN
    
    # 建立列索引映射
    col_map = {}
    detected_items = set()
    
    for col in range(1, ws.max_column + 1):
        hdr = str(ws.cell(row=header_row, column=col).value or '').strip()
        if hdr == '成绩' or hdr == '总成绩' or hdr == 'BMI':
            continue
        if '姓名' in hdr:
            col_map['name'] = col
        elif '性别' in hdr:
            col_map['gender'] = col
        elif hdr == '身高':
            col_map['height'] = col
        elif hdr == '体重':
            col_map['weight'] = col
        elif '肺活量' in hdr:
            col_map['肺活量'] = col
            detected_items.add('肺活量')
        elif ('50米' in hdr and '50×8' not in hdr and '50*8' not in hdr
              and '50x8' not in hdr and '50X8' not in hdr and '往返' not in hdr):
            col_map['50米跑'] = col
            detected_items.add('50米跑')
        elif '50×8' in hdr or '50*8' in hdr or '50x8' in hdr or '50X8' in hdr or '往返跑' in hdr:
            col_map['50*8折返跑'] = col
            detected_items.add('50*8折返跑')
        elif '坐位' in hdr:
            col_map['坐位体前屈'] = col
            detected_items.add('坐位体前屈')
        elif '跳绳' in hdr:
            col_map['一分钟跳绳'] = col
            detected_items.add('一分钟跳绳')
        elif '仰卧' in hdr:
            col_map['仰卧起坐'] = col
            detected_items.add('仰卧起坐')
    
    # 推断年级
    if grade_hint:
        grade = grade_hint
    elif '50*8折返跑' in detected_items:
        grade = 5
    elif '仰卧起坐' in detected_items:
        grade = 3
    else:
        grade = 1
    
    # 自动生成班级编号
    if class_prefix:
        cid_prefix = str(class_prefix).strip()
    else:
        cid_prefix = f"{grade}01"
    
    # 班级名称
    cn_grade = NUM_TO_CN.get(grade, str(grade))
    class_suffix = cid_prefix[-2:] if len(cid_prefix) >= 2 else cid_prefix
    class_name = f"{cn_grade}({class_suffix})班"
    
    # 读取数据
    students = []
    student_num = 0
    
    for row in range(header_row + 1, ws.max_row + 1):
        name_cell = ws.cell(row=row, column=col_map.get('name', 0)).value
        if not _is_valid_value(name_cell):
            continue
        
        student_num += 1
        student_number = str(student_num).zfill(2)
        
        # 性别映射: "1"→"男", "2"→"女"
        gender_val = str(ws.cell(row=row, column=col_map.get('gender', 0)).value or '').strip()
        if gender_val == '1' or '男' in gender_val:
            gender = '男'
        elif gender_val == '2' or '女' in gender_val:
            gender = '女'
        else:
            gender = '男'
        
        # 身高
        height = None
        if 'height' in col_map:
            hv = ws.cell(row=row, column=col_map['height']).value
            if _is_valid_value(hv):
                try:
                    height = float(hv)
                except (ValueError, TypeError):
                    height = None
        
        # 体重
        weight = None
        if 'weight' in col_map:
            wv = ws.cell(row=row, column=col_map['weight']).value
            if _is_valid_value(wv):
                try:
                    weight = float(wv)
                except (ValueError, TypeError):
                    weight = None
        
        # 测试项目值
        tests = {}
        for item_name in GRADE_ITEMS.get(grade, []):
            col_idx = col_map.get(item_name)
            if col_idx:
                raw = ws.cell(row=row, column=col_idx).value
                if _is_valid_value(raw):
                    if item_name == '50*8折返跑':
                        tests[item_name] = _parse_run_time(raw)
                    else:
                        try:
                            tests[item_name] = float(raw)
                        except (ValueError, TypeError):
                            raw_str = str(raw).strip()
                            tests[item_name] = _parse_run_time(raw_str)
                else:
                    tests[item_name] = None
            else:
                tests[item_name] = None
        
        student = {
            'id': f"{cid_prefix}{student_number}",
            'name': str(name_cell).strip(),
            'student_number': student_number,
            'student_code': '',
            'gender': gender,
            'height': height,
            'weight': weight,
            'bmi': None,
            'tests': tests,
            'scores': {},
            'total_score': 0,
            'total_grade': ''
        }
        students.append(student)
    
    return {
        "success": True,
        "message": f"导入完成：成功 {len(students)} 条",
        "data": {
            "classes": {
                cid_prefix: {
                    "grade": grade,
                    "name": class_name,
                    "students": students
                }
            }
        }
    }


def _import_old_format(wb, grade_sheet_names):
    """从旧模板格式导入数据"""
    all_classes = {}
    total_imported = 0
    total_skipped = 0
    
    for sheet_name in wb.sheetnames:
        if sheet_name not in grade_sheet_names:
            continue
        
        grade = grade_sheet_names[sheet_name]
        ws = wb[sheet_name]
        
        # 查找表头行 (包含 "姓名" 的行)
        header_row = None
        for row in range(1, min(ws.max_row + 1, 10)):
            for col in range(1, ws.max_column + 1):
                val = str(ws.cell(row=row, column=col).value or '')
                if '姓名' in val and ('学号' in val or _find_column_index(ws, row, ['学号'])):
                    header_row = row
                    break
            if header_row:
                break
        
        if header_row is None:
            # 尝试更宽松的匹配
            for row in range(1, min(ws.max_row + 1, 10)):
                has_name = False
                has_number = False
                for col in range(1, ws.max_column + 1):
                    val = str(ws.cell(row=row, column=col).value or '')
                    if '姓名' in val:
                        has_name = True
                    if '学号' in val or '班级' in val:
                        has_number = True
                if has_name and has_number:
                    header_row = row
                    break
        
        if header_row is None:
            continue
        
        # 建立列索引映射
        col_map = {}
        for col in range(1, ws.max_column + 1):
            hdr = str(ws.cell(row=header_row, column=col).value or '').strip()
            if '班级' in hdr:
                col_map['class_id'] = col
            elif '学号' in hdr:
                col_map['student_number'] = col
            elif '姓名' in hdr:
                col_map['name'] = col
            elif '学籍' in hdr:
                col_map['student_code'] = col
            elif '性别' in hdr:
                col_map['gender'] = col
            elif '身高' in hdr:
                col_map['height'] = col
            elif '体重' in hdr:
                col_map['weight'] = col
            elif '肺活量' in hdr:
                col_map['肺活量'] = col
            elif '50米' in hdr and '50*8' not in hdr and '50×8' not in hdr and '50x8' not in hdr and '50X8' not in hdr:
                col_map['50米跑'] = col
            elif '50*8' in hdr or '50×8' in hdr or '50x8' in hdr or '折返' in hdr:
                col_map['50*8折返跑'] = col
            elif '坐位' in hdr:
                col_map['坐位体前屈'] = col
            elif '跳绳' in hdr:
                col_map['一分钟跳绳'] = col
            elif '仰卧' in hdr:
                col_map['仰卧起坐'] = col
        
        # 兼容：可能列名为BMI格式
        if 'BMI(15%)' in col_map:
            col_map['bmi_col'] = col_map.pop('BMI(15%)')
        
        # 读取数据
        students_by_class = {}
        
        for row in range(header_row + 1, ws.max_row + 1):
            name_cell = ws.cell(row=row, column=col_map.get('name', 3)).value
            if not _is_valid_value(name_cell):
                continue  # 空行或错误行跳过
            
            try:
                # 班级编号
                if 'class_id' in col_map:
                    class_id = str(ws.cell(row=row, column=col_map['class_id']).value or '').strip()
                    if '.' in class_id:
                        class_id = str(int(float(class_id)))
                else:
                    class_id = f"{grade}01"
                
                # 如果class_id只有2位，补上年级前缀
                if len(class_id) == 2:
                    class_id = f"{grade}{class_id}"
                
                # 学号
                student_number = ''
                if 'student_number' in col_map:
                    sv = ws.cell(row=row, column=col_map['student_number']).value
                    if sv is not None:
                        student_number = str(int(float(str(sv)))) if '.' in str(sv) else str(sv)
                
                # 姓名
                name = str(name_cell).strip()
                
                # 学籍号
                student_code = ''
                if 'student_code' in col_map:
                    sc = ws.cell(row=row, column=col_map['student_code']).value
                    student_code = str(sc).strip() if sc else ''
                
                # 性别
                gender_val = str(ws.cell(row=row, column=col_map.get('gender', 5)).value or '').strip()
                gender = '男' if '男' in gender_val else '女'
                
                # 身高
                height = None
                if 'height' in col_map:
                    hv = ws.cell(row=row, column=col_map['height']).value
                    if _is_valid_value(hv):
                        try:
                            height = float(hv)
                        except (ValueError, TypeError):
                            height = None
                
                # 体重
                weight = None
                if 'weight' in col_map:
                    wv = ws.cell(row=row, column=col_map['weight']).value
                    if _is_valid_value(wv):
                        try:
                            weight = float(wv)
                        except (ValueError, TypeError):
                            weight = None
                
                # 测试项目值
                tests = {}
                for item_name in GRADE_ITEMS.get(grade, []):
                    col_idx = col_map.get(item_name)
                    if col_idx:
                        raw = ws.cell(row=row, column=col_idx).value
                        if _is_valid_value(raw):
                            if item_name == '50*8折返跑':
                                tests[item_name] = _parse_run_time(raw)
                            else:
                                try:
                                    tests[item_name] = float(raw)
                                except (ValueError, TypeError):
                                    # 可能是时间格式如 1'36
                                    raw_str = str(raw).strip()
                                    tests[item_name] = _parse_run_time(raw_str)
                        else:
                            tests[item_name] = None
                    else:
                        tests[item_name] = None
                
                student = {
                    'id': f"{class_id}{student_number}",
                    'name': name,
                    'student_number': student_number,
                    'student_code': student_code,
                    'gender': gender,
                    'height': height,
                    'weight': weight,
                    'bmi': None,
                    'tests': tests,
                    'scores': {},
                    'total_score': 0,
                    'total_grade': ''
                }
                
                if class_id not in students_by_class:
                    students_by_class[class_id] = {
                        'grade': grade,
                        'name': f"{grade}年级{class_id[-2:]}班",
                        'students': []
                    }
                
                students_by_class[class_id]['students'].append(student)
                total_imported += 1
            except Exception:
                total_skipped += 1
                continue
        
        all_classes.update(students_by_class)
    
    wb.close()
    
    return {
        "success": True,
        "message": f"导入完成：成功 {total_imported} 条，跳过 {total_skipped} 条",
        "data": {"classes": all_classes}
    }


def _to_time_str(seconds):
    """将秒数转换为 1'36 格式"""
    if seconds is None or seconds == 0:
        return ''
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}'{s:02d}"


def export_statistics_report(dm, output_path, scope='全校', grade=None, class_id=None):
    """导出统计分析报告
    
    Args:
        dm: DataManager 实例
        output_path: 输出文件路径
        scope: '全校'/'年级'/'班级'
        grade: 年级数字 (scope='年级'时)
        class_id: 班级编号 (scope='班级'时)
    """
    try:
        wb = openpyxl.Workbook()
        
        # 标题样式
        title_font = Font(name='微软雅黑', size=14, bold=True)
        header_font = Font(name='微软雅黑', size=10, bold=True)
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_font_white = Font(name='微软雅黑', size=10, bold=True, color='FFFFFF')
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        center_align = Alignment(horizontal='center', vertical='center')
        
        # --- 学生明细表 ---
        ws_detail = wb.active
        ws_detail.title = '学生明细'
        
        # 获取数据
        stats = dm.get_statistics(grade=grade, class_id=class_id)
        
        # 标题
        title_map = {
            '全校': '全校',
            '年级': f'{grade}年级',
            '班级': f'{class_id}班' if class_id else ''
        }
        ws_detail.merge_cells('A1:R1')
        ws_detail.cell(row=1, column=1, value=f'诸葛镇中心小学 — 学生体质健康数据 ({title_map[scope]})').font = title_font
        ws_detail.cell(row=1, column=1).alignment = center_align
        
        # 表头 (与模板一致)
        headers = [
            '班级编号', '学号', '姓名', '学籍号', '性别',
            '身高(cm)', '体重(kg)', 'BMI', 'BMI等级', 'BMI得分',
            '肺活量', '50米跑', '坐位体前屈', '一分钟跳绳', '仰卧起坐',
            '50*8折返跑', '总分', '等级'
        ]
        
        for ci, h in enumerate(headers, 1):
            cell = ws_detail.cell(row=2, column=ci, value=h)
            cell.font = header_font_white
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = border
        
        # 数据行
        row = 3
        for s in stats['students']:
            data_row = [
                s.get('class_id', '') if s.get('class_id') else (class_id or ''),
                s.get('student_number', ''),
                s.get('name', ''),
                s.get('student_code', ''),
                s.get('gender', ''),
                s.get('height', ''),
                s.get('weight', ''),
                s.get('bmi', ''),
                s.get('bmi_grade', ''),
                s.get('bmi_score', ''),
                s.get('tests', {}).get('肺活量', ''),
                s.get('tests', {}).get('50米跑', ''),
                s.get('tests', {}).get('坐位体前屈', ''),
                s.get('tests', {}).get('一分钟跳绳', ''),
                s.get('tests', {}).get('仰卧起坐', ''),
                _to_time_str(s.get('tests', {}).get('50*8折返跑')),
                s.get('total_score', ''),
                s.get('total_grade', '')
            ]
            for ci, val in enumerate(data_row, 1):
                cell = ws_detail.cell(row=row, column=ci, value=val if val is not None else '')
                cell.border = border
                cell.alignment = center_align
            row += 1
        
        # 调整列宽
        for ci in range(1, len(headers) + 1):
            ws_detail.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = 12
        
        # --- 统计汇总表 ---
        ws_summary = wb.create_sheet('统计汇总')
        
        ws_summary.merge_cells('A1:D1')
        ws_summary.cell(row=1, column=1, value=f'诸葛镇中心小学 — 统计分析 ({title_map[scope]})').font = title_font
        
        summary_data = [
            ('总人数', stats['total']),
            ('平均分', stats['avg_score']),
            ('', ''),
            ('等级', '人数', '占比', ''),
            ('优秀', stats['优秀'], f"{stats['优秀率']}%", f"(90-100分)"),
            ('良好', stats['良好'], f"{stats['良好率']}%", f"(80-89分)"),
            ('及格', stats['及格'], f"{stats['及格率']}%", f"(60-79分)"),
            ('不及格', stats['不及格'], f"{stats['不及格率']}%", f"(<60分)"),
        ]
        
        for ri, (label, *vals) in enumerate(summary_data, 2):
            ws_summary.cell(row=ri, column=1, value=label).font = header_font
            for vi, v in enumerate(vals, 2):
                ws_summary.cell(row=ri, column=vi, value=v)
        
        wb.save(output_path)
        wb.close()
        return True, f"报告已导出到: {output_path}"
    
    except Exception as e:
        return False, f"导出失败: {str(e)}"
