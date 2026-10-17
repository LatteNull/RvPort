import re
import os
import sys
import copy
import threading

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.response.response_code import ResponseCode
from common.db.SQLOperation import Base, db_session_scope, DatabaseException
from sqlalchemy import Column, Integer, String, UniqueConstraint, Text

MAX_ONLINE_USERS_DEFAULT = '10'
# 会话空闲超时默认 30 分钟。
SESSION_TIMEOUT_DEFAULT = '30'
MAX_PW_FAILED_DEFAULT = '5'
PASSWORD_PERMANENT = '0'
LOCKOUT_TIME_LIMIT = '3'
TASK_PER_USER_LIMIT = '30'
FILE_SIZE_LIMIT_UPLOAD_LIMIT = '2147483648'
LOG_SAVE_TIME_LIMIT = '31'
LOGGER = logger.init_log('config_manager')
PROXY_RE = r"^(http://|https://)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*$"
NO_PROXY_RE = r'^[A-Za-z0-9\-._~*/,\s:]*$'
CONFIG_LOCK = threading.Lock()


class SysConfig(Base):
    """
    系统配置 ORM 类
    对应数据库表: sysconfig
    """
    __tablename__ = 'sysconfig'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_name = Column(String(255), unique=True, nullable=False)
    config_value = Column(Text)

    __table_args__ = (
        UniqueConstraint('config_name', name='uq_sysconfig_config_name'),
    )

    @staticmethod
    def query_by_name(key):
        """
        使用 ORM 查询配置项

        Args:
            key: 配置名称

        Returns:
            tuple: (config_name, config_value) 或 None
        """
        try:
            with db_session_scope() as session:
                config = session.query(SysConfig).filter(SysConfig.config_name == key).first()
                if config:
                    return (config.config_name, config.config_value)
                return None
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"get config set from db error:{str(e)}")
            return None

    @staticmethod
    def _update_value(key, value):
        """
        使用 ORM 更新配置项

        Args:
            key: 配置名称
            value: 配置值

        Returns:
            tuple: (success, response_code)
        """
        try:
            with db_session_scope() as session:
                config = session.query(SysConfig).filter(SysConfig.config_name == key).first()

                if config:
                    # 检查值是否相同
                    if str(config.config_value) == str(value):
                        return False, ResponseCode.SYSCONFIG_VALUE_NOT_CHANGE
                    # 更新值
                    config.config_value = value
                else:
                    # 如果不存在，创建新配置
                    config = SysConfig(config_name=key, config_value=value)
                    session.add(config)

                # db_session_scope 会自动提交
                return True, ResponseCode.OK
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f'Error updating config: {e}')
            return False, ResponseCode.DB_EXCEPTION

    @staticmethod
    def list_all():
        """
        使用 ORM 列出所有配置项

        Returns:
            tuple: (success, response_code, config_set)
                success: bool, 是否成功
                response_code: ResponseCode, 响应代码
                config_set: dict, 配置字典，如果失败则为 None
        """
        config_set = {}
        try:
            with db_session_scope() as session:
                configs = session.query(SysConfig).all()
                # 在 session 内提取数据，避免 detached instance 错误
                for config in configs:
                    config_set[config.config_name] = config.config_value
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f'Error querying sysconfig: {e}')
            return False, ResponseCode.DB_EXCEPTION, None

        # 补充默认值
        for k, v in DEFAULT_VALUE.items():
            if k not in config_set:
                config_set[k] = v

        config_cache.update_all(config_set)
        return True, ResponseCode.OK, config_set

    @staticmethod
    def query_system_configuration(name, cached=True):
        """
        查询指定系统配置的值（使用 ORM）

        Args:
            name: 系统配置名称
            cached: 是否使用缓存，默认为 True

        Returns:
            tuple: (success, value, response_code)
                success: bool, 是否成功
                value: str, 配置值（失败时为 None）
                response_code: ResponseCode, 响应代码
        """
        if name not in [v for k, v in ConfigKeys.__dict__.items() if
                        not callable(v) and not k.startswith("__")]:
            return False, None, ResponseCode.SYSCONFIG_INVALID_KEY
        if cached:
            configs = config_cache.list_config()
            if name in configs:
                return True, configs[name], ResponseCode.OK
        system_configuration = SysConfig.query_by_name(name)
        if not system_configuration:
            value = DEFAULT_VALUE.get(name)
        else:
            value = system_configuration[1]
        if cached:
            configs[name] = value
        config_cache.update_config(name, value)
        return True, value, ResponseCode.OK

    @staticmethod
    def update(key, value):
        """
        更新系统配置（使用 ORM）

        Args:
            key: 配置名称
            value: 配置值

        Returns:
            tuple: (success, response_code)
        """
        if not _is_valid_key(key):
            return False, ResponseCode.SYSCONFIG_INVALID_KEY

        status, code = _check_config_param(key, value)
        if not status:
            return status, code

        with CONFIG_LOCK:
            status, code = SysConfig._update_value(key, value)
            config_cache.update_config(key, value)
        try:
            if key in config_callbacks:
                config_callbacks[key](value)
        except Exception as e:
            LOGGER.error(f'Error call back of  {key}: {e}')
        return status, code


