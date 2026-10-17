import os
import pytest
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import common.db.SQLOperation as sql_op
from common.db.SQLOperation import DB_INFO, Base, engine as global_engine
from common.response.response_code import ResponseCode
from framework.config_manager.config import DEFAULT_VALUE, ConfigKeys, _check_config_param, \
    SysConfig


@pytest.fixture
def mock_db_file():
    """
    创建测试数据库文件并设置数据库环境

    Yields:
        str: 测试数据库文件路径
    """
    # 创建临时数据库文件
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as test_db_file:
        db_path = test_db_file.name

    # 保存原始状态
    old_file = DB_INFO.file
    old_env_uri = os.environ.get('SQLITE_DATABASE_URI')
    original_engine = sql_op.engine
    original_session = sql_op.db_session
    new_engine = None

    try:

        # 关闭旧引擎
        if hasattr(sql_op, 'engine'):
            global_engine.dispose()

        # 创建新引擎（测试环境不使用加密）
        new_engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )

        # 创建新的会话工厂
        new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
        new_db_session = scoped_session(new_session_local)

        # 临时替换全局变量
        sql_op.engine = new_engine
        sql_op.db_session = new_db_session

        # 创建表结构
        Base.metadata.create_all(bind=new_engine)

        # 执行 SQL 脚本来初始化表结构
        sql_file = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                         'scripts', 'install', 'sqlite.sql'))
        try:
            conn = sqlite3.connect(db_path)
            with open(sql_file, "r") as f:
                sql = f.read()
                try:
                    conn.executescript(sql)
                    print(f"Executed SQL from: {sql_file}")
                except Exception as e:
                    print(f"Executed SQL error from: {sql_file}: {e}")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error executing SQL scripts: {e}")

        # 设置环境变量，让 Config 使用测试数据库路径
        os.environ['SQLITE_DATABASE_URI'] = f'sqlite:///{db_path}'

        print(f"Created test database: {db_path}")

        yield db_path

    finally:
        # 恢复原始引擎和会话
        sql_op.engine = original_engine
        sql_op.db_session = original_session
        if hasattr(sql_op, 'engine') and new_engine:
            new_engine.dispose()

        # 恢复环境变量
        if old_env_uri is not None:
            os.environ['SQLITE_DATABASE_URI'] = old_env_uri
        elif 'SQLITE_DATABASE_URI' in os.environ:
            del os.environ['SQLITE_DATABASE_URI']

        # 清理测试数据库
        if os.path.exists(db_path):
            os.remove(db_path)


def test_sysconfig_init_does_not_duplicate_defaults(mock_db_file):
    """
    测试多次调用 list_all 方法，不重复插入默认配置。
    """
    # 第一次调用 list_all 来加载配置
    SysConfig.list_all()
    conn = sqlite3.connect(mock_db_file)
    cursor = conn.cursor()

    # 检查数据库中的配置项数量
    cursor.execute(f"SELECT COUNT(*) FROM sysconfig")
    initial_count = cursor.fetchone()[0]

    # 再次调用 list_all，确保不重复插入数据
    SysConfig.list_all()
    cursor.execute(f"SELECT COUNT(*) FROM sysconfig")
    second_count = cursor.fetchone()[0]
    assert second_count == initial_count, "多次初始化后，数据库中配置项数量不应发生变化"

    conn.close()


def test_query_system_configuration_existing_key(mock_db_file):
    # 测试成功查询一个已存在的配置项
    valid_key = ConfigKeys.MAX_ONLINE_USERS
    result, value, code = SysConfig.query_system_configuration(valid_key)
    assert result is True


def test_query_system_configuration_invalid_key(mock_db_file):
    # 测试查询一个无效的配置项
    invalid_key = "non_existing_key"
    result, value, code = SysConfig.query_system_configuration(invalid_key)
    assert result is False
    assert value is None
    assert code == ResponseCode.SYSCONFIG_INVALID_KEY


def test_query_uses_cached_value(mock_db_file):
    """
    测试查询时是否优先使用缓存值。
    """
    SysConfig.list_all()
    test_key = list(DEFAULT_VALUE.keys())[0]  # 获取一个默认键

    # 第一次查询，确保缓存了值
    SysConfig.query_system_configuration(test_key)
    _, _, configs = SysConfig.list_all()
    assert test_key in configs, f"{test_key} 应存在于缓存中"

    # 模拟更新数据库中该键的值（不更新缓存）
    new_value = "new_cached_value"
    conn = sqlite3.connect(mock_db_file)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE sysconfig SET config_value = ? WHERE config_name = ?",
                   (new_value, test_key))
    conn.commit()
    conn.close()

    # 再次查询，值应来自缓存，而不是数据库
    success, value, code = SysConfig.query_system_configuration(test_key)
    assert success is True, "缓存查询应返回成功"
    assert value == DEFAULT_VALUE[test_key], "查询结果应优先返回缓存中的默认值，而非数据库更新值"


