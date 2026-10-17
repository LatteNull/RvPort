import sys
import time
import hashlib
import os
import random
from datetime import datetime

import string
import uuid
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func, ForeignKey, text
from sqlalchemy.orm import relationship, load_only

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.db.SQLOperation import Base, db_session_scope, DatabaseException
from framework.config_manager.config import ConfigKeys, SysConfig

LOGGER = logger.init_log('usermanager')

MAX_HISTORY = 2

MAX_FAILED = 5
IP_FAILED = 5  # 每分钟5次
IP_BAN_DURATION = 120  # 封禁2小时

SALT_LENGTH = 12
# Admin 初始密码 'Codemig@123' 的 PBKDF2-HMAC-SHA256 哈希（salt.hex + dk.hex）。
# 首次登录强制改密（is_first_login=1），初始密码随即作废。
INIT = '3445466c634c537a4a685032955e94504c2396dd0aa50b3e72c9d90ed807fcb21dd35c860b92976c47fc83db'


# pylint: disable=too-few-public-methods
class Role:
    ADMIN = 'admin'
    NORMAL = 'normal'


# pylint: disable=too-few-public-methods
class UserStatus:
    NORMAL = 'normal'
    LOCKED = 'locked'


def encrypt_password(password, salt: str = None):
    if salt is None:
        salt = ''.join(random.sample(string.ascii_letters + string.digits, SALT_LENGTH)).encode(
            'UTF-8')
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('UTF-8'), salt, 50000)
    return salt.hex() + dk.hex()