# pylint: disable=too-few-public-methods
class ConfigKeys:
    MAX_ONLINE_USERS = 'max_online_users'
    SESSION_TIMEOUT = 'session_timeout'
    MAX_PW_FAILED = 'max_password_failed'
    PW_TIMEOUT = 'password_timeout'
    LOCK_TIME = 'lock_time'
    TASK_PER_USER = 'task_per_user'
    FILE_SIZE_LIMIT_UPLOAD = 'file_size_limit_upload'
    LOG_SAVE_TIME = 'log_save_time'
    DOCKER_HTTP_PROXY = 'docker_http_proxy'
    DOCKER_HTTPS_PROXY = 'docker_https_proxy'
    DOCKER_NO_PROXY = 'docker_no_proxy'


DEFAULT_VALUE = {
    ConfigKeys.MAX_ONLINE_USERS: MAX_ONLINE_USERS_DEFAULT,
    ConfigKeys.SESSION_TIMEOUT: SESSION_TIMEOUT_DEFAULT,
    ConfigKeys.MAX_PW_FAILED: MAX_PW_FAILED_DEFAULT,
    ConfigKeys.PW_TIMEOUT: PASSWORD_PERMANENT,
    ConfigKeys.LOCK_TIME: LOCKOUT_TIME_LIMIT,
    ConfigKeys.TASK_PER_USER: TASK_PER_USER_LIMIT,
    ConfigKeys.FILE_SIZE_LIMIT_UPLOAD: FILE_SIZE_LIMIT_UPLOAD_LIMIT,
    ConfigKeys.LOG_SAVE_TIME: LOG_SAVE_TIME_LIMIT
}


class _ConfigSet:
    """配置管理器单例类"""

    def __init__(self):
        self._config_dict = {}

    def update_all(self, configs):
        """更新所有配置"""
        self._config_dict = copy.deepcopy(configs)

    def update_config(self, key, value):
        """更新单个配置"""
        self._config_dict[key] = value

    def list_config(self):
        """获取配置副本"""
        return copy.deepcopy(self._config_dict)


config_cache = _ConfigSet()

# 配置更新回调函数字典
config_callbacks = {}


def register_callback(key, callback):
    """
    注册配置更新回调函数

    Args:
        key: 配置键名
        callback: 回调函数

    Returns:
        tuple: (success, response_code)
    """
    if key not in [v for k, v in ConfigKeys.__dict__.items() if
                   not callable(v) and not k.startswith("__")]:
        return False, ResponseCode.SYSCONFIG_INVALID_KEY
    config_callbacks[key] = callback
    return True, None


def _is_valid_key(k):
    return k in (v for k, v in ConfigKeys.__dict__.items() if
                 not callable(v) and not k.startswith("__"))


# pylint: disable=too-few-public-methods
class ConfigCheckLimit:
    def __init__(self, min_=0, max_=99, enum_=None, particular_=-2):
        self.min_ = min_
        self.max_ = max_
        self.enum_ = enum_
        self.particular_ = particular_

    def __call__(self, value):
        if self.enum_:
            return value in self.enum_
        try:
            if not isinstance(value, str) and not isinstance(value, int):
                return False
            value = int(value)
        except (TypeError, ValueError) as err:
            LOGGER.error(err)
            return False
        if self.particular_ != -2:
            return self.particular_ == value or self.min_ <= value <= self.max_
        return self.min_ <= value <= self.max_


class ConfigRegexCheckLimit:
    def __init__(self, pattern=None, max_len=2000, nullable=True):
        self.pattern = pattern
        self.max_len = max_len
        self.nullable = nullable

    def __call__(self, value):
        # 1. 处理空值情况
        if not value:
            return self.nullable

        # 2. 确保是字符串
        if not isinstance(value, str):
            value = str(value)

        # 3. 长度校验
        if len(value) > self.max_len:
            return False

        # 4. 正则校验
        if self.pattern:
            return bool(re.match(self.pattern, value))

        return True


SYSCONFIG_CHECK_LIMITS = {
    ConfigKeys.MAX_ONLINE_USERS: ConfigCheckLimit(min_=1, max_=20),
    ConfigKeys.SESSION_TIMEOUT: ConfigCheckLimit(min_=10, max_=10080),
    ConfigKeys.MAX_PW_FAILED: ConfigCheckLimit(min_=3, max_=10),
    ConfigKeys.PW_TIMEOUT: ConfigCheckLimit(min_=0, max_=360),
    ConfigKeys.LOCK_TIME: ConfigCheckLimit(min_=3, max_=1440),
    ConfigKeys.TASK_PER_USER: ConfigCheckLimit(min_=20, max_=100),
    ConfigKeys.FILE_SIZE_LIMIT_UPLOAD: ConfigCheckLimit(min_=524288000, max_=4294967296),
    ConfigKeys.LOG_SAVE_TIME: ConfigCheckLimit(min_=31, max_=90),
    ConfigKeys.DOCKER_HTTP_PROXY: ConfigRegexCheckLimit(pattern=PROXY_RE, max_len=256),
    ConfigKeys.DOCKER_HTTPS_PROXY: ConfigRegexCheckLimit(pattern=PROXY_RE, max_len=256),
    ConfigKeys.DOCKER_NO_PROXY: ConfigRegexCheckLimit(pattern=NO_PROXY_RE, max_len=1024)
    # 500MB ~ 4GB
}


def _check_config_param(key, value):
    if key not in SYSCONFIG_CHECK_LIMITS:
        return False, ResponseCode.SYSCONFIG_INVALID_KEY
    func = SYSCONFIG_CHECK_LIMITS.get(key)
    if not func(value):
        return False, ResponseCode.SYSCONFIG_INVALID_VALUE
    return True, ResponseCode.OK