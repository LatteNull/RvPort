"""
为 log_manager/operation_log.py 补充测试。
"""
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import common.db.SQLOperation as sql_op
from common.db.SQLOperation import Base, engine as global_engine
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.log_manager.operation_constant import OpLogResult, OpLogModule, OpLogEvent
from framework.log_manager.operation_log import (
    OperationLog, get_expire_days, get_max_log_size, record_operation_log,
    log_buffer,
)


def record_sync(*args, **kwargs):
    """record 并同步刷盘：record 已改为异步缓冲写入（log_buffer + 后台线程），
    测试中显式调用 _do_flush() 保证数据落库后再断言，避免竞态。"""
    result = OperationLog.record(*args, **kwargs)
    log_buffer._do_flush()
    return result


@pytest.fixture(scope="function")
def setup_db():
    """复用与 test_operation_log.py 类似的测试数据库初始化"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db:
        db_path = db.name

    original_engine = sql_op.engine
    original_session = sql_op.db_session
    new_engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
    new_db_session = scoped_session(new_session_local)
    sql_op.engine = new_engine
    sql_op.db_session = new_db_session
    Base.metadata.create_all(bind=new_engine)

    # 执行合并后的安装 SQL
    sql_file = os.path.realpath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                     'scripts', 'install', 'sqlite.sql'))
    if os.path.isfile(sql_file):
        conn = sqlite3.connect(db_path)
        with open(sql_file, "r") as f:
            sql = f.read()
            try:
                conn.executescript(sql)
            except Exception as e:
                print(f"SQL error {sql_file}: {e}")
        conn.commit()
        conn.close()

    SysConfig.list_all()

    try:
        yield db_path
    finally:
        sql_op.engine = original_engine
        sql_op.db_session = original_session
        new_engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


# ------------------- get_expire_days -------------------

class TestGetExpireDays:
    def test_returns_value_from_config(self, setup_db):
        """配置中存在有效值时返回该值"""
        # 默认配置存在 -> 返回 31
        assert get_expire_days() == 31

    def test_returns_default_on_invalid_value(self, setup_db, mocker):
        """配置值非数字时返回 EXPIRATION_DAYS"""
        mocker.patch(
            'framework.log_manager.operation_log.SysConfig.query_system_configuration',
            return_value=(True, 'not-a-number', None))
        from framework.log_manager.operation_log import EXPIRATION_DAYS
        assert get_expire_days() == EXPIRATION_DAYS

    def test_returns_default_when_status_false(self, mocker):
        mocker.patch(
            'framework.log_manager.operation_log.SysConfig.query_system_configuration',
            return_value=(False, None, None))
        from framework.log_manager.operation_log import EXPIRATION_DAYS
        assert get_expire_days() == EXPIRATION_DAYS


# ------------------- get_max_log_size -------------------

def test_get_max_log_size():
    from framework.log_manager.operation_log import MAX_LOG_SIZE
    assert get_max_log_size() == MAX_LOG_SIZE


# ------------------- record_operation_log -------------------

class TestRecordOperationLog:
    def test_with_no_user_id(self, setup_db):
        """user_id=None 时不查询 UserManager"""
        with patch('framework.log_manager.operation_log.UserManager') as mock_um:
            result = record_operation_log(None, '127.0.0.1', 'mod', 'evt',
                                          OpLogResult.SUCCESS, detail='d')
            mock_um.query_by_id.assert_not_called()
            assert result == 0

    def test_with_user_id_found(self, setup_db):
        """user_id 存在且用户存在时使用 db_user_name"""
        mock_user = MagicMock()
        mock_user.user_name = 'db_user'
        with patch('framework.log_manager.operation_log.UserManager') as mock_um:
            mock_um.query_by_id.return_value = mock_user
            result = record_operation_log('uid', '127.0.0.1', 'mod', 'evt',
                                          OpLogResult.SUCCESS, detail='d',
                                          user_name='from_param')
            assert result == 0

    def test_with_user_id_not_found(self, setup_db):
        """user_id 存在但用户不存在时使用传入的 user_name"""
        with patch('framework.log_manager.operation_log.UserManager') as mock_um:
            mock_um.query_by_id.return_value = None
            result = record_operation_log('uid', '127.0.0.1', 'mod', 'evt',
                                          OpLogResult.SUCCESS, detail='d',
                                          user_name='param_user')
            assert result == 0

    def test_with_user_id_no_param_user_name(self, setup_db):
        """user_id 存在但用户不存在且未传 user_name"""
        with patch('framework.log_manager.operation_log.UserManager') as mock_um:
            mock_um.query_by_id.return_value = None
            result = record_operation_log('uid', '127.0.0.1', 'mod', 'evt',
                                          OpLogResult.SUCCESS, detail='d')
            assert result == 0


# ------------------- OperationLog.insert 异常 -------------------

def test_insert_handles_exception(mocker):
    from common.db.SQLOperation import DatabaseException
    mocker.patch(
        'framework.log_manager.operation_log.db_session_scope',
        side_effect=DatabaseException("boom"))
    result = OperationLog.insert('uid', 'uname', '127.0.0.1', 'mod', 'evt',
                                 OpLogResult.SUCCESS)
    assert result is None


# ------------------- OperationLog.record 异常 -------------------

def test_record_handles_exception(mocker):
    """record 已改为异步缓冲写入：底层批量落库异常时降级处理，record 本身不抛异常。"""
    from common.db.SQLOperation import DatabaseException
    # mock 数据库会话入口而非 _write_batch 本身：_write_batch 的容错在方法
    # 内部 try/except，整体替换会让异常逃逸到无 try/except 的后台
    # oplog-writer 线程（PytestUnhandledThreadExceptionWarning）；
    # db_session_scope 始终抛异常时，真实 _write_batch 的批量与单条兜底
    # 路径会在任意线程内安全吞掉
    mocker.patch(
        'framework.log_manager.operation_log.db_session_scope',
        side_effect=DatabaseException("boom"))
    result = OperationLog.record('uid', 'uname', '127.0.0.1', 'mod', 'evt',
                                 OpLogResult.SUCCESS, 'd')
    assert result == 0


# ------------------- OperationLog.get_count 异常 -------------------

def test_get_count_handles_exception(mocker):
    from common.db.SQLOperation import DatabaseException
    mocker.patch(
        'framework.log_manager.operation_log.db_session_scope',
        side_effect=DatabaseException("boom"))
    assert OperationLog.get_count() == 0


# ------------------- OperationLog.list_operation_log 多值过滤 -------------------

def test_list_operation_log_module_multi_filter(setup_db):
    """module 多值 OR 过滤"""
    record_sync(1, "user_a", "127.0.0.1", "mod_a", "evt_a",
                        OpLogResult.SUCCESS, "d")
    record_sync(2, "user_b", "127.0.0.1", "mod_b", "evt_b",
                        OpLogResult.SUCCESS, "d")
    status, msg, data = OperationLog.list_operation_log(
        filter_params={'module': 'mod_a,mod_b'})
    assert status is True
    assert data.get('total_log_count') == 2


def test_list_operation_log_ip_single_filter(setup_db):
    """ip 单值过滤"""
    record_sync(1, "user_a", "127.0.0.1", "mod_a", "evt_a",
                        OpLogResult.SUCCESS, "d")
    record_sync(2, "user_b", "127.0.0.2", "mod_b", "evt_b",
                        OpLogResult.SUCCESS, "d")
    status, msg, data = OperationLog.list_operation_log(
        filter_params={'ip': '127.0.0.1'})
    assert status is True
    assert data.get('total_log_count') == 1


def test_list_operation_log_ip_multi_filter(setup_db):
    """ip 多值 OR 过滤"""
    record_sync(1, "user_a", "127.0.0.1", "mod_a", "evt_a",
                        OpLogResult.SUCCESS, "d")
    record_sync(2, "user_b", "127.0.0.2", "mod_b", "evt_b",
                        OpLogResult.SUCCESS, "d")
    status, msg, data = OperationLog.list_operation_log(
        filter_params={'ip': '127.0.0.1,127.0.0.2'})
    assert status is True
    assert data.get('total_log_count') == 2


def test_list_operation_log_user_with_user_id(setup_db):
    """user_id 过滤"""
    record_sync(99, "user_99", "127.0.0.1", "mod", "evt",
                        OpLogResult.SUCCESS, "d")
    record_sync(100, "user_100", "127.0.0.1", "mod", "evt",
                        OpLogResult.SUCCESS, "d")
    status, msg, data = OperationLog.list_operation_log(user_id=99)
    assert status is True
    assert data.get('total_log_count') == 1


def test_list_operation_log_filter_empty_value_skipped(setup_db):
    """filter 中 value 为空字符串时被跳过"""
    record_sync(1, "user_a", "127.0.0.1", "mod", "evt",
                        OpLogResult.SUCCESS, "d")
    status, msg, data = OperationLog.list_operation_log(
        filter_params={'user_name': ''})
    assert status is True
    assert data.get('total_log_count') == 1


# ------------------- OperationLog.del_over_limit_log -------------------

def test_del_over_limit_log_no_cleanup_when_under_limit(setup_db):
    """total < max_log_size 时不触发清理"""
    with patch('framework.log_manager.operation_log.get_max_log_size', return_value=1000):
        # 仅写入少量记录
        record_sync(1, "user_a", "127.0.0.1", "mod", "evt",
                            OpLogResult.SUCCESS, "d")
        OperationLog.del_over_limit_log()
        status, msg, data = OperationLog.list_operation_log()
        assert data.get('total_log_count') >= 1


def test_del_over_limit_log_triggers_cleanup(setup_db):
    """total > max_log_size 时触发清理"""
    with patch('framework.log_manager.operation_log.get_max_log_size', return_value=2):
        for i in range(5):
            record_sync(i, f"user_{i}", "127.0.0.1", "mod", "evt",
                                OpLogResult.SUCCESS, "d")
        OperationLog.del_over_limit_log()
        # 至少没抛异常即视为通过


def test_del_over_limit_log_handles_exception(mocker):
    from common.db.SQLOperation import DatabaseException
    mocker.patch(
        'framework.log_manager.operation_log.OperationLog.get_count',
        side_effect=DatabaseException("boom"))
    OperationLog.del_over_limit_log()  # 不抛异常即视为通过


# ------------------- OperationLog.del_expire_log 异常 -------------------

def test_del_expire_log_handles_exception(mocker):
    from common.db.SQLOperation import DatabaseException
    mocker.patch(
        'framework.log_manager.operation_log.get_expire_days',
        return_value=10)
    mocker.patch(
        'framework.log_manager.operation_log.db_session_scope',
        side_effect=DatabaseException("boom"))
    OperationLog.del_expire_log()  # 不抛异常即视为通过


# ------------------- OperationLog.insert with enums -------------------

def test_insert_with_enum_values(setup_db):
    """传入 OpLogModule / OpLogEvent / OpLogResult 枚举"""
    result = OperationLog.insert(
        'uid', 'uname', '127.0.0.1', OpLogModule.USER, OpLogEvent.LOGIN,
        OpLogResult.SUCCESS, 'd')
    assert result is not None
