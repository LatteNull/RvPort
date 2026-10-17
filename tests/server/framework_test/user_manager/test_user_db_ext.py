"""
补充测试，覆盖 user_db.py 中未覆盖的 UserPasswordHistory / UserFailedLogin /
UserLoginFailedTime / IPFailedLogin 等类的方法以及部分异常分支。
"""
import importlib.util
import os
import sqlite3
import sys
import time
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import common.db.SQLOperation as sql_op
from common.db.SQLOperation import Base, DB_INFO
from framework.user_manager import user_db
from framework.user_manager.user_db import (
    Role, UserStatus, UserManager, UserPasswordHistory,
    UserFailedLogin, UserLoginFailedTime, IPFailedLogin,
    encrypt_password,
)
from framework_test.public.random_pw import random_pw

test_pw = random_pw()

# 复用 user_manager/conftest.py 中的 helper
_conftest_path = os.path.join(os.path.dirname(__file__), 'conftest.py')
_conftest_spec = importlib.util.spec_from_file_location("conftest_module", _conftest_path)
_conftest_module = importlib.util.module_from_spec(_conftest_spec)
_conftest_spec.loader.exec_module(_conftest_module)
setup_test_database_helper = _conftest_module.setup_test_database_helper

SQL_FILE = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'scripts', 'install', 'sqlite.sql'))


def _run_all_sql(db_path):
    """执行合并后的安装 SQL 脚本"""
    if not os.path.isfile(SQL_FILE):
        return
    conn = sqlite3.connect(db_path)
    with open(SQL_FILE, "r") as f:
        sql = f.read()
        try:
            conn.executescript(sql)
            print(f"Executed SQL from: {SQL_FILE}")
        except Exception as e:
            print(f"Executed SQL error from: {SQL_FILE}: {e}")
    conn.commit()
    conn.close()


@pytest.fixture(scope="function")
def setup_db_with_user():
    """构造带 Admin 用户的测试数据库"""
    for context in setup_test_database_helper(create_tables=True, init_default_user=True):
        db_path, _, _, _ = context
        _run_all_sql(db_path)
        yield type('obj', (object,), {'name': db_path})()


@pytest.fixture(autouse=True)
def _reset_ip_failed_login_classvars():
    """每个测试前后恢复 IPFailedLogin 类变量默认值，避免污染其他测试"""
    IPFailedLogin.max_failed = user_db.IP_FAILED
    IPFailedLogin.ban_duration = user_db.IP_BAN_DURATION
    yield
    IPFailedLogin.max_failed = user_db.IP_FAILED
    IPFailedLogin.ban_duration = user_db.IP_BAN_DURATION


# ------------------- encrypt_password -------------------

def test_encrypt_password_with_custom_salt():
    """传入自定义 salt 时使用该 salt"""
    salt = b'abcdefghijkl'  # 12 字节
    encrypted = encrypt_password('mypassword', salt)
    assert encrypted.startswith(salt.hex())


def test_encrypt_password_default_salt():
    """不传 salt 时生成 12 字节随机 salt"""
    encrypted = encrypt_password('mypassword')
    # salt.hex() 长度 24（12 字节 -> 24 hex 字符） + dk 32 字节 -> 64 hex
    assert len(encrypted) == 24 + 64


# ------------------- UserManager.query 异常分支 -------------------

def test_query_returns_none_on_exception(setup_db_with_user):
    """query 内部抛 DatabaseException 时返回 None"""
    with patch('framework.user_manager.user_db.db_session_scope') as mock_scope:
        mock_scope.side_effect = user_db.DatabaseException("db error")
        result = UserManager.query(user_name='admin')
        assert result is None


def test_update_returns_false_on_exception(setup_db_with_user):
    """update 内部抛 DatabaseException 时返回 False"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert UserManager.update('uid', is_first_login=0) is False


def test_delete_user_returns_false_on_exception(setup_db_with_user):
    """delete_user 内部抛 DatabaseException 时返回 False"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert UserManager.delete_user('uid') is False


def test_save_returns_false_on_exception(setup_db_with_user):
    """save 内部抛 DatabaseException 时返回 (False, None)"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        ok, user_id = UserManager.save('foo', Role.NORMAL, test_pw)
        assert ok is False
        assert user_id is None


def test_list_all_local_returns_empty_on_exception(setup_db_with_user):
    """list_all_local 内部抛异常时返回空列表"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert UserManager.list_all_local() == []


