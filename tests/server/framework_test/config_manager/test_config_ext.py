"""
为 config_manager/config.py 补充测试。
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.response.response_code import ResponseCode
from framework.config_manager.config import (
    SysConfig, ConfigKeys, _check_config_param, register_callback,
    ConfigCheckLimit, ConfigRegexCheckLimit, PROXY_RE, NO_PROXY_RE,
    DEFAULT_VALUE, SYSCONFIG_CHECK_LIMITS, config_cache, config_callbacks,
)


# ------------------- SysConfig.query_by_name -------------------

class TestQueryByName:
    def test_found(self, mocker):
        mock_config = MagicMock()
        mock_config.config_name = 'k'
        mock_config.config_value = 'v'
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            return_value=_ctx_mgr(mock_session))
        result = SysConfig.query_by_name('k')
        assert result == ('k', 'v')

    def test_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            return_value=_ctx_mgr(mock_session))
        assert SysConfig.query_by_name('k') is None

    def test_exception(self, mocker):
        from common.db.SQLOperation import DatabaseException
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            side_effect=DatabaseException("boom"))
        assert SysConfig.query_by_name('k') is None


def _ctx_mgr(session):
    """辅助：构造一个 with 块返回 session 的 context manager"""
    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *args):
            return None

    return _Ctx()


# ------------------- SysConfig._update_value -------------------

class TestUpdateValue:
    def test_update_same_value_returns_not_change(self, mocker):
        """值未变化时返回 SYSCONFIG_VALUE_NOT_CHANGE"""
        mock_config = MagicMock()
        mock_config.config_value = '10'
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            return_value=_ctx_mgr(mock_session))
        status, code = SysConfig._update_value(ConfigKeys.MAX_ONLINE_USERS, '10')
        assert status is False
        assert code == ResponseCode.SYSCONFIG_VALUE_NOT_CHANGE

    def test_update_new_value(self, mocker):
        """值变化时更新"""
        mock_config = MagicMock()
        mock_config.config_value = '5'
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            return_value=_ctx_mgr(mock_session))
        status, code = SysConfig._update_value(ConfigKeys.MAX_ONLINE_USERS, '10')
        assert status is True
        assert code == ResponseCode.OK

    def test_insert_new_config(self, mocker):
        """不存在时插入新记录"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            return_value=_ctx_mgr(mock_session))
        status, code = SysConfig._update_value(ConfigKeys.MAX_ONLINE_USERS, '10')
        assert status is True
        mock_session.add.assert_called_once()

    def test_update_exception(self, mocker):
        from common.db.SQLOperation import DatabaseException
        mocker.patch(
            'framework.config_manager.config.db_session_scope',
            side_effect=DatabaseException("boom"))
        status, code = SysConfig._update_value(ConfigKeys.MAX_ONLINE_USERS, '10')
        assert status is False
        assert code == ResponseCode.DB_EXCEPTION


# ------------------- SysConfig.query_system_configuration -------------------

class TestQuerySystemConfigurationNoCache:
    def test_no_cache_query_db(self, mock_db_file, mocker):
        """cached=False 时绕过缓存"""
        SysConfig.list_all()
        status, value, code = SysConfig.query_system_configuration(
            ConfigKeys.MAX_ONLINE_USERS, cached=False)
        assert status is True
        assert code == ResponseCode.OK


# ------------------- SysConfig.update -------------------

class TestSysConfigUpdate:
    def test_update_invalid_key(self, mock_db_file):
        status, code = SysConfig.update('invalid_key', 'value')
        assert status is False
        assert code == ResponseCode.SYSCONFIG_INVALID_KEY

    def test_update_invalid_value(self, mock_db_file):
        status, code = SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '999')
        assert status is False

    def test_update_with_callback_exception(self, mock_db_file, mocker):
        """callback 抛异常被吞掉"""
        SysConfig.list_all()

        # 注册一个会抛异常的 callback
        def bad_callback(v):
            raise RuntimeError("callback failed")

        config_callbacks[ConfigKeys.MAX_ONLINE_USERS] = bad_callback
        try:
            status, code = SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '5')
            assert status is True  # 不影响返回值
        finally:
            config_callbacks.pop(ConfigKeys.MAX_ONLINE_USERS, None)

    def test_update_with_callback_success(self, mock_db_file):
        SysConfig.list_all()
        called = []

        def good_callback(v):
            called.append(v)

        config_callbacks[ConfigKeys.MAX_ONLINE_USERS] = good_callback
        try:
            status, code = SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '5')
            assert status is True
            assert called == ['5']
        finally:
            config_callbacks.pop(ConfigKeys.MAX_ONLINE_USERS, None)