# ORM 模型：用户管理表
class UserManager(Base):
    """用户管理表"""
    __tablename__ = 'user_manager'

    id = Column(Integer, primary_key=True, autoincrement=True)
    password = Column(String(128))
    user_id = Column(String(64), unique=True)  # UNIQUE 约束
    user_name = Column(String(32))
    role = Column(String(6))
    is_first_login = Column(Integer)
    create_time = Column(DateTime)
    last_login = Column(Integer)  # 时间戳
    last_login_ip = Column(String(64))
    time_pw_reset = Column(Integer)  # 时间戳
    last_logout = Column(Integer)  # 时间戳
    status = Column(String(32), default='normal')
    workspace = Column(String(255))
    provider_id = Column(Integer, default=-1)
    infos = Column(String(255))  # SQL 文件中定义为 infos，不是 others

    # 关系：用户密码历史记录
    password_history = relationship('UserPasswordHistory', back_populates='user',
                                    cascade='all, delete-orphan')

    @property
    def pw(self):
        """向后兼容属性：password 的别名"""
        return self.password

    @pw.setter
    def pw(self, value):
        """向后兼容属性：password 的别名"""
        self.password = value

    @staticmethod
    def query(nopw=True, **selector):
        """
        查询用户

        Args:
            nopw: 如果为 True，不加载 password 字段
            **selector: 查询条件，例如 user_name='admin', provider_id=-1

        Returns:
            UserManager 对象，如果未找到则返回 None
        """
        try:
            with db_session_scope() as session:
                # 构建查询
                query = session.query(UserManager)

                # 应用查询条件
                for key, value in selector.items():
                    if hasattr(UserManager, key):
                        query = query.filter(getattr(UserManager, key) == value)

                # 如果不需要密码，使用 load_only 优化查询
                if nopw:
                    query = query.options(load_only(
                        UserManager.id,
                        UserManager.user_id,
                        UserManager.user_name,
                        UserManager.role,
                        UserManager.is_first_login,
                        UserManager.create_time,
                        UserManager.last_login,
                        UserManager.last_login_ip,
                        UserManager.time_pw_reset,
                        UserManager.last_logout,
                        UserManager.status,
                        UserManager.workspace,
                        UserManager.provider_id,
                        UserManager.infos
                    ))

                # 执行查询
                user = query.first()

                if user is None:
                    conditions = ' AND '.join(f"{k}={v!r}" for k, v in selector.items())
                    LOGGER.warning(f'Not exists querying user: {conditions}')
                    return None

                # expunge 对象，使其可以在会话外使用
                session.expunge(user)
                return user
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error query user: {e}')
            return None

    @staticmethod
    def query_by_id(user_id, nopw=True):
        """
        根据 user_id 查询用户

        Args:
            user_id: 用户 ID
            nopw: 如果为 True，不加载 password 字段

        Returns:
            UserManager 对象，如果未找到则返回 None
        """
        return UserManager.query(nopw=nopw, user_id=user_id)

    @staticmethod
    def query_name_map_by_user_ids(user_ids):
        """
        批量按 user_id 列表查询，返回 {user_id: user_name} 映射。
        用于列表补“归属者”列时避免 N+1 查询。user_ids 为空或全无效时返回 {}。
        未匹配到的 user_id 不会出现在返回 map 中。
        """
        valid_ids = [u for u in user_ids if u]
        if not valid_ids:
            return {}
        try:
            with db_session_scope() as session:
                rows = (
                    session.query(UserManager.user_id, UserManager.user_name)
                    .filter(UserManager.user_id.in_(valid_ids))
                    .all()
                )
                return {r.user_id: r.user_name for r in rows}
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error querying user name map: {e}')
            return {}

    @staticmethod
    def update(user_id, **kwargs):
        """
        更新用户信息

        Args:
            user_id: 用户 ID
            **kwargs: 要更新的字段和值，例如 password='new_password', status='normal'

        Returns:
            bool: 更新成功返回 True，失败返回 False
        """
        try:
            with db_session_scope() as session:
                # 查询用户
                user = session.query(UserManager).filter(UserManager.user_id == user_id).first()
                if user is None:
                    LOGGER.warning(f'User not found for update: user_id={user_id}')
                    return False

                # 更新字段
                for key, value in kwargs.items():
                    if hasattr(UserManager, key):
                        setattr(user, key, value)
                    else:
                        LOGGER.warning(f'Invalid field for update: {key}')

                return True
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error updating user: {e}')
            return False

    @staticmethod
    def delete_user(user_id):
        """
        删除用户

        Args:
            user_id: 用户 ID

        Returns:
            bool: 删除成功返回 True，失败返回 False
        """
        try:
            with db_session_scope() as session:
                # 查询用户
                user = session.query(UserManager).filter(UserManager.user_id == user_id).first()
                if user is None:
                    LOGGER.warning(f'User not found for deletion: user_id={user_id}')
                    return False

                # 删除用户（级联删除会同时删除关联的密码历史记录）
                session.delete(user)
                return True
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error deleting user: {e}')
            return False

    @staticmethod
    def save(user_name, role, pwd):
        """
        创建新用户

        Args:
            user_name: 用户名
            role: 角色
            pwd: 密码（明文）

        Returns:
            tuple: (成功标志, user_id) 或 (False, None)
        """
        try:
            with db_session_scope() as session:
                # 加密密码
                encrypted_pwd = encrypt_password(pwd)
                user_id = str(uuid.uuid4())

                # 创建新用户
                new_user = UserManager(
                    user_name=user_name,
                    password=encrypted_pwd,
                    role=role,
                    user_id=user_id,
                    is_first_login=1,
                    create_time=datetime.now(),
                    provider_id=-1,
                    status='normal'
                )

                session.add(new_user)
                return True, user_id
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error creating user: {e}')
            return False, None

    @staticmethod
    def list_all_local(selector=None):
        """
        列出所有本地用户（provider_id=-1）

        Args:
            selector: 可选，格式为 (条件字符串, 参数列表)，例如 ('user_name=?', ['admin'])

        Returns:
            list: UserManager 对象列表
        """
        try:
            with db_session_scope() as session:
                # 基础查询：provider_id=-1
                query = session.query(UserManager).filter(UserManager.provider_id == -1)

                # 应用额外的选择条件
                if selector:
                    condition, params = selector
                    # 将条件字符串转换为 SQLAlchemy 表达式
                    # selector 格式是 ('user_name=?', ['admin'])
                    # 为了兼容性，使用 text() 处理原始 SQL 条件
                    # 将 ? 替换为 :param0, :param1 等
                    param_names = {f'param{i}': param for i, param in enumerate(params)}
                    condition_with_params = condition
                    for i in range(len(params)):
                        condition_with_params = condition_with_params.replace('?', f':param{i}', 1)
                    query = query.filter(text(condition_with_params).bindparams(**param_names))

                # 按 id 排序
                query = query.order_by(UserManager.id)

                # 使用 load_only 优化查询（不加载 password）
                query = query.options(load_only(
                    UserManager.id,
                    UserManager.user_id,
                    UserManager.user_name,
                    UserManager.role,
                    UserManager.is_first_login,
                    UserManager.create_time,
                    UserManager.last_login,
                    UserManager.last_login_ip,
                    UserManager.time_pw_reset,
                    UserManager.last_logout,
                    UserManager.status,
                    UserManager.workspace,
                    UserManager.provider_id,
                    UserManager.infos
                ))

                # 获取所有结果并 expunge，使对象可以在会话外使用
                results = query.all()
                for result in results:
                    session.expunge(result)
                return results
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error list local user: {e}')
            return []

    @staticmethod
    def init_default_user():
        """
        初始化默认的 Admin 用户

        如果 Admin 用户不存在，则创建一个默认的 Admin 用户
        """
        try:
            with db_session_scope() as session:
                # 检查 Admin 用户是否已存在
                admin_user = session.query(UserManager).filter(
                    UserManager.user_name == 'Admin'
                ).first()

                if admin_user is None:
                    # 创建默认 Admin 用户
                    admin_user = UserManager(
                        password=INIT,
                        user_id=str(uuid.uuid4()),
                        user_name='Admin',
                        role=Role.ADMIN,
                        is_first_login=1,
                        create_time=datetime.now(),
                        provider_id=-1,
                        status='normal'
                    )
                    session.add(admin_user)
                    LOGGER.info('Default Admin user created')
                else:
                    LOGGER.debug('Admin user already exists')
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error initializing default user: {e}')