def test_init_default_user_handles_exception(setup_db_with_user):
    """init_default_user 内部异常被吞掉"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserManager.init_default_user()  # 不抛异常即视为通过


def test_init_default_user_creates_when_missing(setup_db_with_user):
    """Admin 不存在时创建"""
    UserManager.delete_user(UserManager.query(user_name='Admin').user_id)
    UserManager.init_default_user()
    assert UserManager.query(user_name='Admin') is not None


def test_init_default_user_skips_when_existing(setup_db_with_user):
    """Admin 已存在时直接返回"""
    UserManager.init_default_user()
    UserManager.init_default_user()
    assert UserManager.query(user_name='Admin') is not None


def test_update_invalid_field_logs_warning(setup_db_with_user):
    """update 传入无效字段时不更新，仅记日志"""
    admin = UserManager.query(user_name='Admin')
    result = UserManager.update(admin.user_id, undefined_field='value')
    assert result is True  # 仍返回 True（有效字段为空）


def test_update_user_not_found(setup_db_with_user):
    """update 用户不存在时返回 False"""
    assert UserManager.update('non-existent-user-id', is_first_login=0) is False


def test_delete_user_not_found(setup_db_with_user):
    """delete_user 用户不存在时返回 False"""
    assert UserManager.delete_user('non-existent-user-id') is False


def test_list_all_local_with_selector(setup_db_with_user):
    """list_all_local 支持自定义 selector 条件"""
    UserManager.save('alice', Role.NORMAL, test_pw)
    UserManager.save('bob', Role.NORMAL, test_pw)
    users = UserManager.list_all_local(selector=('user_name=?', ['alice']))
    assert len(users) == 1
    assert users[0].user_name == 'alice'


# ------------------- UserPasswordHistory -------------------

def test_password_history_save_and_check(setup_db_with_user):
    """保存历史后 is_password_in_history 能识别旧密码"""
    status, user_id = UserManager.save('alice', Role.NORMAL, test_pw)
    UserPasswordHistory.save_password_history(user_id, 'OldPwd#123')
    assert UserPasswordHistory.is_password_in_history(user_id, 'OldPwd#123') is True
    assert UserPasswordHistory.is_password_in_history(user_id, 'OtherPwd#456') is False


def test_password_history_save_limit(setup_db_with_user):
    """保存多次后超出 MAX_HISTORY 的旧记录被删除"""
    status, user_id = UserManager.save('alice', Role.NORMAL, test_pw)
    for i in range(user_db.MAX_HISTORY + 2):
        UserPasswordHistory.save_password_history(user_id, f'OldPwd#{i}xyz')
    # 此时 is_password_in_history 仅检查最近 MAX_HISTORY+1 条
    # 最早的 'OldPwd#0xyz' 应已被剔除
    assert UserPasswordHistory.is_password_in_history(user_id, 'OldPwd#0xyz') is False


def test_is_password_in_history_handles_exception(setup_db_with_user):
    """is_password_in_history 内部异常返回 False"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert UserPasswordHistory.is_password_in_history('uid', 'pwd') is False


def test_save_password_history_handles_exception(setup_db_with_user):
    """save_password_history 内部异常时不向外抛出"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserPasswordHistory.save_password_history('uid', 'pwd')  # 不抛异常即视为通过


def test_is_password_in_history_handles_value_error(setup_db_with_user):
    """密码历史中存在非法 salt 时 is_password_in_history 返回 False"""
    status, user_id = UserManager.save('alice', Role.NORMAL, test_pw)
    # 直接插入一条非法的 password 历史记录
    conn = sqlite3.connect(setup_db_with_user.name)
    conn.execute(
        "INSERT INTO user_password_history (user_id, password, created_at) VALUES (?, ?, ?)",
        (user_id, 'zzz-not-hex', int(time.time_ns())))
    conn.commit()
    conn.close()
    # salt 解析时 int(...) 会抛 ValueError，被 except 捕获
    assert UserPasswordHistory.is_password_in_history(user_id, 'whatever') is False


# ------------------- UserFailedLogin -------------------

def test_record_failed_login_and_count(setup_db_with_user):
    """记录失败登录后能查询到"""
    UserFailedLogin.record_failed_login('alice', now=1000)
    UserFailedLogin.record_failed_login('alice', now=1001)
    count, last = UserFailedLogin.get_failed_count('alice', now_time=2000)
    assert count == 2
    assert last == 1001


def test_get_failed_count_returns_zero_when_empty(setup_db_with_user):
    """无失败记录时 count=0"""
    count, last = UserFailedLogin.get_failed_count('ghost', now_time=2000)
    assert count == 0
    assert last is None


def test_get_failed_count_handles_exception(setup_db_with_user):
    """get_failed_count 内部异常时返回 (0, None)"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        count, last = UserFailedLogin.get_failed_count('alice', now_time=1000)
        assert count == 0
        assert last is None


