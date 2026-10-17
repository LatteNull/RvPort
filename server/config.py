"""
应用配置
"""
import os
import json
import logging
from common.public.common import ROOT_PATH
from common.db.crypto_utils import get_key


def load_config_from_json(config_path=None):
    """从 JSON 文件加载配置"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")

    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"无法读取配置文件 {config_path}: {e}")
    return config


class Config:
    """应用配置类"""

    def __init__(self):
        # 从 JSON 文件加载配置
        self._json_config = load_config_from_json()

    def _get_config(self, key, default=None):
        """获取配置值，优先级：环境变量 > JSON 配置 > 默认值"""
        # 首先检查环境变量
        value = os.environ.get(key)
        if value is not None:
            # 尝试转换类型
            if isinstance(default, bool):
                return value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(default, int):
                try:
                    return int(value)
                except ValueError:
                    return default
            return value

        # 然后检查 JSON 配置
        if key in self._json_config:
            return self._json_config[key]

        # 返回默认值
        return default

    # 安全配置（默认空串：未配置时 Flask 拒绝签名，优于静默使用可预测默认值）
    @property
    def SECRET_KEY(self):
        return self._get_config('key', '')

    # 数据库类型: 'sqlite' 或 'mysql'（默认 sqlite，配置文件只需 DB_TYPE 一项；
    # 选 mysql 时才需要在 config.json 增加 MYSQL_* 配置，见下方 MySQL 配置段）
    @property
    def DB_TYPE(self):
        return self._get_config('DB_TYPE', 'sqlite').lower()

    # SQLite 配置
    @property
    def SQLITE_DATABASE_URI(self):
        """获取 SQLite 数据库 URI"""
        # 如果 JSON 或环境变量中指定了路径，使用它
        custom_uri = self._get_config('SQLITE_DATABASE_URI', '')
        if custom_uri:
            return custom_uri

        # 否则使用默认路径
        _default_db_path = os.path.join(ROOT_PATH, 'data', 'codemig.db')
        return f'sqlite:///{_default_db_path}'

    @property
    def SQLITE_USE_ENCRYPTION(self):
        return not self.DEBUG

    # MySQL 配置（仅在 DB_TYPE='mysql' 时被访问——SQLALCHEMY_DATABASE_URI 只在
    # mysql 分支读取这些属性，sqlite 模式不会触发。MYSQL_PASSWORD 来自 data/ 下
    # 的密钥文件，由 scripts/install_db.py db_type=mysql 交互录入后加密存储）
    @property
    def MYSQL_HOST(self):
        return self._get_config('MYSQL_HOST', 'localhost')

    @property
    def MYSQL_PORT(self):
        return self._get_config('MYSQL_PORT', 3306)

    @property
    def MYSQL_USER(self):
        return self._get_config('MYSQL_USER', 'root')

    @property
    def MYSQL_PASSWORD(self):
        """获取解密后的 MySQL 密码（仅 DB_TYPE='mysql' 时访问；文件缺失即启动失败，
        属预期行为——选了 mysql 就必须先跑 install_db.py 录入密码）"""
        # 使用与 SQLite 相同的解密方式
        try:
            return get_key(path=os.path.join(ROOT_PATH, "data"))
        except Exception as e:
            # 如果解密失败，记录错误并抛出异常，导致应用启动失败
            error_msg = f"MySQL 密码解密失败: {e}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e

    @property
    def MYSQL_DATABASE(self):
        return self._get_config('MYSQL_DATABASE', 'codemig')

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """根据配置返回数据库 URI"""
        if self.DB_TYPE == 'mysql':
            return f'mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}'
        else:
            return self.SQLITE_DATABASE_URI

    @property
    def SQLITE_PASSWORD(self):
        """获取解密后的 SQLite 密码"""
        if self.DEBUG:
            return None
        try:
            return get_key(path=os.path.join(ROOT_PATH, "data"))
        except Exception as e:
            # 如果解密失败，记录详细错误但不阻止应用启动
            error_msg = f"SQLite 密码解密失败: {e}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVER_THREADS = 4

    @property
    def SQLALCHEMY_ECHO(self):
        return self._get_config('SQLALCHEMY_ECHO', False)

    # 服务器配置
    @property
    def HOST(self):
        return self._get_config('HOST', '0.0.0.0')

    @property
    def PORT(self):
        return self._get_config('PORT', 8081)

    @property
    def DEBUG(self):
        return self._get_config('DEBUG', False)
