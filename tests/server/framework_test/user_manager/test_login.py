import os
import sys
import importlib.util

import copy
import random
import string
import time

import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from common.response.response_code import ResponseCode
from framework.config_manager.config import LOCKOUT_TIME_LIMIT
from framework.user_manager.login_manager import login
from framework.user_manager.user_db import UserStatus, encrypt_password, Role, UserFailedLogin, \
    IPFailedLogin, MAX_FAILED

# 导入 conftest 中的共享函数
# 由于 conftest 在同一个目录下，使用相对导入
from .conftest import setup_test_database_helper


def generate_random_string(length=10):
    """
    生成一个指定长度的随机字符串。

    :param length: 字符串的长度，默认为10。
    :return: 生成的随机字符串。
    """
    # 定义字符集
    characters = string.ascii_letters + string.digits + string.punctuation

    # 生成随机字符串
    random_string = ''.join(random.choice(characters) for _ in range(length))

    return random_string


random_string = generate_random_string()


@pytest.fixture
def mock_user_db():
    """模拟 UserManager 的方法，并设置测试数据库环境"""
    # 使用 conftest.py 中的共享函数设置数据库
    for context in setup_test_database_helper(create_tables=True):
        # Mock UserManager
        with patch('framework.user_manager.login_manager.UserManager') as mock_db:
            mock_user = MagicMock()
            mock_user.configure_mock(
                user_id="mock_user_1",
                user_name="test_user",
                status=UserStatus.NORMAL,
                role=Role.NORMAL,
                pw=encrypt_password(random_string),  # 确保这里有值
                exp_time=None,
                last_login=None,
                last_logout=None,
                time_pw_reset=int(time.time()),
                is_first_login=False
            )
            mock_db.query.return_value = mock_user
            mock_db.update.return_value = True
            mock_db.list_all.return_value = []
            yield mock_db


@pytest.fixture
def mock_sys_config_service():
    """模拟 SysConfig 的方法"""
    with patch(
            'framework.user_manager.login_manager.SysConfig.query_system_configuration') as mock_query:
        def config_side_effect(key):
            configs = {
                'max_online_users': (True, '10'),  # 最大在线用户限制
                'session_timeout': (True, '30'),  # 会话超时，单位：分钟
                'password_timeout': (True, '7'),  # 密钥超时，单位：分钟
                'lock_time': (True, '10'),  # 用户锁定时间，单位：分钟
                'max_password_failed': (True, '5')
            }
            return configs.get(key, (False, '0'))

        mock_query.side_effect = config_side_effect
        yield mock_query


@pytest.fixture
def mock_operation_log():
    """模拟 operation_log"""
    with patch('framework.user_manager.login_manager.operation_log') as mock_operation_log:
        yield mock_operation_log


def test_login_success(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试成功登录"""
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is True
    assert user["user_id"] == "mock_user_1"
    assert code == ResponseCode.OK


def test_login_wrong_password(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试密码错误"""
    status, user, code = login("test_user", "wrong", "127.0.0.1")
    assert status is False
    assert code == ResponseCode.USER_AUTH_FAILED


def test_account_locked_after_failed_attempts(mock_user_db, mock_sys_config_service,
                                              mock_operation_log):
    """测试多次失败后用户被锁定"""
    mock_user = copy.deepcopy(mock_user_db.query.return_value)
    for _ in range(2):
        mock_user_db.query.return_value = copy.deepcopy(mock_user)
        login("test_user", "wrong", "127.0.0.1")
    for _ in range(MAX_FAILED - 2):
        mock_user_db.query.return_value = copy.deepcopy(mock_user)
        login("test_user", "wrong", "192.0.0.1")
    mock_user_db.query.return_value = copy.deepcopy(mock_user)
    mock_user_db.query.return_value.status = UserStatus.LOCKED
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is False
    assert code == ResponseCode.USER_LOCKED


def test_account_unlock_after_timeout(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试锁定超时后解锁"""
    mock_user_db.query.return_value.status = UserStatus.LOCKED
    last_failed_time = (datetime.now() - timedelta(minutes=int(LOCKOUT_TIME_LIMIT) + 1)).strftime(
        "%Y-%m-%d %H:%M:%S")
    with patch('framework.user_manager.login_manager.validate_pw', return_value=(True, False)):
        status, user, code = login("test_user", random_string, "127.0.0.1")
        assert status is True
        assert code == ResponseCode.OK


@patch(f"framework.user_manager.login_manager.UserSessionCache.get_online_users",
       return_value=[None] * 4)
@patch(f"framework.user_manager.login_manager.SysConfig.query_system_configuration",
       return_value=(True, 4, ResponseCode.OK))
def test_max_online_users_reached(mock_sys_config, mock_online_user, mock_user_db,
                                  mock_sys_config_service, mock_operation_log):
    """测试超过最大在线用户限制"""
    # mock_user_db.list_all.return_value = [
    #     MagicMock(exp_time=(datetime.now() + timedelta(minutes=10)).timestamp())
    #     for _ in range(10)
    # ]
    mock_user_db.list_all.return_value = [
        MagicMock()
        for _ in range(10)
    ]
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is False
    assert code == ResponseCode.USER_OVER_MAX_ONLINE


def test_first_login(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试首次登录"""
    mock_user_db.query.return_value.is_first_login = True
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is False  # 首次登录返回 False
    assert code == ResponseCode.USER_FIRST_LOGIN


def test_pw_timeout(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试密钥过期"""
    mock_user_db.query.return_value.time_pw_reset = int(time.time()) - 7 * 24 * 60 * 60 - 10
    mock_user_db.query.return_value.is_first_login = True
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is False  # 首次登录返回 False
    assert code == ResponseCode.PW_TIMEOUT


def test_login_fail_times(mock_user_db, mock_sys_config_service, mock_operation_log):
    """测试密码错误"""
    status, user, code = login("test_user", "wrong", "127.0.0.1")
    assert status is False
    assert code == ResponseCode.USER_AUTH_FAILED
    mock_user_db.query.return_value.pw = encrypt_password(random_string)
    status, user, code = login("test_user", random_string, "127.0.0.1")
    assert status is True
    assert user.get('auth_failed') == 1
    assert code == ResponseCode.OK