def test_record_failed_login_handles_exception(setup_db_with_user):
    """record_failed_login 内部异常被吞掉"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserFailedLogin.record_failed_login('alice')  # 不抛异常即视为通过


def test_clean_failed_record(setup_db_with_user):
    """清理后再查应为 0"""
    UserFailedLogin.record_failed_login('alice', now=1000)
    UserFailedLogin.clean_failed_record('alice')
    count, _ = UserFailedLogin.get_failed_count('alice', now_time=2000)
    assert count == 0


def test_clean_failed_record_handles_exception(setup_db_with_user):
    """clean_failed_record 内部异常被吞掉"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserFailedLogin.clean_failed_record('alice')  # 不抛异常即视为通过


def test_check_lock_status_locked(setup_db_with_user):
    """超过 max_failed 且未超 timeout 时返回 True"""
    with patch('framework.user_manager.user_db.SysConfig') as mock_cfg:
        mock_cfg.query_system_configuration.side_effect = [(True, '1', None), (True, '3', None)]
        for i in range(5):
            UserFailedLogin.record_failed_login('alice', now=1000 + i)
        assert UserFailedLogin.check_lock_status('alice', now=1010) is True


def test_check_lock_status_unlocked_after_timeout(setup_db_with_user):
    """超过 timeout 后清理记录并返回 False"""
    with patch('framework.user_manager.user_db.SysConfig') as mock_cfg:
        mock_cfg.query_system_configuration.side_effect = [(True, '1', None), (True, '3', None)]
        for i in range(5):
            UserFailedLogin.record_failed_login('alice', now=1000)
        # 5 分钟后已超 timeout * 60 = 60s
        assert UserFailedLogin.check_lock_status('alice', now=2000) is False


def test_check_lock_status_not_locked(setup_db_with_user):
    """失败次数不足时返回 False"""
    with patch('framework.user_manager.user_db.SysConfig') as mock_cfg:
        mock_cfg.query_system_configuration.side_effect = [(True, '1', None), (True, '5', None)]
        UserFailedLogin.record_failed_login('alice', now=1000)
        assert UserFailedLogin.check_lock_status('alice', now=1010) is False


def test_record_and_check_locks_when_threshold_reached(setup_db_with_user):
    """达到阈值时 record_and_check 返回 True"""
    with patch('framework.user_manager.user_db.SysConfig') as mock_cfg:
        mock_cfg.query_system_configuration.side_effect = [
            (True, '1', None), (True, '3', None),  # check_lock_status
            (True, '1', None), (True, '3', None),  # record_and_check
        ]
        # 预置已 2 次失败
        UserFailedLogin.record_failed_login('alice', now=1000)
        UserFailedLogin.record_failed_login('alice', now=1001)
        # 第 3 次：count(2) < max_failed(3) 不锁，再记 1 次 -> 返回 True
        assert UserFailedLogin.record_and_check('alice', now=1002) is True


def test_record_and_check_resets_after_timeout(setup_db_with_user):
    """超时后 record_and_check 先清理再记录新失败"""
    with patch('framework.user_manager.user_db.SysConfig') as mock_cfg:
        mock_cfg.query_system_configuration.side_effect = [
            (True, '1', None), (True, '3', None),
            (True, '1', None), (True, '3', None),
        ]
        UserFailedLogin.record_failed_login('alice', now=1000)
        UserFailedLogin.record_failed_login('alice', now=1001)
        UserFailedLogin.record_failed_login('alice', now=1002)
        # 已锁，超时后应清理，重新计数
        result = UserFailedLogin.record_and_check('alice', now=5000)
        assert result is False  # 单次不够锁


# ------------------- UserLoginFailedTime -------------------

def test_user_login_failed_time_record_and_count(setup_db_with_user):
    """record_user_failed + get_count + clean"""
    UserLoginFailedTime.record_user_failed('uid-1', '127.0.0.1')
    UserLoginFailedTime.record_user_failed('uid-1', '127.0.0.1')
    assert UserLoginFailedTime.get_count('uid-1') == 2
    UserLoginFailedTime.clean_failed_record('uid-1')
    assert UserLoginFailedTime.get_count('uid-1') == 0


