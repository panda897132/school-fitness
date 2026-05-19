"""数据管理 — JSON 文件持久化存储"""

import json
import os
import hashlib
from config import DATA_DIR, STUDENTS_FILE, CONFIG_FILE, GRADE_ITEMS


def _hash_password(password):
    """简单的密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


class DataManager:
    """学生数据和配置管理"""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(base_dir, DATA_DIR)
        self.students_path = os.path.join(base_dir, STUDENTS_FILE)
        self.config_path = os.path.join(base_dir, CONFIG_FILE)
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化默认数据
        self._init_defaults()
    
    def _init_defaults(self):
        """初始化默认数据文件"""
        if not os.path.exists(self.students_path):
            self._save_students({"classes": {}})
        
        if not os.path.exists(self.config_path):
            default_config = {
                "school_name": "诸葛镇中心小学",
                "users": {
                    "admin": _hash_password("admin123")
                }
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    # ---- 认证 ----
    def verify_login(self, username, password):
        """验证登录"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            stored_hash = users.get(username)
            if stored_hash and stored_hash == _hash_password(password):
                return True
            return False
        except Exception:
            return False
    
    def change_password(self, username, old_password, new_password):
        """修改密码"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            if users.get(username) != _hash_password(old_password):
                return False
            users[username] = _hash_password(new_password)
            config['users'] = users
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    # ---- 班级管理 ----
    def _load_students(self):
        try:
            with open(self.students_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"classes": {}}
    
    def _save_students(self, data):
        with open(self.students_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_all_classes(self):
        """获取所有班级"""
        data = self._load_students()
        return data.get('classes', {})
    
    def get_classes_by_grade(self, grade):
        """获取某年级的所有班级"""
        all_classes = self.get_all_classes()
        return {cid: cdata for cid, cdata in all_classes.items()
                if cdata.get('grade') == grade}
    
    def get_class(self, class_id):
        """获取单个班级"""
        all_classes = self.get_all_classes()
        return all_classes.get(str(class_id))
    
    def add_class(self, class_id, grade, class_name):
        """添加班级"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id in data.get('classes', {}):
            return False, "班级已存在"
        if 'classes' not in data:
            data['classes'] = {}
        data['classes'][class_id] = {
            'grade': grade,
            'name': class_name,
            'students': []
        }
        self._save_students(data)
        return True, "添加成功"
    
    def delete_class(self, class_id):
        """删除班级"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        del data['classes'][class_id]
        self._save_students(data)
        return True, "删除成功"
    
    # ---- 学生管理 ----
    def get_students(self, class_id):
        """获取班级的学生列表"""
        class_data = self.get_class(class_id)
        if class_data is None:
            return []
        return class_data.get('students', [])
    
    def add_student(self, class_id, student_data):
        """添加学生"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        # 生成学生ID: 班级编号 + 序号
        students = data['classes'][class_id].get('students', [])
        
        # 确保有id字段
        if 'id' not in student_data:
            # Auto-generate: class_id + student_number
            sid = student_data.get('student_number', str(len(students) + 1).zfill(2))
            student_data['id'] = f"{class_id}{sid}"
        
        students.append(student_data)
        data['classes'][class_id]['students'] = students
        self._save_students(data)
        return True, "添加成功"
    
    def update_student(self, class_id, student_id, student_data):
        """更新学生信息"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        students = data['classes'][class_id]['students']
        for i, s in enumerate(students):
            if s.get('id') == student_id:
                students[i].update(student_data)
                self._save_students(data)
                return True, "更新成功"
        return False, "学生不存在"
    
    def delete_student(self, class_id, student_id):
        """删除学生"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        students = data['classes'][class_id]['students']
        data['classes'][class_id]['students'] = [
            s for s in students if s.get('id') != student_id
        ]
        self._save_students(data)
        return True, "删除成功"
    
    def import_students(self, class_id, student_list):
        """批量导入学生（替换班级现有学生）"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            # Auto-create class if not exists
            grade = int(str(class_id)[0]) if len(str(class_id)) >= 2 else 1
            data.setdefault('classes', {})[class_id] = {
                'grade': grade,
                'name': f"{grade}年级{str(class_id)[-2:]}班",
                'students': []
            }
        
        data['classes'][class_id]['students'] = student_list
        self._save_students(data)
        return True, f"导入成功，共{len(student_list)}名学生"
    
    def get_statistics(self, grade=None, class_id=None):
        """获取统计信息"""
        all_classes = self.get_all_classes()
        
        students = []
        if class_id:
            cdata = all_classes.get(str(class_id))
            if cdata:
                students = cdata.get('students', [])
        elif grade:
            for cid, cdata in all_classes.items():
                if cdata.get('grade') == grade:
                    students.extend(cdata.get('students', []))
        else:
            for cid, cdata in all_classes.items():
                students.extend(cdata.get('students', []))
        
        total = len(students)
        if total == 0:
            return {
                'total': 0,
                '优秀': 0, '良好': 0, '及格': 0, '不及格': 0,
                '优秀率': 0, '良好率': 0, '及格率': 0, '不及格率': 0,
                'avg_score': 0,
                'students': []
            }
        
        counts = {'优秀': 0, '良好': 0, '及格': 0, '不及格': 0}
        total_score = 0
        scored_count = 0
        
        for s in students:
            grade_level = s.get('total_grade', '')
            if grade_level:
                counts[grade_level] = counts.get(grade_level, 0) + 1
            
            ts = s.get('total_score', 0) or 0
            if ts > 0:
                total_score += ts
                scored_count += 1
        
        avg = round(total_score / scored_count, 1) if scored_count > 0 else 0
        
        return {
            'total': total,
            '优秀': counts['优秀'],
            '良好': counts['良好'],
            '及格': counts['及格'],
            '不及格': counts['不及格'],
            '优秀率': round(counts['优秀'] / total * 100, 1),
            '良好率': round(counts['良好'] / total * 100, 1),
            '及格率': round((counts['优秀'] + counts['良好'] + counts['及格']) / total * 100, 1),
            '不及格率': round(counts['不及格'] / total * 100, 1),
            'avg_score': avg,
            'students': students
        }