def test_query_nonexistent_key_returns_default(mock_db_file):
    """
    测试查询不存在的键时，返回默认值。
    """
    # 查询一个不存在的键
    test_key = list(DEFAULT_VALUE.keys())[0]  # 获取一个默认键
    success, value, code = SysConfig.query_system_configuration(test_key)
    assert success is True, "查询不存在的键时，查询结果应为成功"
    assert value == DEFAULT_VALUE[test_key], f"查询的值应返回默认值 {DEFAULT_VALUE[test_key]}"
    assert code == ResponseCode.OK, "返回的响应码应为 ResponseCode.OK"


# 测试update
def test_update_config_valid(mock_db_file):
    # 测试使用有效值更新配置项
    valid_key = ConfigKeys.MAX_ONLINE_USERS
    valid_value = "15"

    success, code = SysConfig.update(key=valid_key, value=valid_value)
    assert success is True
    assert code == ResponseCode.OK


def test_update_config_invalid_key(mock_db_file):
    # 测试使用无效键更新配置项
    invalid_key = "invalid_key"
    valid_value = "15"
    success, code = SysConfig.update(key=invalid_key, value=valid_value)
    assert success is False


def test_update_config_out_of_range_value(mock_db_file):
    # 测试使用超出限制值更新配置项
    valid_key = ConfigKeys.MAX_ONLINE_USERS
    invalid_value = "25"  # 超出ConfigCheckLimit范围
    success, code = SysConfig.update(key=valid_key, value=invalid_value)
    assert success is False


# 测试check_config_param
def test_check_config_param_valid():
    # 测试一个合法配置键值对
    key = ConfigKeys.SESSION_TIMEOUT
    value = "60"  # 在10~10080范围内
    status, code = _check_config_param(key, value)
    assert status is True


def test_check_config_param_invalid_value():
    # 测试一个不合法的值
    key = ConfigKeys.SESSION_TIMEOUT
    invalid_value = "100000"  # 超出限制范围
    status, code = _check_config_param(key, invalid_value)
    assert status is False
    assert code == ResponseCode.SYSCONFIG_INVALID_VALUE


def test_check_config_param_not_string():
    # 测试一个不合法的值
    key = ConfigKeys.SESSION_TIMEOUT
    invalid_value = {"100000"}  # 超出限制范围
    status, code = _check_config_param(key, invalid_value)
    assert status is False
    assert code == ResponseCode.SYSCONFIG_INVALID_VALUE


def test_check_config_param_invalid_type():
    # 测试一个不合法的值
    key = ConfigKeys.SESSION_TIMEOUT
    invalid_value = "100000abd"  # 非数字
    status, code = _check_config_param(key, invalid_value)
    assert status is False


# 测试list_all
def test_list_all(mock_db_file):
    # 测试是否可以正确列出所有配置
    # 实际键集 = SQL 种子（含 docker_* 代理配置）+ 启动补入的 DEFAULT_VALUE 项，
    # 可能多于 DEFAULT_VALUE，断言改为：DEFAULT_VALUE 键全在 + 所有键均为合法 ConfigKeys
    _, _, configs = SysConfig.list_all()
    assert set(DEFAULT_VALUE.keys()).issubset(set(configs.keys()))
    valid_keys = {v for k, v in ConfigKeys.__dict__.items() if not k.startswith('_')}
    assert set(configs.keys()).issubset(valid_keys)


# Ended by AICoder, pid:0ee2chd44ak191c149fa0a02815ea79b70d376ee

def test_query_db_handles_exception(mock_db_file):
    result = SysConfig.query_by_name(key="test_key")

    # 验证结果
    assert result is None  # 当异常发生时，query_by_name 应返回 None


def test_list_all_handles_no_db_file():
    """
    测试 list_all 方法在数据库操作抛出异常时的行为。
    """
    # 使用 patch 来模拟数据库异常
    # 模拟 db_session_scope 在 with 块内部抛出 DatabaseException
    from common.db.SQLOperation import DatabaseException

    with patch('framework.config_manager.config.db_session_scope') as mock_scope:
        # 创建一个模拟的上下文管理器，在 __enter__ 时抛出异常
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(side_effect=DatabaseException("Database error"))
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_scope.return_value = mock_context

        code, msg, configs = SysConfig.list_all()  # 调用目标方法
        assert code == False
        assert msg == ResponseCode.DB_EXCEPTION
        assert configs is None


def test_query_system_configuration_key_not_found(mock_db_file):
    """
    测试 query_system_configuration 方法，当查询不到键时的行为。
    """
    # 查询一个不存在的键应该返回默认值
    result, value, code = SysConfig.query_system_configuration('max_online_users')

    # 验证返回值
    assert result is True  # 查询应该成功，返回默认值
    assert value == DEFAULT_VALUE[ConfigKeys.MAX_ONLINE_USERS]  # 应该返回默认值