def test_user_login_failed_time_get_count_zero_when_empty(setup_db_with_user):
    """无记录时 get_count 返回 0"""
    assert UserLoginFailedTime.get_count('uid-none') == 0


def test_user_login_failed_time_record_handles_exception(setup_db_with_user):
    """record_user_failed 异常被吞掉"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserLoginFailedTime.record_user_failed('uid-1', '127.0.0.1')


def test_user_login_failed_time_get_count_handles_exception(setup_db_with_user):
    """get_count 异常时返回 0"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert UserLoginFailedTime.get_count('uid-1') == 0


def test_user_login_failed_time_clean_handles_exception(setup_db_with_user):
    """clean_failed_record 异常被吞掉"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        UserLoginFailedTime.clean_failed_record('uid-1')


# ------------------- IPFailedLogin -------------------

def test_ip_failed_login_setters():
    """set_max_failed / set_ban_duration 类方法"""
    IPFailedLogin.set_max_failed(7)
    IPFailedLogin.set_ban_duration(30)
    assert IPFailedLogin.max_failed == 7
    assert IPFailedLogin.ban_duration == 30


def test_ip_failed_login_record_and_check_lock(setup_db_with_user):
    """超过阈值后锁定并返回 True"""
    IPFailedLogin.set_max_failed(2)
    IPFailedLogin.set_ban_duration(120)
    ip = '10.0.0.1'
    now = time.time()
    # 第一次：count=1，未锁
    assert IPFailedLogin.record_and_check(ip, now=now) is False
    # 第二次：count=2，锁定
    assert IPFailedLogin.record_and_check(ip, now=now + 1) is True


def test_ip_failed_login_get_lock_status_unlocked(setup_db_with_user):
    """未锁定时 get_lock_status 返回 False"""
    IPFailedLogin.set_max_failed(5)
    IPFailedLogin.set_ban_duration(120)
    assert IPFailedLogin.get_lock_status('10.0.0.9') is False


def test_ip_failed_login_get_lock_status_locked(setup_db_with_user):
    """锁定且未过 ban_duration 时 get_lock_status 返回 True"""
    IPFailedLogin.set_max_failed(1)
    IPFailedLogin.set_ban_duration(120)
    ip = '10.0.0.2'
    now = time.time()
    IPFailedLogin.record_and_check(ip, now=now)
    assert IPFailedLogin.get_lock_status(ip, now=now + 1) is True


def test_ip_failed_login_get_lock_status_after_ban_expired(setup_db_with_user):
    """锁定但已过 ban_duration 时 get_lock_status 返回 False"""
    IPFailedLogin.set_max_failed(1)
    IPFailedLogin.set_ban_duration(1)  # 1 分钟
    ip = '10.0.0.3'
    now = time.time()
    IPFailedLogin.record_and_check(ip, now=now)
    # 时间已超过 ban_duration * 60s
    assert IPFailedLogin.get_lock_status(ip, now=now + 120) is False


def test_ip_failed_login_record_and_check_handles_exception(setup_db_with_user):
    """record_and_check 内部异常时返回 False"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert IPFailedLogin.record_and_check('10.0.0.4') is False


def test_ip_failed_login_get_lock_status_handles_exception(setup_db_with_user):
    """get_lock_status 内部异常时返回 False"""
    with patch('framework.user_manager.user_db.db_session_scope',
               side_effect=user_db.DatabaseException("db error")):
        assert IPFailedLogin.get_lock_status('10.0.0.5') is False


def test_ip_failed_login_get_lock_status_no_records(setup_db_with_user):
    """没有失败记录时返回 False（max_time_result 路径）"""
    # 直接走 except 分支前的早返回
    assert IPFailedLogin.get_lock_status('8.8.8.8') is False


def test_ip_failed_login_get_lock_status_locked_zero():
    """locked 字段为 0 时返回 False"""
    IPFailedLogin.set_max_failed(1)
    IPFailedLogin.set_ban_duration(120)
    with patch('framework.user_manager.user_db.db_session_scope') as mock_scope:
        mock_session = MagicMock()
        mock_scope.return_value.__enter__.return_value = mock_session
        mock_scope.return_value.__exit__.return_value = None

        # 模拟 max_time 查询返回 locked=0
        max_time_result = MagicMock()
        max_time_result.max_time = 1000
        lock_result = MagicMock()
        lock_result.locked = 0
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            max_time_result, lock_result]
        assert IPFailedLogin.get_lock_status('9.9.9.9', now=2000) is False