# ORM 模型：用户密码历史记录表
class UserPasswordHistory(Base):
    """用户密码历史记录表"""
    __tablename__ = 'user_password_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), ForeignKey('user_manager.user_id'))
    password = Column(String(128))
    created_at = Column(BigInteger)  # 时间戳（纳秒级）

    # 关系：关联的用户
    user = relationship('UserManager', back_populates='password_history')

    @staticmethod
    def is_password_in_history(user_id, new_password):
        """
        检查新密码是否存在于用户的最近历史密码中

        Args:
            user_id: 用户 ID
            new_password: 新密码（明文）

        Returns:
            bool: 如果新密码存在于历史记录中返回 True，否则返回 False
        """
        try:
            # 第一步：快速查询历史密码（在会话中）
            password_list = []
            with db_session_scope() as session:
                # 获取用户最近使用的密码（最多 MAX_HISTORY + 1 条，因为我们要检查是否重复）
                recent_passwords = session.query(UserPasswordHistory.password).filter(
                    UserPasswordHistory.user_id == user_id
                ).order_by(UserPasswordHistory.created_at.desc()).limit(MAX_HISTORY + 1).all()

                # 将查询结果转换为普通列表（在会话关闭前）
                password_list = [password for (password,) in recent_passwords]

            # 第二步：在会话外进行密码加密和比较操作
            for old_password in password_list:
                salt = int(old_password[0:24], 16).to_bytes(12, byteorder='big')
                dk = encrypt_password(new_password, salt)
                if dk == old_password:
                    return True
            return False
        except (DatabaseException, OSError, IOError, RuntimeError, ValueError) as e:
            # 只记录异常类型不记录内容：本函数入参含密码，str(e) 可能带出敏感数据
            LOGGER.error('Error checking password history: %s', type(e).__name__)
            return False

    @staticmethod
    def save_password_history(user_id, password):
        """
        保存新密码到历史表，并删除超过 MAX_HISTORY 次的旧记录

        Args:
            user_id: 用户 ID
            password: 密码（明文）
        """
        try:
            # 在数据库连接外加密密码（耗时操作）
            encrypted = encrypt_password(password)
            created_at = time.time_ns()

            with db_session_scope() as session:
                # 插入新密码记录
                new_history = UserPasswordHistory(
                    user_id=user_id,
                    password=encrypted,
                    created_at=created_at
                )
                session.add(new_history)
                session.flush()  # 确保新记录已插入，以便后续查询

                # 查询需要删除的旧记录（跳过最新的 MAX_HISTORY 条，删除其余的）
                records_to_delete = session.query(UserPasswordHistory).filter(
                    UserPasswordHistory.user_id == user_id
                ).order_by(UserPasswordHistory.created_at.desc()).offset(MAX_HISTORY).all()

                # 删除多余的旧记录
                for record in records_to_delete:
                    session.delete(record)
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            # 只记录异常类型不记录内容：本函数入参含密码，str(e) 可能带出敏感数据
            LOGGER.error('Error save password history: %s', type(e).__name__)


