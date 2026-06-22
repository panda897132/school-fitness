"""数据管理 — JSON 文件持久化存储"""

import json
import os
import sys
import hashlib
import secrets
import shutil
import threading
import logging
from datetime import datetime
from config import DATA_DIR, STUDENTS_FILE, CONFIG_FILE, GRADE_ITEMS
from utils import compute_grade_distribution

# 审计日志：记录所有关键操作
_audit_logger = logging.getLogger('audit')
_audit_logger.setLevel(logging.INFO)
_audit_handler = None


def _get_audit_handler():
    """延迟初始化审计日志 handler（等 DATA_DIR 准备好）"""
    global _audit_handler
    if _audit_handler is None:
        # PyInstaller 冻结 EXE 中 __file__ 指向临时目录，使用 sys.executable 替代
        if getattr(sys, 'frozen', False):
            _app_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            _app_dir = os.path.dirname(os.path.abspath(__file__))
        # 不可写时回退到用户数据目录（如 Program Files 场景）
        if not os.access(_app_dir, os.W_OK):
            _app_dir = os.path.join(
                os.environ.get('APPDATA', os.path.expanduser('~')),
                'SchoolFitness',
            )
        log_dir = os.path.join(_app_dir, 'data')
        os.makedirs(log_dir, exist_ok=True)
        _audit_handler = logging.FileHandler(
            os.path.join(log_dir, 'audit.log'),
            encoding='utf-8'
        )
        os.chmod(os.path.join(log_dir, 'audit.log'), 0o600)
        _audit_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        _audit_logger.addHandler(_audit_handler)
    return _audit_handler


def _audit(message):
    """写入审计日志"""
    _get_audit_handler()
    _audit_logger.info(message)


PBKDF2_ITERATIONS = 600000


