import sys

import sqlcipher3

import os
import sqlite3
from enum import Enum

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.db.SQLOperation import Base, db_session_scope, DatabaseException
from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint

LOGGER = logger.init_log('plugin_manager')


# pylint: disable=too-few-public-methods
class PluginStatus:
    '''
    功能插件状态
    '''
    NOT_INSTALLED = 1
    INSTALLING = 2
    INSTALLED = 3
    INSTALLED_BUT_DAMAGED = 4


# pylint: disable=too-few-public-methods
class PluginExtendStatus(PluginStatus):
    '''
    插件进度条状态
    '''
    VERIFYING = 7
    VERIFY_SIGNATURE_FAILED = 16
    PLUGIN_PACKAGE_CHECK_FAILED = 17


# pylint: disable=too-few-public-methods
class PluginType(Enum):
    codemig = 'codemig'

    @classmethod
    def get_supported_types(cls):
        """获取支持的插件类型列表"""
        return [member.value for member in cls]


class Plugin(Base):
    """
    插件 ORM 类
    对应数据库表: plugin
    """
    __tablename__ = 'plugin'
    __table_args__ = (
        UniqueConstraint('plugin_type', name='uq_plugin_plugin_type'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin_type = Column(String, nullable=False)
    current_version = Column(String)
    status = Column(Integer)
    update_time = Column(DateTime)
    progress_status = Column(Integer)
    create_time = Column(DateTime)
    plugin_meta_json = Column(Text)

    @staticmethod
    def query_all():
        """
        使用 ORM 查询所有插件

        Returns:
            tuple: (success: bool, plugins: list, error: str)
        """
        try:
            with db_session_scope() as session:
                plugins = session.query(Plugin).order_by(Plugin.id).all()
                # 在会话内提取数据，避免 DetachedInstanceError
                plugin_list = []
                for plugin in plugins:
                    plugin_list.append({
                        'id': plugin.id,
                        'plugin_type': plugin.plugin_type,
                        'current_version': plugin.current_version,
                        'status': plugin.status,
                        'update_time': plugin.update_time,
                        'progress_status': plugin.progress_status,
                        'create_time': plugin.create_time,
                        'plugin_meta_json': plugin.plugin_meta_json
                    })
                return True, plugin_list, None
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error('query plugin data error! %s', err)
            return False, None, 'query plugin error!'

    @staticmethod
    def query_version_by_type(plugin_type):
        """
        按 plugin_type 查询当前版本号。

        Args:
            plugin_type: 插件类型，如 'framework' / 'codemig'

        Returns:
            str: current_version；查询失败或记录不存在时返回 None。
        """
        try:
            with db_session_scope() as session:
                plugin = session.query(Plugin).filter(
                    Plugin.plugin_type == plugin_type).first()
                return plugin.current_version if plugin else None
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error('query plugin version error! %s', err)
            return None