# ORM 模型：用户失败登录记录
class UserFailedLogin(Base):
    """用户失败登录记录表"""
    __tablename__ = 'user_failedlogin'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(64))
    failed_time = Column(Integer)  # 时间戳

    @staticmethod
    def get_failed_count(user_name, now_time):
        """获取用户失败登录次数和最后失败时间"""
        try:
            with db_session_scope() as session:
                result = session.query(
                    func.count(UserFailedLogin.id).label('total_count'),
                    func.max(UserFailedLogin.failed_time).label('last_failed_time')
                ).filter(
                    UserFailedLogin.user_name == user_name,
                    UserFailedLogin.failed_time <= now_time
                ).first()

                if result and result.total_count:
                    return result.total_count, result.last_failed_time
                return 0, None
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error get login failed record: {e}')
            return 0, None

    @staticmethod
    def record_failed_login(user_name, now=None):
        """记录失败的登录尝试"""
        now = now or time.time()
        try:
            with db_session_scope() as session:
                failed_record = UserFailedLogin(user_name=user_name, failed_time=int(now))
                session.add(failed_record)
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error record failed login: {e}')

    @staticmethod
    def clean_failed_record(user_name):
        """清理用户的失败登录记录"""
        try:
            with db_session_scope() as session:
                session.query(UserFailedLogin).filter(
                    UserFailedLogin.user_name == user_name).delete()
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error clean failed record: {e}')

    @staticmethod
    def check_lock_status(user_name=None, now=None):
        """检查用户是否被锁定"""
        timeout = int(SysConfig.query_system_configuration(ConfigKeys.LOCK_TIME)[1])
        max_failed = int(SysConfig.query_system_configuration(ConfigKeys.MAX_PW_FAILED)[1])
        now = now or time.time()

        count, last_time = UserFailedLogin.get_failed_count(user_name, now)
        if count >= max_failed and last_time:
            if now - last_time > timeout * 60:
                UserFailedLogin.clean_failed_record(user_name)
                return False
            else:
                return True
        return False

    @staticmethod
    def record_and_check(user_name=None, now=None):
        """记录失败登录并检查是否应该锁定用户"""
        timeout = int(SysConfig.query_system_configuration(ConfigKeys.LOCK_TIME)[1])
        max_failed = int(SysConfig.query_system_configuration(ConfigKeys.MAX_PW_FAILED)[1])
        now = now or time.time()

        count, last_time = UserFailedLogin.get_failed_count(user_name, now)
        if count >= max_failed and last_time:
            if now - last_time > timeout * 60:
                UserFailedLogin.clean_failed_record(user_name)
                UserFailedLogin.record_failed_login(user_name, now)
                return False
            return True
        UserFailedLogin.record_failed_login(user_name, now)
        return count + 1 >= max_failed