# ------------------- register_callback -------------------

class TestRegisterCallback:
    def test_register_valid_key(self):
        cb = lambda v: None
        status, code = register_callback(ConfigKeys.MAX_ONLINE_USERS, cb)
        assert status is True
        assert code is None
        # 清理
        config_callbacks.pop(ConfigKeys.MAX_ONLINE_USERS, None)

    def test_register_invalid_key(self):
        status, code = register_callback('invalid_key', lambda v: None)
        assert status is False
        assert code == ResponseCode.SYSCONFIG_INVALID_KEY


# ------------------- ConfigCheckLimit -------------------

class TestConfigCheckLimit:
    def test_enum_value(self):
        """enum_ 提供时返回 value in enum_"""
        chk = ConfigCheckLimit(enum_={'a', 'b'})
        assert chk('a') is True
        assert chk('c') is False

    def test_int_value_in_range(self):
        chk = ConfigCheckLimit(min_=0, max_=10)
        assert chk(5) is True
        assert chk(15) is False

    def test_int_string_value(self):
        chk = ConfigCheckLimit(min_=0, max_=10)
        assert chk('5') is True
        assert chk('15') is False

    def test_invalid_type(self):
        chk = ConfigCheckLimit(min_=0, max_=10)
        # list 不能 int()
        assert chk([]) is False

    def test_invalid_int_string(self):
        chk = ConfigCheckLimit(min_=0, max_=10)
        assert chk('abc') is False

    def test_particular_equal(self):
        chk = ConfigCheckLimit(min_=5, max_=10, particular_=0)
        assert chk(0) is True
        assert chk(7) is True
        assert chk(15) is False

    def test_particular_not_equal(self):
        chk = ConfigCheckLimit(min_=5, max_=10, particular_=0)
        assert chk(3) is False


# ------------------- ConfigRegexCheckLimit -------------------

class TestConfigRegexCheckLimit:
    def test_empty_value_nullable(self):
        chk = ConfigRegexCheckLimit(nullable=True)
        assert chk('') is True

    def test_empty_value_not_nullable(self):
        chk = ConfigRegexCheckLimit(nullable=False)
        assert chk('') is False

    def test_non_string_value(self):
        chk = ConfigRegexCheckLimit()
        assert chk(123) is True

    def test_too_long(self):
        chk = ConfigRegexCheckLimit(max_len=5)
        assert chk('abcdef') is False

    def test_pattern_match(self):
        chk = ConfigRegexCheckLimit(pattern=r'^\d+$')
        assert chk('123') is True

    def test_pattern_no_match(self):
        chk = ConfigRegexCheckLimit(pattern=r'^\d+$')
        assert chk('abc') is False

    def test_no_pattern(self):
        chk = ConfigRegexCheckLimit(pattern=None)
        assert chk('anything') is True


# ------------------- _check_config_param -------------------

class TestCheckConfigParam:
    def test_invalid_key(self):
        status, code = _check_config_param('unknown_key', 'value')
        assert status is False
        assert code == ResponseCode.SYSCONFIG_INVALID_KEY

    def test_docker_http_proxy_valid(self):
        status, code = _check_config_param(
            ConfigKeys.DOCKER_HTTP_PROXY, 'http://example.com')
        assert status is True

    def test_docker_http_proxy_invalid(self):
        status, code = _check_config_param(
            ConfigKeys.DOCKER_HTTP_PROXY, 'not a url')
        assert status is False
        assert code == ResponseCode.SYSCONFIG_INVALID_VALUE

    def test_docker_https_proxy_valid(self):
        status, code = _check_config_param(
            ConfigKeys.DOCKER_HTTPS_PROXY, 'https://example.com')
        assert status is True

    def test_docker_no_proxy_valid(self):
        status, code = _check_config_param(
            ConfigKeys.DOCKER_NO_PROXY, 'localhost,127.0.0.1')
        assert status is True

    def test_password_timeout_zero(self):
        """PASSWORD_PERMANENT=0 -> 允许 particular_=0"""
        status, code = _check_config_param(ConfigKeys.PW_TIMEOUT, '0')
        assert status is True

    def test_password_timeout_max(self):
        status, code = _check_config_param(ConfigKeys.PW_TIMEOUT, '360')
        assert status is True

    def test_password_timeout_out_of_range(self):
        status, code = _check_config_param(ConfigKeys.PW_TIMEOUT, '400')
        assert status is False
