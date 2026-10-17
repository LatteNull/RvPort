"""api_key_manager.py 单元测试"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from flask import Flask

from plugin.codemig.ai_assistant.api_key_manager import (
    _has_whitespace_or_control_chars,
    _is_valid_http_url,
    _validate_api_config_params,
    _record_op_log,
    _safe_model_fmt,
    do_test_api_key,
    _test_cursor_api_key,
    _test_openai_api_key,
    do_del_api_key_from_db,
    do_store_api_key_to_db,
    get_agent_config_from_db,
    do_get_api_key_from_db,
    do_set_default_api_key_to_db,
    do_set_model_default_api_key_to_db,
    store_api_key_to_db,
    get_api_key_from_db,
    del_api_key_from_db,
    test_api_key_by_post as _do_test_api_key_by_post,
    set_default_api_key_to_db,
    set_model_default_api_key_to_db,
)


# ---------------------------------------------------------------------------
# _has_whitespace_or_control_chars
# ---------------------------------------------------------------------------
class TestHasWhitespaceOrControlChars:
    def test_no_whitespace(self):
        assert _has_whitespace_or_control_chars("abc123") is False

    def test_space(self):
        assert _has_whitespace_or_control_chars("a b") is True

    def test_tab(self):
        assert _has_whitespace_or_control_chars("a\tb") is True

    def test_newline(self):
        assert _has_whitespace_or_control_chars("a\nb") is True

    def test_control_char(self):
        assert _has_whitespace_or_control_chars("a\x00b") is True

    def test_empty(self):
        assert _has_whitespace_or_control_chars("") is False


# ---------------------------------------------------------------------------
# _is_valid_http_url
# ---------------------------------------------------------------------------
class TestIsValidHttpUrl:
    def test_valid_http(self):
        assert _is_valid_http_url("http://example.com") is True

    def test_valid_https(self):
        assert _is_valid_http_url("https://example.com/path") is True

    def test_ftp(self):
        assert _is_valid_http_url("ftp://example.com") is False

    def test_no_scheme(self):
        assert _is_valid_http_url("example.com") is False

    def test_whitespace(self):
        assert _is_valid_http_url("http://ex ample.com") is False

    def test_no_netloc(self):
        assert _is_valid_http_url("http:/example") is False

    def test_empty(self):
        assert _is_valid_http_url("") is False


# ---------------------------------------------------------------------------
# _validate_api_config_params
# ---------------------------------------------------------------------------
class TestValidateApiConfigParams:
    def test_valid(self):
        ok, msg = _validate_api_config_params("key123", "https://api.test.com", "gpt-4")
        assert ok is True
        assert msg == ""

    def test_empty_api_key(self):
        ok, msg = _validate_api_config_params("", "https://api.test.com", "gpt-4")
        assert ok is False
        assert "API Key" in msg

    def test_empty_base_url(self):
        ok, msg = _validate_api_config_params("key123", "", "gpt-4")
        assert ok is False

    def test_empty_model(self):
        ok, msg = _validate_api_config_params("key123", "https://api.test.com", "")
        assert ok is False

    def test_whitespace_in_api_key(self):
        ok, msg = _validate_api_config_params("key 123", "https://api.test.com", "gpt-4")
        assert ok is False
        assert "非法字符" in msg

    def test_invalid_base_url(self):
        ok, msg = _validate_api_config_params("key123", "not-a-url", "gpt-4")
        assert ok is False

    def test_invalid_model(self):
        ok, msg = _validate_api_config_params("key123", "https://api.test.com", "model with spaces")
        assert ok is False


# ---------------------------------------------------------------------------
# _record_op_log
# ---------------------------------------------------------------------------
class TestRecordOpLog:
    @patch('plugin.codemig.ai_assistant.api_key_manager.operation_log')
    def test_success(self, mock_log):
        _record_op_log("user1", "127.0.0.1", "event", "result", "detail")
        mock_log.record_operation_log.assert_called_once()

    @patch('plugin.codemig.ai_assistant.api_key_manager.operation_log')
    def test_exception_swallowed(self, mock_log):
        mock_log.record_operation_log.side_effect = RuntimeError("db down")
        # Should not raise
        _record_op_log("user1", "127.0.0.1", "event", "result", "detail")


# ---------------------------------------------------------------------------
# _safe_model_fmt
# ---------------------------------------------------------------------------
class TestSafeModelFmt:
    def test_with_value(self):
        assert _safe_model_fmt("gpt-4") == "gpt-4"

    def test_none(self):
        assert _safe_model_fmt(None) == "(empty)"

    def test_empty(self):
        assert _safe_model_fmt("") == "(empty)"

    def test_whitespace(self):
        assert _safe_model_fmt("  ") == "(empty)"


# ---------------------------------------------------------------------------
# _test_cursor_api_key
# ---------------------------------------------------------------------------
class TestTestCursorApiKey:
    def _mock_subprocess_module(self):
        """Patch the whole subprocess module in the source, preserving exception classes."""
        import subprocess as real_sp
        mock_sp = MagicMock()
        mock_sp.TimeoutExpired = real_sp.TimeoutExpired
        mock_sp.SubprocessError = real_sp.SubprocessError
        return mock_sp

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_success(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_401_error(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Unauthorized 401"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "无效" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_429_rate_limit(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "rate limit 429"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "配额" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_403_forbidden(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Forbidden 403"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "拒绝" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_other_error(self, mock_subprocess):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "some unknown error"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_timeout(self, mock_subprocess):
        mock_subprocess.run.side_effect = __import__('subprocess').TimeoutExpired(cmd="docker", timeout=120)
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "超时" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_docker_not_found(self, mock_subprocess):
        mock_subprocess.run.side_effect = FileNotFoundError("docker not found")
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "Docker" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_permission_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = PermissionError("no permission")
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "权限" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_unicode_decode_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "err")
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "解码" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_subprocess_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = __import__('subprocess').SubprocessError("failed")
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "子进程" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.subprocess')
    def test_os_error(self, mock_subprocess):
        mock_subprocess.run.side_effect = OSError(12, "os error")
        mock_subprocess.TimeoutExpired = __import__('subprocess').TimeoutExpired
        mock_subprocess.SubprocessError = __import__('subprocess').SubprocessError

        result = _test_cursor_api_key("key", "model", "", "")
        assert result["code"] == -1
        assert "系统错误" in result["msg"]


# ---------------------------------------------------------------------------
# _test_openai_api_key
# ---------------------------------------------------------------------------
class TestTestOpenaiApiKey:
    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = _test_openai_api_key("sk-123", "https://api.test.com", "gpt-4")
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_401(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        result = _test_openai_api_key("bad-key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "无效" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_429(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        result = _test_openai_api_key("key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "配额" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_403(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_post.return_value = mock_resp

        result = _test_openai_api_key("key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "拒绝" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_other_status(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "server busy"}}
        mock_post.return_value = mock_resp

        result = _test_openai_api_key("key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "500" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_timeout(self, mock_post):
        mock_post.side_effect = __import__('requests').exceptions.Timeout("timed out")

        result = _test_openai_api_key("key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "超时" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager.requests.post')
    def test_connection_error(self, mock_post):
        mock_post.side_effect = __import__('requests').exceptions.ConnectionError("refused")

        result = _test_openai_api_key("key", "https://api.test.com", "gpt-4")
        assert result["code"] == -1
        assert "无法连接" in result["msg"]


# ---------------------------------------------------------------------------
# do_test_api_key
# ---------------------------------------------------------------------------
class TestDoTestApiKey:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.SysConfig')
    def test_empty_api_key(self, mock_config, mock_log):
        mock_config.query_system_configuration.return_value = (True, "", "")
        result = do_test_api_key({"api_key": "", "base_url": "http://a", "model": "m", "api_format": ""})
        assert result["code"] == -1
        assert "不能为空" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager._test_openai_api_key')
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.SysConfig')
    def test_openai_format(self, mock_config, mock_log, mock_test):
        mock_config.query_system_configuration.return_value = (True, "", "")
        mock_test.return_value = {"code": 0, "msg": "ok", "data": {}}
        result = do_test_api_key({"api_key": "key", "base_url": "http://a", "model": "m", "api_format": "openai"})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager._test_cursor_api_key')
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.SysConfig')
    def test_cursor_format(self, mock_config, mock_log, mock_test):
        mock_config.query_system_configuration.return_value = (True, "", "")
        mock_test.return_value = {"code": 0, "msg": "ok", "data": {}}
        result = do_test_api_key({"api_key": "key", "model": "m", "api_format": "cursor"})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager._test_openai_api_key')
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.SysConfig')
    def test_failed_test_records_log(self, mock_config, mock_log, mock_test):
        mock_config.query_system_configuration.return_value = (True, "", "")
        mock_test.return_value = {"code": -1, "msg": "bad", "data": ""}
        result = do_test_api_key({"api_key": "key", "base_url": "http://a", "model": "m", "api_format": ""})
        assert result["code"] == -1
        # Verify failure was logged (called once for the failure case)
        assert mock_log.call_count == 1


# ---------------------------------------------------------------------------
# do_del_api_key_from_db
# ---------------------------------------------------------------------------
class TestDoDelApiKeyFromDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    def test_empty_user_name(self, mock_log):
        result = do_del_api_key_from_db("user1", "", 1)
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    def test_empty_api_key_id(self, mock_log):
        result = do_del_api_key_from_db("user1", "test", "")
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    def test_invalid_api_key_id(self, mock_log):
        result = do_del_api_key_from_db("user1", "test", -1)
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    def test_non_numeric_api_key_id(self, mock_log):
        result = do_del_api_key_from_db("user1", "test", "abc")
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_success(self, mock_model, mock_log):
        mock_model.del_api_key.return_value = 0
        result = do_del_api_key_from_db("user1", "test", 1)
        assert result["code"] == 0
        assert result["data"]["deleted_id"] == 1

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_not_found(self, mock_model, mock_log):
        mock_model.del_api_key.return_value = -2
        result = do_del_api_key_from_db("user1", "test", 999)
        assert result["code"] == -2

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_user_mismatch(self, mock_model, mock_log):
        mock_model.del_api_key.return_value = -3
        result = do_del_api_key_from_db("user1", "test", 1)
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_db_error(self, mock_model, mock_log):
        mock_model.del_api_key.return_value = -1
        result = do_del_api_key_from_db("user1", "test", 1)
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# do_store_api_key_to_db
# ---------------------------------------------------------------------------
class TestDoStoreApiKeyToDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    @patch('plugin.codemig.ai_assistant.api_key_manager.encrypt_passphrase', return_value=b"enc")
    @patch('plugin.codemig.ai_assistant.api_key_manager._perform_api_key_validity_check')
    def test_success(self, mock_check, mock_enc, mock_model, mock_log):
        mock_check.return_value = {"code": 0, "msg": "ok", "data": {}}
        mock_model.store.return_value = (0, 42)
        params = {"user_name": "u", "api_key": "k", "base_url": "https://a.com",
                  "model": "gpt-4", "api_format": "openai", "others": "", "is_default": 0}
        result = do_store_api_key_to_db("user1", params)
        assert result["code"] == 0
        assert result["data"]["api_key_id"] == 42

    @patch('plugin.codemig.ai_assistant.api_key_manager.encrypt_passphrase', return_value=b"enc")
    def test_validation_failure(self, mock_enc):
        params = {"user_name": "u", "api_key": "", "base_url": "https://a.com",
                  "model": "gpt-4", "api_format": "openai", "others": "", "is_default": 0}
        result = do_store_api_key_to_db("user1", params)
        assert result["code"] == -3

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    @patch('plugin.codemig.ai_assistant.api_key_manager.encrypt_passphrase', return_value=b"enc")
    @patch('plugin.codemig.ai_assistant.api_key_manager._perform_api_key_validity_check')
    def test_duplicate(self, mock_check, mock_enc, mock_model, mock_log):
        mock_check.return_value = {"code": 0, "msg": "ok", "data": {}}
        mock_model.store.return_value = (-2, None)
        params = {"user_name": "u", "api_key": "k", "base_url": "https://a.com",
                  "model": "gpt-4", "api_format": "openai", "others": "", "is_default": 0}
        result = do_store_api_key_to_db("user1", params)
        assert result["code"] == -2

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    @patch('plugin.codemig.ai_assistant.api_key_manager.encrypt_passphrase', return_value=b"enc")
    @patch('plugin.codemig.ai_assistant.api_key_manager._perform_api_key_validity_check')
    def test_db_error(self, mock_check, mock_enc, mock_model, mock_log):
        mock_check.return_value = {"code": 0, "msg": "ok", "data": {}}
        mock_model.store.return_value = (-1, None)
        params = {"user_name": "u", "api_key": "k", "base_url": "https://a.com",
                  "model": "gpt-4", "api_format": "openai", "others": "", "is_default": 0}
        result = do_store_api_key_to_db("user1", params)
        assert result["code"] == -1

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager._perform_api_key_validity_check')
    def test_validity_failure(self, mock_check, mock_log):
        """校验失败时返回 -4，不继续存储"""
        mock_check.return_value = {"code": -1, "msg": "API Key 无效", "data": ""}
        params = {"user_name": "u", "api_key": "bad-key", "base_url": "https://a.com",
                  "model": "gpt-4", "api_format": "openai", "others": "", "is_default": 0}
        result = do_store_api_key_to_db("user1", params)
        assert result["code"] == -4
        assert "无效" in result["msg"]


# ---------------------------------------------------------------------------
# get_agent_config_from_db
# ---------------------------------------------------------------------------
class TestGetAgentConfigFromDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_success(self, mock_model):
        mock_model.get_agent_config.return_value = (0, {"api_key": "k", "base_url": "u", "model": "m"})
        result = get_agent_config_from_db("gpt-4")
        assert result["api_key"] == "k"

    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_not_found(self, mock_model):
        mock_model.get_agent_config.return_value = (-2, None)
        result = get_agent_config_from_db("unknown")
        assert result is None

    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_db_error(self, mock_model):
        mock_model.get_agent_config.return_value = (-1, None)
        result = get_agent_config_from_db("gpt-4")
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# do_get_api_key_from_db
# ---------------------------------------------------------------------------
class TestDoGetApiKeyFromDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_success(self, mock_model):
        mock_model.get_all_api_keys.return_value = (0, [{"api_key_id": 1}])
        app = Flask(__name__)
        with app.app_context():
            result = do_get_api_key_from_db()
            # Returns a Flask jsonify response
            assert result is not None

    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_db_error(self, mock_model):
        mock_model.get_all_api_keys.return_value = (-1, None)
        result = do_get_api_key_from_db()
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# do_set_default_api_key_to_db
# ---------------------------------------------------------------------------
class TestDoSetDefaultApiKeyToDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_success(self, mock_model, mock_log):
        mock_model.set_default_api_key.return_value = 0
        result = do_set_default_api_key_to_db(1, user_id="u1", login_ip="127.0.0.1")
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_not_found(self, mock_model, mock_log):
        mock_model.set_default_api_key.return_value = -4
        result = do_set_default_api_key_to_db(999)
        assert result["code"] == -4

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_db_error(self, mock_model, mock_log):
        mock_model.set_default_api_key.return_value = -1
        result = do_set_default_api_key_to_db(1)
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# Wrapper functions
# ---------------------------------------------------------------------------
class TestWrapperFunctions:
    @patch('plugin.codemig.ai_assistant.api_key_manager.do_store_api_key_to_db')
    def test_store_api_key_to_db(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = store_api_key_to_db("u1", {"api_key": "k"})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_get_api_key_from_db')
    def test_get_api_key_from_db(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = get_api_key_from_db()
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_del_api_key_from_db')
    def test_del_api_key_from_db(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = del_api_key_from_db("u1", {"user_name": "u", "api_key_id": 1})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_test_api_key')
    def test_test_api_key_by_post(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = _do_test_api_key_by_post({"api_key": "k"})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_set_default_api_key_to_db')
    def test_set_default_api_key_to_db(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = set_default_api_key_to_db({"api_key_id": 1})
        assert result["code"] == 0


# ---------------------------------------------------------------------------
# get_agent_config_from_db - new params user_id / is_admin pass-through
# ---------------------------------------------------------------------------
class TestGetAgentConfigFromDbPassThrough:
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_passes_user_id_and_admin_flag(self, mock_model):
        """新参数 user_id / is_admin 必须透传给 ORM 层"""
        mock_model.get_agent_config.return_value = (0, {"api_key": "k", "base_url": "u", "model": "m"})
        get_agent_config_from_db("gpt-4", user_id="user1", is_admin=False)
        args, kwargs = mock_model.get_agent_config.call_args
        assert kwargs.get("user_id") == "user1"
        assert kwargs.get("is_admin") is False

    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_admin_path(self, mock_model):
        mock_model.get_agent_config.return_value = (0, {"api_key": "k", "base_url": "u", "model": "m"})
        get_agent_config_from_db("gpt-4", user_id=1, is_admin=True)
        _, kwargs = mock_model.get_agent_config.call_args
        assert kwargs.get("is_admin") is True

    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_defaults_when_omitted(self, mock_model):
        """不传 user_id/is_admin 时走默认值（兼容旧调用）"""
        mock_model.get_agent_config.return_value = (-2, None)
        result = get_agent_config_from_db("unknown")
        assert result is None
        _, kwargs = mock_model.get_agent_config.call_args
        assert kwargs.get("user_id") is None
        assert kwargs.get("is_admin") is False


# ---------------------------------------------------------------------------
# do_set_default_api_key_to_db - new -3 (no permission) branch + is_admin
# ---------------------------------------------------------------------------
class TestDoSetDefaultApiKeyToDbBranches:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_no_permission_returns_minus3(self, mock_model, mock_log):
        """普通用户操作别人的 key 返回 -3"""
        mock_model.set_default_api_key.return_value = -3
        result = do_set_default_api_key_to_db(1, user_id="user1", is_admin=False)
        assert result["code"] == -3
        assert "无权限" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_passes_is_admin_to_model(self, mock_model, mock_log):
        """is_admin 透传给 ORM 层"""
        mock_model.set_default_api_key.return_value = 0
        do_set_default_api_key_to_db(1, user_id=1, is_admin=True)
        _, kwargs = mock_model.set_default_api_key.call_args
        assert kwargs.get("is_admin") is True

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_admin_success_logs_op(self, mock_model, mock_log):
        """admin 成功设置默认时记录日志"""
        mock_model.set_default_api_key.return_value = 0
        do_set_default_api_key_to_db(1, user_id=1, login_ip="127.0.0.1", is_admin=True)
        mock_log.assert_called_once()


# ---------------------------------------------------------------------------
# do_set_model_default_api_key_to_db - per-user model selection
# ---------------------------------------------------------------------------
class TestDoSetModelDefaultApiKeyToDb:
    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_success(self, mock_model, mock_log):
        mock_model.set_model_default_api_key.return_value = 0
        result = do_set_model_default_api_key_to_db(1, user_id="u1", is_admin=False)
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_not_found(self, mock_model, mock_log):
        mock_model.set_model_default_api_key.return_value = -4
        result = do_set_model_default_api_key_to_db(999)
        assert result["code"] == -4

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_no_permission(self, mock_model, mock_log):
        """普通用户操作别人 key 返回 -3"""
        mock_model.set_model_default_api_key.return_value = -3
        result = do_set_model_default_api_key_to_db(1, user_id="u1", is_admin=False)
        assert result["code"] == -3
        assert "无权限" in result["msg"]

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_db_error(self, mock_model, mock_log):
        mock_model.set_model_default_api_key.return_value = -1
        result = do_set_model_default_api_key_to_db(1)
        assert result["code"] == -1

    @patch('plugin.codemig.ai_assistant.api_key_manager._record_op_log')
    @patch('plugin.codemig.ai_assistant.api_key_manager.UserApiKey')
    def test_admin_passes_is_admin(self, mock_model, mock_log):
        """is_admin=True 透传到 ORM"""
        mock_model.set_model_default_api_key.return_value = 0
        do_set_model_default_api_key_to_db(1, user_id=1, is_admin=True)
        _, kwargs = mock_model.set_model_default_api_key.call_args
        assert kwargs.get("is_admin") is True


# ---------------------------------------------------------------------------
# Wrapper functions - new is_admin / user_id params
# ---------------------------------------------------------------------------
class TestWrapperFunctionsWithRole:
    @patch('plugin.codemig.ai_assistant.api_key_manager.do_set_default_api_key_to_db')
    def test_set_default_api_key_to_db_passes_role(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        set_default_api_key_to_db({"api_key_id": 1}, user_id="u1", is_admin=True)
        _, kwargs = mock_fn.call_args
        assert kwargs.get("user_id") == "u1"
        assert kwargs.get("is_admin") is True

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_set_model_default_api_key_to_db')
    def test_set_model_default_api_key_to_db(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        result = set_model_default_api_key_to_db({"api_key_id": 1})
        assert result["code"] == 0

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_set_model_default_api_key_to_db')
    def test_set_model_default_api_key_to_db_passes_role(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        set_model_default_api_key_to_db({"api_key_id": 1}, user_id="u1", is_admin=False)
        _, kwargs = mock_fn.call_args
        assert kwargs.get("user_id") == "u1"
        assert kwargs.get("is_admin") is False

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_get_api_key_from_db')
    def test_get_api_key_from_db_passes_role(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        get_api_key_from_db(user_id="u1", is_admin=False)
        _, kwargs = mock_fn.call_args
        assert kwargs.get("user_id") == "u1"
        assert kwargs.get("is_admin") is False

    @patch('plugin.codemig.ai_assistant.api_key_manager.do_del_api_key_from_db')
    def test_del_api_key_from_db_passes_role(self, mock_fn):
        mock_fn.return_value = {"code": 0}
        del_api_key_from_db("u1", {"user_name": "u", "api_key_id": 1}, is_admin=True)
        _, kwargs = mock_fn.call_args
        assert kwargs.get("is_admin") is True