def _hash_password(password, salt=None):
    """带盐 PBKDF2-SHA256 密码哈希（含迭代次数版本号）"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"{salt}${PBKDF2_ITERATIONS}${h.hex()}"


def _verify_and_upgrade_password(stored_hash, password, upgrade_callback=None):
    """验证密码，自动处理三种哈希格式并升级

    支持格式:
      v2: salt${iterations}${hexhash}   (当前，含迭代次数)
      v1: salt${hexhash}                (旧版 PBKDF2，假定 100000 次)
      v0: hexhash                       (旧版无盐 SHA256)

    Returns:
        (bool, str|None) — (验证是否通过, 新哈希(仅升级时非None))
    """
    if '$' in stored_hash:
        parts = stored_hash.split('$')
        salt = parts[0]
        if len(parts) == 3:
            iterations = int(parts[1])
            stored_hex = parts[2]
        else:
            iterations = 100000
            stored_hex = parts[1]
        computed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
        if secrets.compare_digest(computed.hex(), stored_hex):
            if iterations < PBKDF2_ITERATIONS:
                new_hash = _hash_password(password)
                if upgrade_callback:
                    upgrade_callback(new_hash)
                return True, new_hash
            return True, None
        return False, None
    else:
        if stored_hash == hashlib.sha256(password.encode()).hexdigest():
            new_hash = _hash_password(password)
            if upgrade_callback:
                upgrade_callback(new_hash)
            return True, new_hash
        return False, None


def _verify_password(stored_hash, password):
    """验证密码（兼容旧版无盐 SHA256 格式）"""
    ok, _ = _verify_and_upgrade_password(stored_hash, password)
    return ok


class DataManager:
    """学生数据和配置管理"""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            # PyInstaller 冻结 EXE 中 __file__ 指向临时目录，使用 sys.executable 替代
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            # 不可写时回退到用户数据目录（如 Program Files 场景）
            if not os.access(base_dir, os.W_OK):
                base_dir = os.path.join(
                    os.environ.get('APPDATA', os.path.expanduser('~')),
                    'SchoolFitness',
                )
        self.data_dir = os.path.join(base_dir, DATA_DIR)
        self.students_path = os.path.join(base_dir, STUDENTS_FILE)
        self.config_path = os.path.join(base_dir, CONFIG_FILE)
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.chmod(self.data_dir, 0o700)  # 数据目录仅 owner 可访问
        
        # 惰性缓存：首次加载后缓存，写操作同步更新，避免重复读盘
        self._students_cache = None
        # 写入锁，防止并发写冲突
        self._write_lock = threading.Lock()
    
    @staticmethod
    def _atomic_write(path, data):
        """原子写入 JSON 文件：tmp → fsync → replace → chmod"""
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    
    def _write_config(self, config):
        """带锁的配置原子写入"""
        with self._write_lock:
            self._atomic_write(self.config_path, config)
    
    def _write_students(self, data):
        """带锁、带备份的学生数据原子写入"""
        with self._write_lock:
            if os.path.exists(self.students_path):
                try:
                    shutil.copy2(self.students_path, self.students_path + '.bak')
                except OSError:
                    pass
            self._atomic_write(self.students_path, data)
        
        # 初始化默认数据
        self._init_defaults()
        # 修复已有文件的权限
        self._fix_permissions()
        # 检测并标记需要迁移的旧版密码哈希
        self._migrate_passwords()
    
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
            self._write_config(default_config)
    
    def _fix_permissions(self):
        """修复已有数据文件的权限（仅 owner 可读写）"""
        sensitive_files = [
            self.config_path,
            self.students_path,
            self.students_path + '.bak',
        ]
        audit_log = os.path.join(self.data_dir, 'audit.log')
        if os.path.exists(audit_log):
            sensitive_files.append(audit_log)
        
        for path in sensitive_files:
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
    
    # ---- 密码迁移 ----
    def _migrate_passwords(self):
        """检测旧版 SHA-256（无盐）密码哈希，标记需强制重置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            flagged = 0
            for username, stored_hash in list(users.items()):
                if '$' not in stored_hash:
                    config.setdefault('password_reset_required', {})[username] = True
                    flagged += 1
            if flagged:
                self._write_config(config)
                _audit(f"密码迁移: {flagged}个用户的旧版哈希已标记需重置")
        except Exception as e:
            logging.exception("密码迁移失败: %s", e)
    
    def verify_login(self, username, password):
        """验证登录（检测到旧格式SHA256自动升级为PBKDF2）
        
        Returns: bool — True 表示验证通过（但可能需要强制重置密码）
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            stored_hash = users.get(username)
            if not stored_hash:
                _audit(f"登录失败: {username} (用户不存在)")
                return False
            
            def _do_upgrade(new_hash):
                """升级回调：写回新哈希到配置文件"""
                users[username] = new_hash
                if 'password_reset_required' in config:
                    config['password_reset_required'].pop(username, None)
                config['users'] = users
                self._write_config(config)
                _audit(f"密码哈希自动升级: {username} SHA256→PBKDF2-SHA256")
            
            ok, upgraded = _verify_and_upgrade_password(stored_hash, password, _do_upgrade)
            if ok:
                _audit(f"登录成功: {username}")
                return True
            _audit(f"登录失败: {username} (密码错误)")
            return False
        except Exception:
            _audit(f"登录异常: {username}")
            return False
    
    def password_reset_required(self, username):
        """检查用户是否需要强制重置密码（旧版哈希已标记）"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('password_reset_required', {}).get(username, False)
        except Exception:
            logging.exception("检查密码重置标记失败")
            return False
    
    def reset_password_forced(self, username, new_password, current_password=None):
        """强制重置密码（旧版哈希用户或忘记密码场景）
        
        current_password 为空时直接重置（跳过旧密码验证），
        提供时验证旧密码后再更新。
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            if current_password:
                stored_hash = users.get(username)
                if not stored_hash or not _verify_password(stored_hash, current_password):
                    return False, "当前密码错误"
            users[username] = _hash_password(new_password)
            config['users'] = users
            if 'password_reset_required' in config:
                config['password_reset_required'].pop(username, None)
            self._write_config(config)
            _audit(f"密码强制重置: {username}")
            return True, "密码已更新"
        except Exception:
            _audit(f"密码强制重置异常: {username}")
            return False, "重置失败"
    
    def change_password(self, username, old_password, new_password):
        """修改密码"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            users = config.get('users', {})
            stored_hash = users.get(username)
            if not stored_hash or not _verify_password(stored_hash, old_password):
                _audit(f"密码修改失败: {username} (旧密码错误)")
                return False
            users[username] = _hash_password(new_password)
            config['users'] = users
            self._write_config(config)
            _audit(f"密码修改成功: {username}")
            return True
        except Exception as e:
            _audit(f"密码修改异常: {username} ({e})")
            return False
    
    # ---- 班级管理 ----
    def _load_students(self):
        if self._students_cache is None:
            try:
                with open(self.students_path, 'r', encoding='utf-8') as f:
                    self._students_cache = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                bak = self.students_path + '.bak'
                if os.path.exists(bak):
                    with open(bak, 'r', encoding='utf-8') as f:
                        self._students_cache = json.load(f)
                else:
                    self._students_cache = {"classes": {}}
        return self._students_cache
    
    def _save_students(self, data):
        self._students_cache = data
        self._write_students(data)

    def flush(self):
        """手动刷新缓存（从磁盘重新加载）"""
        self._students_cache = None
    
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
            'test_rounds': [{'date': '', 'students': []}],
            'current_round': 0
        }
        self._save_students(data)
        _audit(f"添加班级: {class_id} ({class_name}, {grade}年级)")
        return True, "添加成功"
    
    def delete_class(self, class_id):
        """删除班级"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        cname = data['classes'][class_id].get('name', class_id)
        del data['classes'][class_id]
        self._save_students(data)
        _audit(f"删除班级: {class_id} ({cname})")
        return True, "删除成功"
    
    # ---- 测试轮次 ----
    @staticmethod
    def _migrate_class(cdata):
        """将旧格式班级数据迁移到测试轮次格式"""
        if 'test_rounds' not in cdata:
            old_students = cdata.pop('students', [])
            cdata['test_rounds'] = [{
                'date': '',
                'students': old_students
            }]
            cdata['current_round'] = 0
    
    def _get_round_students(self, cdata):
        """获取当前轮次的学生列表（自动迁移旧格式）"""
        self._migrate_class(cdata)
        ridx = cdata.get('current_round', 0)
        rounds = cdata.get('test_rounds', [])
        if 0 <= ridx < len(rounds):
            return rounds[ridx].get('students', [])
        return []
    
    def _set_round_students(self, data, class_id, students):
        """设置当前轮次的学生列表"""
        cdata = data['classes'][str(class_id)]
        self._migrate_class(cdata)
        ridx = cdata.get('current_round', 0)
        rounds = cdata.get('test_rounds', [])
        if 0 <= ridx < len(rounds):
            rounds[ridx]['students'] = students
    
    def get_test_rounds(self, class_id):
        """获取班级的所有测试轮次"""
        cdata = self.get_class(class_id)
        if not cdata:
            return []
        self._migrate_class(cdata)
        return cdata.get('test_rounds', [])
    
    def add_test_round(self, class_id, date=''):
        """为班级添加新测试轮次"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        cdata = data['classes'][class_id]
        self._migrate_class(cdata)
        cdata.setdefault('test_rounds', []).append({
            'date': date,
            'students': []
        })
        cdata['current_round'] = len(cdata['test_rounds']) - 1
        self._save_students(data)
        _audit(f"新增测试轮次: {class_id}, 第{cdata['current_round']+1}次")
        return True, f"已添加第{cdata['current_round']+1}次测试"
    
    def delete_test_round(self, class_id, round_index):
        """删除指定的测试轮次"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        cdata = data['classes'][class_id]
        self._migrate_class(cdata)
        rounds = cdata.get('test_rounds', [])
        if not rounds or round_index >= len(rounds):
            return False, "轮次不存在"
        if len(rounds) <= 1:
            return False, "至少保留一个测试轮次"
        del rounds[round_index]
        if cdata.get('current_round', 0) >= len(rounds):
            cdata['current_round'] = len(rounds) - 1
        self._save_students(data)
        _audit(f"删除测试轮次: {class_id}, 第{round_index+1}次")
        return True, f"已删除第{round_index+1}次测试"
    
    def set_current_test_round(self, class_id, round_index):
        """切换当前测试轮次"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        cdata = data['classes'][class_id]
        self._migrate_class(cdata)
        rounds = cdata.get('test_rounds', [])
        if round_index < 0 or round_index >= len(rounds):
            return False, "无效轮次"
        cdata['current_round'] = round_index
        self._save_students(data)
        return True, f"已切换到第{round_index+1}次测试"
    
    # ---- 学生管理 ----
    def get_students(self, class_id):
        """获取班级当前轮次的学生列表"""
        class_data = self.get_class(class_id)
        if class_data is None:
            return []
        return self._get_round_students(class_data)
    
    def add_student(self, class_id, student_data):
        """添加学生"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        students = self._get_round_students(data['classes'][class_id])
        
        if 'id' not in student_data:
            sid = student_data.get('student_number', str(len(students) + 1).zfill(2))
            student_data['id'] = f"{class_id}{sid}"
        
        for existing in students:
            if existing.get('id') == student_data.get('id'):
                return False, "学生ID已存在，请勿重复添加"
        
        students.append(student_data)
        self._set_round_students(data, class_id, students)
        self._save_students(data)
        _audit(f"添加学生: {class_id}/{student_data.get('name', '?')} (ID: {student_data.get('id', '?')})")
        return True, "添加成功"
    
    def update_student(self, class_id, student_id, student_data):
        """更新学生信息"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        students = self._get_round_students(data['classes'][class_id])
        for i, s in enumerate(students):
            if s.get('id') == student_id:
                students[i].update(student_data)
                self._set_round_students(data, class_id, students)
                self._save_students(data)
                _audit(f"更新学生: {class_id}/{student_data.get('name', student_id)}")
                return True, "更新成功"
        return False, "学生不存在"
    
    def delete_student(self, class_id, student_id):
        """删除学生"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            return False, "班级不存在"
        
        students = self._get_round_students(data['classes'][class_id])
        deleted_name = next((s.get('name', student_id) for s in students if s.get('id') == student_id), student_id)
        filtered = [s for s in students if s.get('id') != student_id]
        self._set_round_students(data, class_id, filtered)
        self._save_students(data)
        _audit(f"删除学生: {class_id}/{deleted_name}")
        return True, "删除成功"
    
    def import_students(self, class_id, student_list):
        """批量导入学生（替换当前轮次学生）"""
        data = self._load_students()
        class_id = str(class_id)
        if class_id not in data.get('classes', {}):
            grade = int(str(class_id)[0]) if len(str(class_id)) >= 2 else 1
            data.setdefault('classes', {})[class_id] = {
                'grade': grade,
                'name': f"{grade}年级{str(class_id)[-2:]}班",
                'test_rounds': [{'date': '', 'students': []}],
                'current_round': 0
            }
        
        cdata = data['classes'][class_id]
        self._migrate_class(cdata)
        ridx = cdata.get('current_round', 0)
        cdata['test_rounds'][ridx]['students'] = student_list
        self._save_students(data)
        _audit(f"导入学生: {class_id}, 共{len(student_list)}名")
        return True, f"导入成功，共{len(student_list)}名学生"
    
    def search_students(self, keyword):
        """全校搜索学生（姓名/学号匹配，返回带 _class_id 标记的学生列表）"""
        keyword = keyword.strip().lower()
        results = []
        all_classes = self.get_all_classes()
        for cid, cdata in all_classes.items():
            students = self._get_round_students(cdata)
            for s in students:
                if not keyword:
                    # 空关键字返回所有学生（用于查找编辑）
                    s_copy = dict(s)
                    s_copy['_class_id'] = cid
                    results.append(s_copy)
                else:
                    name = (s.get('name', '') or '').lower()
                    sid = (s.get('student_number', '') or '').lower()
                    if keyword in name or keyword in sid:
                        s['_class_id'] = cid
                        results.append(s)
        return results
    
    def get_all_students(self, grade=None, class_id=None):
        """获取符合条件的全部学生列表（仅当前轮次）"""
        all_classes = self.get_all_classes()
        students = []
        if class_id:
            cdata = all_classes.get(str(class_id))
            if cdata:
                students = self._get_round_students(cdata)
        elif grade:
            for cid, cdata in all_classes.items():
                if cdata.get('grade') == grade:
                    students.extend(self._get_round_students(cdata))
        else:
            for cid, cdata in all_classes.items():
                students.extend(self._get_round_students(cdata))
        return students
    
    def get_statistics(self, grade=None, class_id=None):
        """获取统计信息（仅统计当前轮次）"""
        students = self.get_all_students(grade=grade, class_id=class_id)
        dist = compute_grade_distribution(students)
        total = dist['total']
        counts = dist['counts']
        
        if total == 0:
            return {
                'total': 0, '优秀': 0, '良好': 0, '及格': 0, '不及格': 0,
                '优秀率': 0, '良好率': 0, '及格率': 0, '不及格率': 0,
                'avg_score': 0, 'students': []
            }
        
        return {
            'total': total,
            '优秀': counts['优秀'], '良好': counts['良好'],
            '及格': counts['及格'], '不及格': counts['不及格'],
            '优秀率': round(counts['优秀'] / total * 100, 1),
            '良好率': round(counts['良好'] / total * 100, 1),
            '及格率': round(dist['pass_count'] / total * 100, 1),
            '不及格率': round(counts['不及格'] / total * 100, 1),
            'avg_score': dist['avg_score'],
            'students': students
        }