# ORM 模型：用户登录失败时间记录
class UserLoginFailedTime(Base):
    """用户登录失败时间记录表"""
    __tablename__ = 'user_login_failed_time'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64))
    ip = Column(String(60))
    failed_time = Column(DateTime, default=datetime.now)  # 失败时间

    @staticmethod
    def record_user_failed(user_id, ip):
        """记录失败的登录尝试"""
        try:
            with db_session_scope() as session:
                failed_record = UserLoginFailedTime(
                    user_id=user_id,
                    ip=ip,
                    failed_time=datetime.now()
                )
                session.add(failed_record)
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error record user failed: {e}')

    @staticmethod
    def get_count(user_id):
        """获取用户失败登录次数"""
        try:
            with db_session_scope() as session:
                count = session.query(func.count(UserLoginFailedTime.id)).filter(
                    UserLoginFailedTime.user_id == user_id
                ).scalar()
                return count if count else 0
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error get login failed record: {e}')
            return 0

    @staticmethod
    def clean_failed_record(user_id):
        """清理用户的失败登录记录"""
        try:
            with db_session_scope() as session:
                session.query(UserLoginFailedTime).filter(
                    UserLoginFailedTime.user_id == user_id
                ).delete()
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error clean failed record: {e}')


# ORM 模型：IP 失败登录记录
class IPFailedLogin(Base):
    """IP 失败登录记录表"""
    __tablename__ = 'user_ip_failedlogin'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_addr = Column(String(60))
    failed_time = Column(Integer)  # 时间戳
    locked = Column(Integer, default=0)  # 0=未锁定, 1=已锁定

    # 类变量：配置参数
    max_failed = IP_FAILED
    ban_duration = IP_BAN_DURATION

    @classmethod
    def set_max_failed(cls, count):
        """设置最大失败次数"""
        cls.max_failed = int(count)

    @classmethod
    def set_ban_duration(cls, duration):
        """设置封禁时长（分钟）"""
        cls.ban_duration = int(duration)

    @staticmethod
    def get_lock_status(ip, now=None):
        """检查 IP 是否被锁定"""
        now = time.time() if now is None else now
        try:
            with db_session_scope() as session:
                # 先找到该 IP 的最大 failed_time
                max_time_result = session.query(
                    func.max(IPFailedLogin.failed_time).label('max_time')
                ).filter(
                    IPFailedLogin.ip_addr == ip
                ).first()

                if max_time_result is None or max_time_result.max_time is None:
                    return False

                max_time = max_time_result.max_time

                # 查询该 IP 在最大 failed_time 时的锁定状态
                result = session.query(
                    IPFailedLogin.locked
                ).filter(
                    IPFailedLogin.ip_addr == ip,
                    IPFailedLogin.failed_time == max_time
                ).first()

                if result is None:
                    return False

                locked = result.locked
                if not locked:
                    return False

                # 检查是否在封禁时间内
                if locked == 1 and max_time > now - IPFailedLogin.ban_duration * 60:
                    return True
                return False
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'get lock status db error: {str(e)}')
            return False

    @staticmethod
    def record_and_check(ip, now=None):
        """记录失败登录并检查是否应该锁定 IP"""
        now = time.time() if now is None else now
        try:
            with db_session_scope() as session:
                # 插入新的失败记录
                failed_record = IPFailedLogin(
                    ip_addr=ip,
                    failed_time=int(now),
                    locked=0
                )
                session.add(failed_record)
                # 刷新 session，确保新插入的记录可以被查询到
                session.flush()

                # 统计最近1分钟内的失败次数
                recent_failures = session.query(func.count(IPFailedLogin.id)).filter(
                    IPFailedLogin.ip_addr == ip,
                    IPFailedLogin.failed_time >= int(now - 60),
                    IPFailedLogin.failed_time <= int(now)
                ).scalar()

                # 删除60秒之前的旧记录
                session.query(IPFailedLogin).filter(
                    IPFailedLogin.ip_addr == ip,
                    IPFailedLogin.failed_time < int(now - 60)
                ).delete()

                # 如果失败次数达到阈值，锁定该 IP
                if recent_failures and recent_failures >= IPFailedLogin.max_failed:
                    session.query(IPFailedLogin).filter(
                        IPFailedLogin.ip_addr == ip
                    ).update({'locked': 1})
                    return True
                return False
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'record ip lock db error: {str(e)}')
            return False
