import os
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import requests
import common.ai_key.ai_key_utils as ai_key_utils
from common.ai_key.ai_key_utils import AIKey
ai_key_utils.URL = "https://127.0.0.1:1234/model"
AIKey.update_api_key("key")
ai_key_utils.MODEL = "DeepSeek-1234"

from plugin.codemig.ai_assistant.query_ai_handler import (
    create_data,
    to_line,
    query_ai_suggestion,
    create_headers,
    create_think_mode_data,
    create_response,
    cleanup_process,
    _chown_app_before_kill,
    _sanitize_agent_user_visible_error,
    _format_agent_stream_json_result_error_message,
    _agent_result_embedded_failure_in_body,
    _agent_stream_json_result_api_error_message,
    create_asm_question_content,
    truncate_path_to_subdir_of_dir_id,
    _validate_user,
    _extract_request_params,
    _get_user_id_and_role,
    _build_log_info,
    _parse_file_path_info,
    _parse_file_path_tuple,
    _build_query_data_dict,
    _convert_selected_data_to_agent_format,
    _convert_query_data_to_list,
    _create_content,
    _create_content_by_solver_type,
    _create_suggestion_content,
    _build_suggestion_result,
    _build_agent_mode_result,
    cancel_ai_suggestion_by_id,
    truncate_suggestion_for_db,
    create_inline_asm_content,
    create_asm_file_content,
    create_program_language_content,
    create_makefile_content,
    create_intrinsics_content,
    create_macros_content,
    create_buildin_content,
    create_build_content,
    create_rust_content,
    prompt_templates,
)
from plugin.codemig.ai_assistant.ai_data_status import AiDataStatus
from plugin.codemig.solver.solvers_mapping import SolverType

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'test.s')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def create_mock_response(chunks, status_code=200):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = status_code
    mock_response.iter_lines.return_value = chunks
    return mock_response


def _setup_common_mocks(mocker, tmp_path, user_name="test", dir_id=1):
    """设置通用 mock：get_codemig_data_path 返回临时目录，创建日志子目录，mock update_ai_suggestion"""
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path',
        return_value=str(tmp_path))
    # 预创建日志文件所需的子目录，避免 FileNotFoundError
    log_dir = tmp_path / user_name / str(dir_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')


# ---------------------------------------------------------------------------
# query_ai_suggestion - 函数级测试
# ---------------------------------------------------------------------------
def test_create_data():
    actual = create_data("test", 'DeepSeek')
    expected = {
        "model": "DeepSeek-V3",
        "messages": [{
            "role": "user",
            "content": "test",
        }],
        "temperature": 0.6,
        "max_tokens": 15_000,
        "stream": True,
    }
    assert actual == expected


def test_to_line():
    value = "代码"
    actual = to_line(AiDataStatus.RECEIVING_RESULT, value)
    expected = b'{"status": 1, "value": "\xe4\xbb\xa3\xe7\xa0\x81"}\n'
    assert actual == expected


def test_empty_chunk(mocker, tmp_path):
    chunks = [b'']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)

    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_done(mocker, tmp_path):
    chunks = [b'data: [DONE]']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 0, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_no_choices(mocker, tmp_path):
    chunks = [b'data: {"id": 123}']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_empty_choices(mocker, tmp_path):
    chunks = [b'data: {"choices": []}']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_no_delta(mocker, tmp_path):
    chunks = [b'data: {"choices": [{"index": 123}]}']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_no_content(mocker, tmp_path):
    chunks = [b'data: {"choices": [{"delta": {"abc": "asm"}}]}']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": ""}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_chunk_has_content(mocker, tmp_path):
    chunks = [b'data: {"choices": [{"delta": {"content": "asm"}}]}']
    think_mode =  "normal"
    mock_response = create_mock_response(chunks)
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    _setup_common_mocks(mocker, tmp_path)
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": 3, "value": "{\\"model\\": \\"test-model\\", \\"key_prefix\\": \\"tes\\"}"}\n',
               b'{"status": 1, "value": "asm"}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_query_has_error(mocker):
    think_mode =  "normal"
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        "Server error")
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": -1, "value": "Server error"}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


def test_query_timeout(mocker):
    think_mode =  "normal"
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.Timeout(
        "Request timed out")
    mocker.patch(
        'plugin.codemig.ai_assistant.query_ai_handler.requests.post',
        return_value=mock_response)
    agent_config = {
        "api_key": "test-key-123456",
        "base_url": "https://gateway.example.com/v1",
        "model": "test-model"
    }
    uuid = "1234567890"
    response = query_ai_suggestion("test", think_mode, TEST_FILE_PATH, 'test.s', agent_config, uuid, "test", 1, '')
    actual = list(response.response)

    # Verify behavior
    expected = [b'{"status": -2, "value": "Request timed out"}\n']
    assert actual == expected
    assert response.mimetype == 'application/json'


# ===========================================================================
# 扩展单元测试 - 覆盖纯逻辑函数
# ===========================================================================

# ---------------------------------------------------------------------------
# create_headers
# ---------------------------------------------------------------------------
class TestCreateHeaders:
    def test_has_auth(self):
        headers = create_headers()
        assert "Authorization" in headers
        assert "Bearer" in headers["Authorization"]
        assert "Content-Type" in headers


# ---------------------------------------------------------------------------
# create_data (类级扩展)
# ---------------------------------------------------------------------------
class TestCreateDataExtended:
    def test_structure(self):
        data = create_data("test content", "Qwen3")
        assert data["stream"] is True
        assert data["messages"][0]["content"] == "test content"
        assert data["temperature"] == 0.6
        assert data["max_tokens"] == 15000


# ---------------------------------------------------------------------------
# create_think_mode_data
# ---------------------------------------------------------------------------
class TestCreateThinkModeData:
    def test_has_chat_template_kwargs(self):
        data = create_think_mode_data("content", "DeepSeek")
        assert "chat_template_kwargs" in data
        assert data["chat_template_kwargs"]["enable_thinking"] is False

    def test_stream_true(self):
        data = create_think_mode_data("content", "DeepSeek")
        assert data["stream"] is True


# ---------------------------------------------------------------------------
# create_response
# ---------------------------------------------------------------------------
class TestCreateResponse:
    def test_creates_flask_response(self):
        from flask import Flask
        app = Flask(__name__)
        with app.app_context():
            resp = create_response(b'test data')
            assert resp.mimetype == 'application/json'


# ---------------------------------------------------------------------------
# _chown_app_before_kill
# ---------------------------------------------------------------------------
class TestChownAppBeforeKill:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_none_container_name_no_exec(self, mock_sp):
        _chown_app_before_kill(None)
        mock_sp.run.assert_not_called()

    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_exec_chown_with_host_uid_gid(self, mock_sp):
        mock_sp.run.return_value = MagicMock(returncode=0)
        _chown_app_before_kill("docker_uuid-1")
        mock_sp.run.assert_called_once()
        args, kwargs = mock_sp.run.call_args
        cmd = args[0]
        assert cmd[:3] == ["docker", "exec", "docker_uuid-1"]
        assert cmd[3] == "chown"
        # uid/gid 必须在宿主机侧拼进 argv，不能依赖容器内 $HOST_UID
        # （docker run -e 的环境变量不会被 docker exec 继承）
        assert f"{os.getuid()}:{os.getgid()}" in cmd
        assert cmd[-1] == "/app"
        assert kwargs.get("timeout") is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_container_gone_swallowed(self, mock_sp):
        # 容器已退出/不存在：docker exec 抛异常必须吞掉，
        # 不能阻塞随后的 docker rm -f -v 强杀主流程
        mock_sp.run.side_effect = Exception("No such container")
        _chown_app_before_kill("docker_uuid-2")  # 不抛即通过

    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_timeout_swallowed(self, mock_sp):
        mock_sp.run.side_effect = subprocess.TimeoutExpired(cmd="docker exec", timeout=15)
        _chown_app_before_kill("docker_uuid-3")  # 不抛即通过


# ---------------------------------------------------------------------------
# cleanup_process
# ---------------------------------------------------------------------------
class TestCleanupProcess:
    def test_terminated_process(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # already terminated
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        cleanup_process(mock_proc)
        mock_proc.terminate.assert_not_called()

    def test_running_process(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = None
        cleanup_process(mock_proc)
        mock_proc.terminate.assert_called_once()
        mock_proc.stdout.close.assert_called_once()

    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_chown_before_rm_when_container_named(self, mock_sp):
        mock_sp.TimeoutExpired = subprocess.TimeoutExpired
        mock_sp.run.return_value = MagicMock(returncode=0)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # already terminated
        mock_proc.stdout = None
        mock_proc.stderr = None
        cleanup_process(mock_proc, container_name="docker_uuid-x")
        assert mock_sp.run.call_count == 2
        first_cmd = mock_sp.run.call_args_list[0][0][0]
        second_cmd = mock_sp.run.call_args_list[1][0][0]
        # chown 补偿必须先于 rm -f -v，否则强杀后 root 残留无从修复
        assert first_cmd[:3] == ["docker", "exec", "docker_uuid-x"]
        assert first_cmd[3] == "chown"
        assert second_cmd == ["docker", "rm", "-f", "-v", "docker_uuid-x"]


# ---------------------------------------------------------------------------
# _sanitize_agent_user_visible_error
# ---------------------------------------------------------------------------
class TestSanitizeAgentUserVisibleError:
    def test_removes_cursor(self):
        result = _sanitize_agent_user_visible_error("cursor AI failed to run")
        assert "cursor" not in result.lower()
        assert "AI" in result

    def test_non_string(self):
        result = _sanitize_agent_user_visible_error(123)
        assert result == "123"

    def test_empty_string(self):
        result = _sanitize_agent_user_visible_error("")
        assert result == "AI 服务调用失败"

    def test_long_string_truncated(self):
        result = _sanitize_agent_user_visible_error("x" * 5000)
        assert len(result) <= 4000


# ---------------------------------------------------------------------------
# _format_agent_stream_json_result_error_message
# ---------------------------------------------------------------------------
class TestFormatAgentStreamJsonResultErrorMessage:
    def test_error_dict_message(self):
        data = {"error": {"message": "API key invalid"}}
        result = _format_agent_stream_json_result_error_message(data)
        assert "API key invalid" in result

    def test_error_dict_msg(self):
        data = {"error": {"msg": "some error"}}
        result = _format_agent_stream_json_result_error_message(data)
        assert "some error" in result

    def test_error_string(self):
        data = {"error": "string error message"}
        result = _format_agent_stream_json_result_error_message(data)
        assert "string error message" in result

    def test_is_error_true_with_message(self):
        data = {"is_error": True, "message": "fail reason"}
        result = _format_agent_stream_json_result_error_message(data)
        assert "fail reason" in result

    def test_result_with_brackets(self):
        data = {"result": "[Error: something failed]"}
        result = _format_agent_stream_json_result_error_message(data)
        assert "something failed" in result

    def test_result_plain_text(self):
        data = {"result": "plain error text"}
        result = _format_agent_stream_json_result_error_message(data)
        assert "plain error text" in result

    def test_no_info(self):
        data = {}
        result = _format_agent_stream_json_result_error_message(data)
        assert "无详细说明" in result


# ---------------------------------------------------------------------------
# _agent_result_embedded_failure_in_body
# ---------------------------------------------------------------------------
class TestAgentResultEmbeddedFailureInBody:
    def test_api_error(self):
        assert _agent_result_embedded_failure_in_body("[api error: key invalid]") is True

    def test_quota(self):
        assert _agent_result_embedded_failure_in_body("quota limitations exceeded") is True

    def test_rate_limit(self):
        assert _agent_result_embedded_failure_in_body("rate limit hit") is True

    def test_normal_text(self):
        assert _agent_result_embedded_failure_in_body("This is a normal response") is False

    def test_empty(self):
        assert _agent_result_embedded_failure_in_body("") is False

    def test_non_string(self):
        assert _agent_result_embedded_failure_in_body(None) is False

    def test_chinese_quota(self):
        assert _agent_result_embedded_failure_in_body("余额不足") is True


# ---------------------------------------------------------------------------
# _agent_stream_json_result_api_error_message
# ---------------------------------------------------------------------------
class TestAgentStreamJsonResultApiErrorMessage:
    def test_non_dict(self):
        assert _agent_stream_json_result_api_error_message("not a dict") is None

    def test_is_error_true(self):
        data = {"is_error": True, "error": {"message": "API error"}}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None
        assert "API error" in result

    def test_failed_true(self):
        data = {"failed": True, "error": "task failed"}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None

    def test_cancelled(self):
        data = {"cancelled": True}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None
        assert "取消" in result

    def test_failure_subtype(self):
        data = {"subtype": "error", "error": {"message": "error msg"}}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None

    def test_success_returns_none(self):
        data = {"subtype": "success", "result": "task completed successfully"}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is None

    def test_embedded_failure(self):
        data = {"is_error": False, "result": "[api error: something went wrong]"}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None

    def test_error_field_present(self):
        data = {"error": {"message": "server error"}}
        result = _agent_stream_json_result_api_error_message(data)
        assert result is not None


# ---------------------------------------------------------------------------
# create_asm_question_content
# ---------------------------------------------------------------------------
class TestCreateAsmQuestionContent:
    def test_basic(self):
        code = ["line1\n", "line2\n"]
        result = create_asm_question_content(code, "请修复")
        assert "请修复" in result
        assert "line1" in result
        assert "line2" in result


# ---------------------------------------------------------------------------
# truncate_path_to_subdir_of_dir_id
# ---------------------------------------------------------------------------
class TestTruncatePathToSubdirOfDirId:
    def test_found_dir_id(self):
        result = truncate_path_to_subdir_of_dir_id("/data/user/123/project/file.c", 123)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_not_found_dir_id(self):
        result = truncate_path_to_subdir_of_dir_id("/data/user/project/file.c", 999)
        assert isinstance(result, tuple)
        assert len(result) == 2
        # Should return (dir_path, file_name)
        assert result[1] == "file.c"


# ---------------------------------------------------------------------------
# _validate_user
# ---------------------------------------------------------------------------
class TestValidateUser:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_valid_user(self, mock_um):
        mock_user = MagicMock()
        mock_user.user_name = "testuser"
        mock_um.query_by_id.return_value = mock_user
        result = _validate_user(1, "testuser")
        assert result is not None
        assert result.user_name == "testuser"

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_user_not_found(self, mock_um):
        mock_um.query_by_id.return_value = None
        result = _validate_user(1, "testuser")
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_name_mismatch(self, mock_um):
        mock_user = MagicMock()
        mock_user.user_name = "other"
        mock_um.query_by_id.return_value = mock_user
        result = _validate_user(1, "testuser")
        assert result is None


# ---------------------------------------------------------------------------
# _extract_request_params
# ---------------------------------------------------------------------------
class TestExtractRequestParams:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_basic_params(self, mock_um):
        mock_um.query_by_id.return_value = MagicMock()
        mock_req = MagicMock()
        mock_req.user_id = 1
        params = {
            "user_name": "u", "task_id": 1, "dir_id": 2, "file_id": 3,
            "change_id": 4, "dependence_id": None, "think_mode": "normal",
            "selected_start_line": None, "selected_end_line": None,
            "agent_model": None, "api_format": None, "request_uuid": "uuid-1"
        }
        result = _extract_request_params(params, mock_req)
        assert result["user_id"] == 1
        assert result["task_id"] == 1
        assert result["dir_id"] == 2

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_with_agent_model(self, mock_um, mock_config):
        mock_um.query_by_id.return_value = MagicMock()
        mock_config.return_value = {"api_key": "k"}
        mock_req = MagicMock()
        mock_req.user_id = 1
        params = {
            "user_name": "u", "task_id": 1, "dir_id": 2, "file_id": 3,
            "change_id": None, "dependence_id": None, "think_mode": "agent",
            "selected_start_line": None, "selected_end_line": None,
            "agent_model": "DeepSeek-V3", "api_format": "openai", "request_uuid": "uuid"
        }
        result = _extract_request_params(params, mock_req)
        assert result["agent_model"] == "DeepSeek-V3"
        assert result["agent_config"] == {"api_key": "k"}

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_base_model_skips_config(self, mock_um, mock_config):
        """agent_model 为 'BASE_MODEL' 时跳过查询数据库配置，使用建议模式默认模型且不传自定义 api_key"""
        mock_um.query_by_id.return_value = MagicMock()
        mock_config.return_value = {"api_key": "base_key"}
        mock_req = MagicMock()
        mock_req.user_id = 1
        params = {
            "user_name": "u", "task_id": 1, "dir_id": 2, "file_id": 3,
            "change_id": None, "dependence_id": None, "think_mode": "normal",
            "selected_start_line": None, "selected_end_line": None,
            "agent_model": "BASE_MODEL", "api_format": None, "request_uuid": "uuid"
        }
        result = _extract_request_params(params, mock_req)
        mock_config.assert_not_called()
        assert result["agent_config"] == ''

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_admin_user_passes_is_admin_true(self, mock_um, mock_config):
        """admin 用户：is_admin=True 透传给 get_agent_config_from_db"""
        admin_user = MagicMock()
        admin_user.role = 'admin'
        mock_um.query_by_id.return_value = admin_user
        mock_config.return_value = {"api_key": "k"}
        mock_req = MagicMock()
        mock_req.user_id = 1
        params = {
            "user_name": "u", "task_id": 1, "dir_id": 2, "file_id": 3,
            "change_id": None, "dependence_id": None, "think_mode": "agent",
            "selected_start_line": None, "selected_end_line": None,
            "agent_model": "DeepSeek-V3", "api_format": "openai", "request_uuid": "uuid"
        }
        _extract_request_params(params, mock_req)
        _, kwargs = mock_config.call_args
        assert kwargs.get("is_admin") is True
        assert kwargs.get("user_id") == 1

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_normal_user_passes_is_admin_false(self, mock_um, mock_config):
        """普通用户：is_admin=False 透传给 get_agent_config_from_db"""
        normal_user = MagicMock()
        normal_user.role = 'user'
        mock_um.query_by_id.return_value = normal_user
        mock_config.return_value = {"api_key": "k"}
        mock_req = MagicMock()
        mock_req.user_id = 99
        params = {
            "user_name": "u", "task_id": 1, "dir_id": 2, "file_id": 3,
            "change_id": None, "dependence_id": None, "think_mode": "agent",
            "selected_start_line": None, "selected_end_line": None,
            "agent_model": "DeepSeek-V3", "api_format": "openai", "request_uuid": "uuid"
        }
        _extract_request_params(params, mock_req)
        _, kwargs = mock_config.call_args
        assert kwargs.get("is_admin") is False
        assert kwargs.get("user_id") == 99


# ---------------------------------------------------------------------------
# _get_user_id_and_role
# ---------------------------------------------------------------------------
class TestGetUserIdAndRole:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_admin_user(self, mock_um):
        """admin 用户：返回 (user_id, True)"""
        admin_user = MagicMock()
        admin_user.user_id = 1
        admin_user.role = 'admin'
        mock_um.query.return_value = admin_user

        user_id, is_admin = _get_user_id_and_role("admin_user")
        assert user_id == 1
        assert is_admin is True

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_normal_user(self, mock_um):
        """普通用户：返回 (user_id, False)"""
        normal_user = MagicMock()
        normal_user.user_id = 99
        normal_user.role = 'user'
        mock_um.query.return_value = normal_user

        user_id, is_admin = _get_user_id_and_role("normal_user")
        assert user_id == 99
        assert is_admin is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_user_not_found(self, mock_um):
        """用户不存在：返回 (None, False)"""
        mock_um.query.return_value = None
        user_id, is_admin = _get_user_id_and_role("nobody")
        assert user_id is None
        assert is_admin is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    def test_db_exception_returns_safe_default(self, mock_um):
        """数据库异常：返回 (None, False) 而非抛出"""
        mock_um.query.side_effect = Exception("db error")
        user_id, is_admin = _get_user_id_and_role("crash_user")
        assert user_id is None
        assert is_admin is False


# ---------------------------------------------------------------------------
# _build_log_info
# ---------------------------------------------------------------------------
class TestBuildLogInfo:
    def test_minimal(self):
        result = _build_log_info("task1", 1, None, None, None, None, "normal")
        assert "task:task1" in result
        assert "file_id:1" in result
        assert "think_mode:normal" in result

    def test_full(self):
        result = _build_log_info("task1", 1, 2, 10, 20, 3, "agent")
        assert "change_id:2" in result
        assert "selected_lines:10-20" in result
        assert "dependence_id:3" in result
        assert "think_mode:agent" in result


# ---------------------------------------------------------------------------
# _parse_file_path_info
# ---------------------------------------------------------------------------
class TestParseFilePathInfo:
    def test_basic(self):
        file_dir, file_name, full = _parse_file_path_info("/data/user/123/proj/file.c", 123)
        assert file_name == "file.c" or file_name != ""


# ---------------------------------------------------------------------------
# _parse_file_path_tuple
# ---------------------------------------------------------------------------
class TestParseFilePathTuple:
    def test_tuple_input(self):
        result = _parse_file_path_tuple(("/dir/", "file.c"))
        assert result == ("/dir/", "file.c")

    def test_string_input(self):
        result = _parse_file_path_tuple("/path/to/file.c")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[1] == "file.c"


# ---------------------------------------------------------------------------
# _build_query_data_dict
# ---------------------------------------------------------------------------
class TestBuildQueryDataDict:
    def test_basic(self):
        result = _build_query_data_dict("/tmp/file.c", 1, 10, 20, "fix this", False)
        assert result["file_path"] == "/tmp/file.c"
        assert result["type"] == 1
        assert result["start_line"] == 10
        assert result["end_line"] == 20
        assert result["suggestion"] == "fix this"
        assert result["is_selected_lines"] is False

    def test_default_is_selected(self):
        result = _build_query_data_dict("/tmp/file.c", 1, 10, 20, "fix")
        assert result["is_selected_lines"] is False


# ---------------------------------------------------------------------------
# _convert_selected_data_to_agent_format
# ---------------------------------------------------------------------------
class TestConvertSelectedDataToAgentFormat:
    def test_basic(self):
        selected_data = {
            "task_name": "task1",
            "query_data": {
                "file_path": "/tmp/file.c",
                "start_line": 10,
                "end_line": 20,
                "suggestion": "fix this"
            }
        }
        result = _convert_selected_data_to_agent_format(selected_data)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0][0] == "task1"  # task_name
        assert result[0][1] == "/tmp/file.c"  # file_path


# ---------------------------------------------------------------------------
# _convert_query_data_to_list
# ---------------------------------------------------------------------------
class TestConvertQueryDataToList:
    def test_basic(self):
        data_dict = {
            "file_path": "/f.c",
            "type": 1,
            "start_line": 10,
            "end_line": 20,
            "suggestion": "fix",
            "is_selected_lines": False
        }
        result = _convert_query_data_to_list(data_dict)
        assert isinstance(result, list)
        assert len(result) == 6
        assert result[0] == "/f.c"


# ---------------------------------------------------------------------------
# Content creation functions (using tmp_path for real files)
# ---------------------------------------------------------------------------
class TestCreateAsmFileContent:
    def test_selected_lines(self, tmp_path):
        f = tmp_path / "test.s"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        query_data = (str(f), "", 2, 4, "修复建议", True)
        result = create_asm_file_content(query_data)
        assert "line2" in result
        assert "line4" in result

    def test_full_file(self, tmp_path):
        f = tmp_path / "test.s"
        f.write_text("line1\nline2\nline3\n")
        query_data = (str(f), "", 1, 3, "建议", False)
        result = create_asm_file_content(query_data)
        assert "line1" in result
        assert "line3" in result


# ---------------------------------------------------------------------------
# create_inline_asm_content
# ---------------------------------------------------------------------------
class TestCreateInlineAsmContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "test.s"
        f.write_text("line1\nline2\nline3\nline4\n")
        query_data = (str(f), "", 2, 3, "修复建议", True)
        result = create_inline_asm_content(query_data)
        assert "line2" in result
        assert "line3" in result


# ---------------------------------------------------------------------------
# create_program_language_content
# ---------------------------------------------------------------------------
class TestCreateProgramLanguageContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "test.java"
        f.write_text("public class A {\n  int x;\n}\n")
        query_data = (str(f), "", 1, 3, "建议修改", False)
        result = create_program_language_content(query_data, "JavaSolver")
        assert "JavaSolver" in result
        assert "public class A" in result


# ---------------------------------------------------------------------------
# create_makefile_content
# ---------------------------------------------------------------------------
class TestCreateMakefileContent:
    def test_short_file(self, tmp_path):
        f = tmp_path / "Makefile"
        f.write_text("CC=gcc\nall: build\n")
        query_data = (str(f), "", 1, 3, "建议修改", False)
        result = create_makefile_content(query_data)
        assert "CC=gcc" in result

    def test_long_file(self, tmp_path):
        f = tmp_path / "Makefile"
        lines = [f"line{i}\n" for i in range(150)]
        f.write_text("".join(lines))
        query_data = (str(f), "", 10, 20, "建议修改", False)
        result = create_makefile_content(query_data)
        assert "关联规则块" in result

    def test_selected_lines(self, tmp_path):
        f = tmp_path / "Makefile"
        f.write_text("CC=gcc\nCXX=g++\nall: build\n")
        query_data = (str(f), "", 1, 2, "建议", True)
        result = create_makefile_content(query_data)
        assert "关联规则块" in result


# ---------------------------------------------------------------------------
# create_intrinsics_content
# ---------------------------------------------------------------------------
class TestCreateIntrinsicsContent:
    def test_selected_lines(self, tmp_path):
        f = tmp_path / "test.c"
        f.write_text("#include <immintrin.h>\n__m256 a;\nother\n")
        query_data = (str(f), "", 1, 2, "建议", True)
        result = create_intrinsics_content(query_data)
        assert "immintrin" in result

    def test_full_file(self, tmp_path):
        f = tmp_path / "test.c"
        f.write_text("#include <immintrin.h>\n__m256 a;\n")
        query_data = (str(f), "", 1, 2, "建议", False)
        result = create_intrinsics_content(query_data)
        assert "immintrin" in result


# ---------------------------------------------------------------------------
# create_macros_content
# ---------------------------------------------------------------------------
class TestCreateMacrosContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "test.h"
        f.write_text("#define X86_FLAG 1\n#define OTHER 2\n")
        query_data = (str(f), "", 1, 2, "建议", False)
        result = create_macros_content(query_data)
        assert "X86_FLAG" in result


# ---------------------------------------------------------------------------
# create_buildin_content
# ---------------------------------------------------------------------------
class TestCreateBuildinContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "test.c"
        f.write_text("__builtin_expect(x, 0)\n")
        query_data = (str(f), "", 1, 1, "建议", False)
        result = create_buildin_content(query_data)
        assert "builtin" in result


# ---------------------------------------------------------------------------
# create_build_content
# ---------------------------------------------------------------------------
class TestCreateBuildContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "build.sh"
        f.write_text("gcc -o main main.c\n")
        query_data = (str(f), "", 1, 1, "建议", False)
        result = create_build_content(query_data)
        assert "gcc" in result


# ---------------------------------------------------------------------------
# create_rust_content
# ---------------------------------------------------------------------------
class TestCreateRustContent:
    def test_basic(self, tmp_path):
        f = tmp_path / "main.rs"
        f.write_text("fn main() { println!(\"hello\"); }\n")
        query_data = (str(f), "", 1, 1, "建议", False)
        result = create_rust_content(query_data)
        assert "Rust" in result


# ---------------------------------------------------------------------------
# _build_suggestion_result
# ---------------------------------------------------------------------------
class TestBuildSuggestionResult:
    def test_basic(self):
        result = _build_suggestion_result("task1", "/f.c", "/dir/", "f.c", {"key": "val"}, 1)
        assert result["type"] == "suggestion"
        assert result["task_name"] == "task1"
        assert result["file_path"] == "/f.c"
        assert result["change_id"] == 1


# ---------------------------------------------------------------------------
# _build_agent_mode_result
# ---------------------------------------------------------------------------
class TestBuildAgentModeResult:
    def test_basic(self):
        result = _build_agent_mode_result(
            selected_data=None,
            query_data_list=[("task1", "/f.c", None, 1, 10, "fix")],
            file_path="/f.c",
            dir_id=1
        )
        assert result["type"] == "agent"
        assert result["file_path"] == "/f.c"

    def test_with_selected_data(self):
        selected = {
            "task_name": "task1",
            "query_data": {"file_path": "/f.c", "start_line": 1, "end_line": 10, "suggestion": "fix"}
        }
        result = _build_agent_mode_result(
            selected_data=selected,
            query_data_list=None,
            file_path="/f.c",
            dir_id=1
        )
        assert result["type"] == "agent"


# ---------------------------------------------------------------------------
# _create_content_by_solver_type
# ---------------------------------------------------------------------------
class TestCreateContentBySolverType:
    def _make_file(self, tmp_path, content="line1\nline2\n"):
        f = tmp_path / "test_file"
        f.write_text(content)
        return str(f)

    def test_inline_asm(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.INLINE_ASM.value, 1, 2, "fix", True]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_asm_file(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.ASM_FILE.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_makefile(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.MAKEFILE.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_intrinsics(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.INTRINSICS.value, 1, 2, "fix", True]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_builtin(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.BUILTIN.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_macros(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.MACROS.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_build_script(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.BUILD_SCRIPT.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_rust_source(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.RUST_SOURCE_CODE.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_rust_toml(self, tmp_path):
        fp = self._make_file(tmp_path)
        qd = [fp, SolverType.RUST_TOML_CODE.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_java_source(self, tmp_path):
        fp = self._make_file(tmp_path, "public class A {}\n")
        qd = [fp, SolverType.JAVA_SOURCE_CODE.value, 1, 1, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is not None

    def test_unknown_type(self, tmp_path):
        fp = self._make_file(tmp_path)
        # Use a value that hits the else branch
        qd = [fp, SolverType.GO_RELEASER_TML.value, 1, 2, "fix", False]
        result = _create_content_by_solver_type(qd)
        assert result is None


# ---------------------------------------------------------------------------
# _create_content
# ---------------------------------------------------------------------------
class TestCreateContent:
    def test_suggestion_type(self, tmp_path):
        f = tmp_path / "test.s"
        f.write_text("line1\nline2\n")
        code_data = {
            'type': 'suggestion',
            'task_name': 'task1',
            'file_dir': str(tmp_path),
            'file_name': 'test.s',
            'query_data': {
                'file_path': str(f),
                'type': SolverType.ASM_FILE.value,
                'start_line': 1,
                'end_line': 2,
                'suggestion': 'fix',
                'is_selected_lines': False
            }
        }
        content, file_dir, file_name, task_name = _create_content(code_data, 'normal', 1)
        assert content is not None
        assert task_name == 'task1'

    def test_agent_type(self):
        code_data = {
            'type': 'agent',
            'task_name': 'task1',
            'file_dir': '/dir',
            'file_name': 'test.s',
            'query_data': [("task1", "/f.s", None, 1, 10, "fix")]
        }
        content, file_dir, file_name, task_name = _create_content(code_data, 'agent', 1)
        assert content is not None

    def test_unknown_type(self):
        code_data = {'type': 'unknown'}
        content, fd, fn, tn = _create_content(code_data, 'normal', 1)
        assert content is None


# ---------------------------------------------------------------------------
# cancel_ai_suggestion_by_id
# ---------------------------------------------------------------------------
class TestCancelAiSuggestionById:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.restore_workspace')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_success(self, mock_sp, mock_restore):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "container deleted"
        mock_sp.run.return_value = mock_result
        mock_sp.TimeoutExpired = subprocess.TimeoutExpired
        mock_sp.SubprocessError = subprocess.SubprocessError

        result = cancel_ai_suggestion_by_id("user", 1, "uuid-123")
        assert result["code"] == 0
        # V7：取消时不再自动 restore_workspace——工作区保留 agent 半成品，
        # 由 finally 块的中间态 commit 收进 git 历史，用户可在历史下拉框手动回退。
        mock_restore.assert_not_called()

    @patch('plugin.codemig.ai_assistant.query_ai_handler.restore_workspace')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_container_not_found(self, mock_sp, mock_restore):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "No such container"
        mock_sp.run.return_value = mock_result
        mock_sp.TimeoutExpired = subprocess.TimeoutExpired
        mock_sp.SubprocessError = subprocess.SubprocessError

        result = cancel_ai_suggestion_by_id("user", 1, "uuid-123")
        assert result["code"] == 0  # container not found is still success

    @patch('plugin.codemig.ai_assistant.query_ai_handler.restore_workspace')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_other_error_raises(self, mock_sp, mock_restore):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "other error"
        mock_sp.run.return_value = mock_result
        mock_sp.TimeoutExpired = subprocess.TimeoutExpired
        mock_sp.SubprocessError = subprocess.SubprocessError

        with pytest.raises(Exception, match="docker rm failed"):
            cancel_ai_suggestion_by_id("user", 1, "uuid-123")

    @patch('plugin.codemig.ai_assistant.query_ai_handler.restore_workspace')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess')
    def test_timeout_raises(self, mock_sp, mock_restore):
        mock_sp.run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=30)
        mock_sp.TimeoutExpired = subprocess.TimeoutExpired
        mock_sp.SubprocessError = subprocess.SubprocessError

        with pytest.raises(Exception, match="timed out"):
            cancel_ai_suggestion_by_id("user", 1, "uuid-123")


# ---------------------------------------------------------------------------
# query_reopen_ai_suggestion, set_ai_score, get_ai_score
# ---------------------------------------------------------------------------
class TestDatabaseDelegators:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion_from_database')
    def test_query_reopen(self, mock_fn):
        mock_fn.return_value = (True, 42, "content")
        from plugin.codemig.ai_assistant.query_ai_handler import query_reopen_ai_suggestion
        result = query_reopen_ai_suggestion("user", 1, 2, 3)
        mock_fn.assert_called_once_with("user", 1, 2, 3)
        assert result == (True, 42, "content")

    @patch('plugin.codemig.ai_assistant.query_ai_handler.set_ai_score_to_database')
    def test_set_ai_score(self, mock_fn):
        mock_fn.return_value = (True, "ok")
        from plugin.codemig.ai_assistant.query_ai_handler import set_ai_score
        result = set_ai_score("user", 1, 2, 3, 5)
        mock_fn.assert_called_once_with("user", 1, 2, 3, 5)

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_ai_score_from_database')
    def test_get_ai_score(self, mock_fn):
        mock_fn.return_value = (True, 5)
        from plugin.codemig.ai_assistant.query_ai_handler import get_ai_score
        result = get_ai_score("user", 1, 2, "uuid")
        mock_fn.assert_called_once_with("user", 1, 2, "uuid")


# ---------------------------------------------------------------------------
# query_ai_suggestion_for_change - main orchestrator
# ---------------------------------------------------------------------------
class TestQueryAiSuggestionForChange:
    @patch('plugin.codemig.ai_assistant.query_ai_handler._validate_user', return_value=None)
    @patch('plugin.codemig.ai_assistant.query_ai_handler._extract_request_params')
    def test_unknown_user(self, mock_extract, mock_validate):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_for_change
        mock_extract.return_value = {'user_id': 1, 'user_name': 'bad'}
        result = query_ai_suggestion_for_change({}, MagicMock())
        assert result["code"] == -1
        assert "Unknown" in result["msg"]

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._create_content')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_code_and_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._validate_user')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._extract_request_params')
    def test_no_code_data(self, mock_extract, mock_validate, mock_get_code, mock_create, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_for_change
        mock_user = MagicMock()
        mock_user.user_name = "testuser"
        mock_validate.return_value = mock_user
        mock_get_code.return_value = None
        mock_extract.return_value = {
            'user_id': 1, 'user_name': 'testuser', 'task_id': 1, 'dir_id': 1,
            'file_id': 1, 'change_id': None, 'dependence_id': None,
            'think_mode': 'normal', 'selected_start_line': None, 'selected_end_line': None,
            'agent_model': None, 'agent_config': '', 'api_format': None, 'request_uuid': 'uuid'
        }
        result = query_ai_suggestion_for_change({}, MagicMock())
        # Should return a Response with UNKNOWN_ERROR status
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_code_and_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._validate_user')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._extract_request_params')
    def test_exception_handling(self, mock_extract, mock_validate, mock_get_code, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_for_change
        mock_user = MagicMock()
        mock_user.user_name = "testuser"
        mock_validate.return_value = mock_user
        mock_get_code.side_effect = Exception("database down")
        mock_extract.return_value = {
            'user_id': 1, 'user_name': 'testuser', 'task_id': 1, 'dir_id': 1,
            'file_id': 1, 'change_id': None, 'dependence_id': None,
            'think_mode': 'normal', 'selected_start_line': None, 'selected_end_line': None,
            'agent_model': None, 'agent_config': '', 'api_format': None, 'request_uuid': 'uuid'
        }
        result = query_ai_suggestion_for_change({}, MagicMock())
        assert result is not None


# ---------------------------------------------------------------------------
# rescan_file
# ---------------------------------------------------------------------------
class TestRescanFile:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info_from_database')
    def test_file_not_in_db(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import rescan_file
        mock_query.return_value = (False, None)
        result = rescan_file("user", 1, 1)
        assert result is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info_from_database')
    def test_file_not_on_disk(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import rescan_file
        mock_query.return_value = (True, ("/nonexistent/file.c", "src", 0, True))
        result = rescan_file("user", 1, 1)
        assert result is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info_from_database')
    def test_is_directory(self, mock_query, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import rescan_file
        mock_query.return_value = (True, (str(tmp_path), "src", 0, True))
        result = rescan_file("user", 1, 1)
        assert result is False


# ---------------------------------------------------------------------------
# generate_streaming_response - HTTP streaming
# ---------------------------------------------------------------------------
class TestGenerateStreamingResponse:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_basic_stream(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "hello"}}]}',
            b'data: [DONE]'
        ]

        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        # Should produce streaming output lines
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_reasoning_mode(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"reasoning_content": "thinking..."}}]}',
            b'data: {"choices": [{"delta": {"content": "answer"}}]}',
            b'data: [DONE]'
        ]

        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# parse_agent_output
# ---------------------------------------------------------------------------
class TestParseAgentOutput:
    def _make_process(self, lines):
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = lines
        mock_proc.returncode = 0
        return mock_proc

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_system_message(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "system", "model": "test-model"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_assistant_message(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello world"}]}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_error_message(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "error", "error": {"message": "API error"}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0
        joined = b"".join(lines).decode("utf-8")
        assert "Agent Error" in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_tool_call_message(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "tool_call", "subtype": "started", "tool_call": {"globToolCall": {"args": {"globPattern": "*.c"}}}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_result_success(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "result", "subtype": "success", "result": "task completed"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_result_failure(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "result", "is_error": true, "error": {"message": "API key invalid"}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_user_message_with_error(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "user", "message": {"content": [{"type": "tool_result", "is_error": true, "tool_use_id": "123"}]}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_stream_event(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}}}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_empty_lines_skipped(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '\n',
            '  \n',
            '{"type": "result", "subtype": "success", "result": "done"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_content_block_start(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"name": "write_file", "type": "tool_use"}}}\n',
            '{"type": "result", "subtype": "success", "result": "done"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_write_file_stream_no_repeat_and_no_div(self, mock_path, tmp_path):
        """anthropic 协议 write_file：多片 input_json_delta 只出一次头部，
        不注入 <div>，内容体不进流，stop 时围栏与 details 正确闭合"""
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        args_json = json.dumps({"file_path": "/app/ut/main.c", "content": "int main(){return 0;}"})
        half = len(args_json) // 2
        proc = self._make_process([
            '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"name": "write_file", "type": "tool_use"}}}\n',
            f'{{"type": "stream_event", "event": {{"type": "content_block_delta", "delta": {{"type": "input_json_delta", "partial_json": {json.dumps(args_json[:half])}}}}}}}\n',
            f'{{"type": "stream_event", "event": {{"type": "content_block_delta", "delta": {{"type": "input_json_delta", "partial_json": {json.dumps(args_json[half:])}}}}}}}\n',
            '{"type": "stream_event", "event": {"type": "content_block_stop"}}\n',
            '{"type": "result", "subtype": "success", "result": "done"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        assert "<div>" not in joined
        assert "int main" not in joined  # 内容体不进流
        assert joined.count("/app/ut/main.c") == 1  # 路径只出现一次（头部摘要）
        assert "```" in joined  # 围栏成对（头部开 + stop 闭）
        assert "</details>" in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_content_block_stop(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"name": "write_file", "type": "tool_use"}}}\n',
            '{"type": "stream_event", "event": {"type": "content_block_stop"}}\n',
            '{"type": "result", "subtype": "success", "result": "done"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_non_json_line(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            'not-json-at-all\n',
            '{"type": "result", "subtype": "success", "result": "done"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_no_result_message(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "system", "model": "test"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        assert len(lines) > 0
        joined = b"".join(lines).decode("utf-8")
        assert "异常中断" in joined

    # ---- pi agent stream-json 协议 ----

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_session_yields_session_id(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "session", "version": 3, "id": "sess-abc-123", "timestamp": "2026-08-12T09:18:19.038Z", "cwd": "/tmp"}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        assert "sess-abc-123" in joined
        # 协议结束信号被识别：不应该再有"异常中断"
        assert "异常中断" not in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_text_delta_streams_to_front(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "message_start", "message": {"role": "assistant"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_start", "contentIndex": 1}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "我来帮你"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "查看目录"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_end", "contentIndex": 1}}\n',
            '{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "我来帮你查看目录"}]}}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        assert "我来帮你" in joined
        assert "查看目录" in joined
        # 累加与 message_end 完全相等，message_end 应被去重，"我来帮你" / "查看目录" 各只 yield 一次
        assert joined.count("我来帮你") == 1
        assert joined.count("查看目录") == 1

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_thinking_delta_wraps_think_tags(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "message_start", "message": {"role": "assistant"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_start", "contentIndex": 0}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "contentIndex": 0, "delta": "用户在问什么"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_end", "contentIndex": 0}}\n',
            '{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "用户在问什么"}, {"type": "text", "text": "好的"}]}}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        # 思考内容必须被 <details> 折叠块包起来（替代早期 <think/> 标签方案）
        assert "<details>" in joined
        assert "<summary>💭 思考过程</summary>" in joined
        assert "</details>" in joined
        assert "用户在问什么" in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_message_end_dedup_matches_stream(self, mock_path, tmp_path):
        """message_end 内容等于累加时，必须去重，不重复 yield"""
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "message_start", "message": {"role": "assistant"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_start", "contentIndex": 1}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "abc"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "def"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_end", "contentIndex": 1}}\n',
            '{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "abcdef"}]}}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        # 累加与 message_end 完全相等，message_end 应被去重，"abc" 和 "def" 各 yield 一次
        assert joined.count("abc") == 1
        assert joined.count("def") == 1

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_message_end_appends_tail(self, mock_path, tmp_path):
        """message_end 比累加多了尾巴，应只补尾巴"""
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "message_start", "message": {"role": "assistant"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_start", "contentIndex": 1}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "abc"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_end", "contentIndex": 1}}\n',
            '{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "abc尾巴"}]}}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        # 流式语义：累加是 "abc"（delta 阶段已发），定型是 "abc尾巴"，
        # message_end 只补发尾巴 "尾巴"，由前端拼接还原全文，不整体重发。
        assert "尾巴" in joined
        assert joined.count("abc") == 1
        assert joined.count("尾巴") == 1

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_full_cycle_includes_session_thinking_text_tool(self, mock_path, tmp_path):
        """完整周期：session → agent_start → turn_start → message_start → thinking → text → tool → message_end → agent_settled"""
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "session", "id": "full-cycle-1", "version": 3}\n',
            '{"type": "agent_start"}\n',
            '{"type": "turn_start"}\n',
            '{"type": "message_start", "message": {"role": "assistant"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_start", "contentIndex": 0}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "contentIndex": 0, "delta": "思考中"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "thinking_end", "contentIndex": 0}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_start", "contentIndex": 1}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "正文A"}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "text_end", "contentIndex": 1}}\n',
            '{"type": "message_update", "assistantMessageEvent": {"type": "toolcall_end", "contentIndex": 2, "toolCall": {"type": "toolCall", "id": "t1", "name": "bash", "arguments": {"command": "ls"}}}\n',
            '{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "思考中"}, {"type": "text", "text": "正文A"}, {"type": "toolCall", "id": "t1", "name": "bash", "arguments": {"command": "ls"}}]}}\n',
            '{"type": "tool_execution_start", "toolCallId": "t1", "toolName": "bash", "args": {"command": "ls"}}\n',
            '{"type": "tool_execution_end", "toolCallId": "t1", "toolName": "bash", "result": {"content": [{"type": "text", "text": "file1.txt"}]}, "isError": false}\n',
            '{"type": "turn_end"}\n',
            '{"type": "agent_end"}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        # 思考流：被 <details> 折叠块包裹（替代早期 <think/> 标签方案）
        assert "<details>" in joined
        assert "<summary>💭 思考过程</summary>" in joined
        assert "思考中" in joined
        assert "</details>" in joined
        # 正文流
        assert "正文A" in joined
        # 工具调用
        assert "bash" in joined
        assert "ls" in joined
        # 工具执行
        assert "file1.txt" in joined
        # 收尾：「▶️ Agent 开始」「⏹️ Agent 结束」视觉帧已删除
        # （开始态由前端 loading 动画表达，结束态由 DONE 事件 + 节点徽章表达，
        #  重复帧只占 AI 建议区空间），此处断言它们不再出现。
        assert "[Agent 开始]" not in joined
        assert "[Agent 结束]" not in joined
        assert "full-cycle-1" in joined
        # 协议结束信号被识别
        assert "异常中断" not in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_non_json_lines_suppressed(self, mock_path, tmp_path):
        """[url-provider] registered ... 噪声不应 yield 到前端"""
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '[url-provider] registered cli-url/aaa ctx=200000 max=200000 api=openai-completions\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        # 噪声不应出现在前端流里
        assert "[url-provider]" not in joined
        assert "cli-url" not in joined
        # 协议结束信号被识别
        assert "异常中断" not in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_toolcall_end_shows_action(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "message_update", "assistantMessageEvent": {"type": "toolcall_end", "contentIndex": 2, "toolCall": {"type": "toolCall", "id": "t1", "name": "read_file", "arguments": {"file_path": "/etc/hosts"}}}}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        assert "read_file" in joined
        assert "/etc/hosts" in joined
        assert "<details>" in joined
        assert "</details>" in joined

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_pi_tool_execution_end_shows_result(self, mock_path, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import parse_agent_output
        mock_path.return_value = str(tmp_path)
        proc = self._make_process([
            '{"type": "tool_execution_start", "toolCallId": "t1", "toolName": "bash", "args": {"command": "ls"}}\n',
            '{"type": "tool_execution_end", "toolCallId": "t1", "toolName": "bash", "result": {"content": [{"type": "text", "text": "a.txt b.txt"}]}, "isError": false}\n',
            '{"type": "agent_settled"}\n',
            ''
        ])
        lines = list(parse_agent_output(proc))
        joined = b"".join(lines).decode("utf-8")
        assert "a.txt" in joined
        assert "b.txt" in joined
        # tool_execution_start 开了折叠块，end 时闭合
        assert joined.count("<details>") >= 1
        assert joined.count("</details>") >= 1


# ---------------------------------------------------------------------------
# cleanup_process - timeout branch
# ---------------------------------------------------------------------------
class TestCleanupProcessTimeout:
    def test_terminate_timeout_kills(self):
        from plugin.codemig.ai_assistant.query_ai_handler import cleanup_process
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="x", timeout=5), None]
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = None
        cleanup_process(mock_proc)
        mock_proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# generate_agent_response
# ---------------------------------------------------------------------------
class TestGenerateAgentResponse:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_result')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.rescan_file')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.insert_generated_files_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_basic(self, mock_path, mock_insert, mock_rescan, mock_git, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_agent_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)
        mock_insert.return_value = (True, "ok")
        mock_git.return_value = (True, "ok")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout.readline.side_effect = [
            '{"type": "result", "subtype": "success", "result": "done"}\n', ''
        ]
        mock_proc.returncode = 0

        gen = generate_agent_response(mock_proc, "user", 1, file_id=1, request_uuid="uuid", start_time=0.0)
        lines = list(gen)
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_result')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.rescan_file')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.insert_generated_files_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_exception_in_stream(self, mock_path, mock_insert, mock_rescan, mock_git, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_agent_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)
        mock_insert.return_value = (True, "ok")
        mock_git.return_value = (True, "ok")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout.readline.side_effect = OSError("pipe broken")
        mock_proc.returncode = 0

        gen = generate_agent_response(mock_proc, "user", 1, file_id=None, request_uuid="uuid", start_time=0.0)
        # OSError is caught internally by parse_agent_output, so the generator completes gracefully
        lines = list(gen)
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# insert_generated_files_to_database
# ---------------------------------------------------------------------------
class TestInsertGeneratedFilesToDatabase:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_by_path_from_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.save_generated_file_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_new_files_from_git')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_repo_path')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_user_id_from_database')
    def test_success_with_new_files(self, mock_uid, mock_repo, mock_git, mock_save, mock_query, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import insert_generated_files_to_database
        mock_uid.return_value = (True, 1)
        mock_git.return_value = (True, ["sub/newfile.c"])
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "sub").mkdir()
        (repo_path / "sub" / "newfile.c").write_text("code")
        mock_repo.return_value = repo_path
        mock_query.return_value = (True, None)  # file not in db
        mock_save.return_value = (True, 1)
        ok, msg = insert_generated_files_to_database("user", 1, 10)
        assert ok is True

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_user_id_from_database')
    def test_uid_failed(self, mock_uid):
        from plugin.codemig.ai_assistant.query_ai_handler import insert_generated_files_to_database
        mock_uid.return_value = (False, None)
        ok, msg = insert_generated_files_to_database("user", 1, 10)
        assert ok is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_new_files_from_git')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_user_id_from_database')
    def test_git_failed(self, mock_uid, mock_git):
        from plugin.codemig.ai_assistant.query_ai_handler import insert_generated_files_to_database
        mock_uid.return_value = (True, 1)
        mock_git.return_value = (False, [])
        ok, msg = insert_generated_files_to_database("user", 1, 10)
        assert ok is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_new_files_from_git')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_user_id_from_database')
    def test_no_new_files(self, mock_uid, mock_git):
        from plugin.codemig.ai_assistant.query_ai_handler import insert_generated_files_to_database
        mock_uid.return_value = (True, 1)
        mock_git.return_value = (True, [])
        ok, msg = insert_generated_files_to_database("user", 1, 10)
        assert ok is True

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_new_files_from_git')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_user_id_from_database')
    def test_oserror(self, mock_uid, mock_git):
        from plugin.codemig.ai_assistant.query_ai_handler import insert_generated_files_to_database
        mock_uid.return_value = (True, 1)
        mock_git.side_effect = OSError("disk error")
        ok, msg = insert_generated_files_to_database("user", 1, 10)
        assert ok is False


# ---------------------------------------------------------------------------
# generate_streaming_response - more branches
# ---------------------------------------------------------------------------
class TestGenerateStreamingResponseExtended:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_oserror(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.iter_lines.side_effect = OSError("broken pipe")

        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_reasoning_to_content(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"reasoning_content": "thinking..."}}]}',
            b'data: {"choices": [{"delta": {"reasoning_content": "more..."}}]}',
            b'data: {"choices": [{"delta": {"content": "answer"}}]}',
            b'data: [DONE]'
        ]
        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_json_decode_error(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {invalid json}',
            b'data: [DONE]'
        ]
        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        assert len(lines) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path')
    def test_empty_delta(self, mock_path, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_streaming_response
        mock_path.return_value = str(tmp_path)
        log_dir = tmp_path / "user" / "1"
        log_dir.mkdir(parents=True)

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {}}]}',
            b'data: [DONE]'
        ]
        result = generate_streaming_response(mock_resp, "user", 1, "uuid-123", 0.0)
        lines = list(result)
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# create_ai_response - think_mode branches
# ---------------------------------------------------------------------------
class TestCreateAiResponse:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_normal_mode(self, mock_post, mock_db, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_resp
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value=str(tmp_path)):
            log_dir = tmp_path / "user" / "1"
            log_dir.mkdir(parents=True, exist_ok=True)
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion'):
                resp = create_ai_response("content", "normal", "/path", "file.c",
                                         {"api_key": "", "base_url": "", "model": ""},
                                         "uuid", "user", 1, "", file_id=1, start_time=0.0)
                assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_reasoning_mode_default(self, mock_post, mock_db, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_resp
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value=str(tmp_path)):
            log_dir = tmp_path / "user" / "1"
            log_dir.mkdir(parents=True, exist_ok=True)
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion'):
                resp = create_ai_response("content", "reasoning", "/path", "file.c",
                                         None, "uuid", "user", 1, "", file_id=1, start_time=0.0)
                assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_reasoning_mode_custom_model(self, mock_post, mock_db, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_resp
        agent_config = {"model": "custom-model", "api_key": "sk-xxx", "base_url": "https://api.test.com"}
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value=str(tmp_path)):
            log_dir = tmp_path / "user" / "1"
            log_dir.mkdir(parents=True, exist_ok=True)
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion'):
                resp = create_ai_response("content", "reasoning", "/path", "file.c",
                                         agent_config, "uuid", "user", 1, "", file_id=1, start_time=0.0)
                assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_reasoning_mode_base_model(self, mock_post, mock_db, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_resp
        agent_config = {"model": "BASE_MODEL", "api_key": "sk-xxx", "base_url": "https://api.test.com"}
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value=str(tmp_path)):
            log_dir = tmp_path / "user" / "1"
            log_dir.mkdir(parents=True, exist_ok=True)
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_suggestion'):
                resp = create_ai_response("content", "reasoning", "/path", "file.c",
                                         agent_config, "uuid", "user", 1, "", file_id=1, start_time=0.0)
                assert resp is not None

    def test_no_think_mode(self):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        resp = create_ai_response("content", "", "/path", "file.c",
                                 None, "uuid", "user", 1, "")
        assert resp is not None

    def test_unknown_think_mode(self):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_response
        resp = create_ai_response("content", "unknown_mode", "/path", "file.c",
                                 None, "uuid", "user", 1, "")
        assert resp is not None


# ---------------------------------------------------------------------------
# _handle_agent_mode
# ---------------------------------------------------------------------------
class TestHandleAgentMode:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_agent_process')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    def test_basic(self, mock_git, mock_create_proc, mock_db):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode
        mock_git.return_value = (True, "ok")
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['']
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_create_proc.return_value = mock_proc
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value="/tmp"):
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_result'):
                resp = _handle_agent_mode("content", "/path", "file.c",
                                         {"api_key": "k"}, "uuid", "user", 1, "",
                                         file_id=1, model="m", start_time=0.0)
                assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.save_intermediate_state_on_failure')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_agent_process')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    def test_file_not_found(self, mock_git, mock_create_proc, mock_save_mid, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode
        mock_git.return_value = (True, "ok")
        mock_create_proc.side_effect = FileNotFoundError("dir missing")
        resp = _handle_agent_mode("content", "/path", "file.c",
                                 {"api_key": "k"}, "uuid", "user", 1, "",
                                 file_id=1, model="m", start_time=0.0)
        assert resp is not None
        # V7：异常路径不再 restore_workspace，改为中间态 commit 留痕（保留 agent 半成品）
        mock_save_mid.assert_called_once_with("user", 1, reason='intermediate-error')

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.save_intermediate_state_on_failure')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_agent_process')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    def test_general_exception(self, mock_git, mock_create_proc, mock_save_mid, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode
        mock_git.return_value = (True, "ok")
        mock_create_proc.side_effect = RuntimeError("boom")
        resp = _handle_agent_mode("content", "/path", "file.c",
                                 {"api_key": "k"}, "uuid", "user", 1, "",
                                 file_id=1, model="m", start_time=0.0)
        assert resp is not None
        mock_save_mid.assert_called_once_with("user", 1, reason='intermediate-error')


# ---------------------------------------------------------------------------
# create_agent_process
# ---------------------------------------------------------------------------
class TestCreateAgentProcess:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess.Popen')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.SysConfig')
    def test_openai_format(self, mock_config, mock_popen):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_process
        mock_config.query_system_configuration.return_value = (True, "", "")
        mock_popen.return_value = MagicMock()
        cmd_list = []
        agent_config = {"api_key": "sk-test", "base_url": "https://api.test.com", "model": "gpt-4"}
        proc = create_agent_process("test prompt", "/path", agent_config, "uuid-1", cmd_list, "openai")
        assert proc is not None
        assert len(cmd_list) > 0

    @patch('plugin.codemig.ai_assistant.query_ai_handler.subprocess.Popen')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.SysConfig')
    def test_cursor_format(self, mock_config, mock_popen):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_process
        mock_config.query_system_configuration.return_value = (True, "", "")
        mock_popen.return_value = MagicMock()
        cmd_list = []
        agent_config = {"api_key": "cursor-key", "model": "claude"}
        proc = create_agent_process("test prompt", "/path", agent_config, "uuid-1", cmd_list, "cursor")
        assert proc is not None

    def test_no_api_key(self):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_process
        cmd_list = []
        agent_config = {"api_key": ""}
        result = create_agent_process("test", "/path", agent_config, "uuid", cmd_list, "openai")
        assert result["code"] == -1

    def test_unknown_format(self):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_process
        cmd_list = []
        agent_config = {"api_key": "key"}
        result = create_agent_process("test", "/path", agent_config, "uuid", cmd_list, "unknown")
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# _make_ai_request_and_stream
# ---------------------------------------------------------------------------
class TestMakeAiRequestAndStream:
    def test_no_request_uuid(self):
        from plugin.codemig.ai_assistant.query_ai_handler import _make_ai_request_and_stream
        resp = _make_ai_request_and_stream({}, "model", "", request_uuid="")
        assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_timeout(self, mock_post, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import _make_ai_request_and_stream
        mock_post.side_effect = requests.Timeout("timeout")
        resp = _make_ai_request_and_stream({"model": "m"}, "DeepSeek", "",
                                            user_name="u", dir_id=1, request_uuid="uuid", start_time=0.0)
        assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.requests.post')
    def test_request_exception(self, mock_post, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import _make_ai_request_and_stream
        mock_post.side_effect = requests.RequestException("conn error")
        resp = _make_ai_request_and_stream({"model": "m"}, "DeepSeek", "",
                                            user_name="u", dir_id=1, request_uuid="uuid", start_time=0.0)
        assert resp is not None


# ---------------------------------------------------------------------------
# query_ai_suggestion exception paths
# ---------------------------------------------------------------------------
class TestQueryAiSuggestionExceptions:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_response')
    def test_timeout_exception(self, mock_resp):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion
        mock_resp.side_effect = requests.Timeout("timeout")
        result = query_ai_suggestion("content", "normal", "/path", "f.c",
                                    None, "uuid", "user", 1, "",
                                    file_id=1, start_time=0.0)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_response')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    def test_general_exception(self, mock_exc, mock_resp):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion
        mock_resp.side_effect = RuntimeError("unexpected")
        result = query_ai_suggestion("content", "normal", "/path", "f.c",
                                    None, "uuid", "user", 1, "",
                                    file_id=1, start_time=0.0)
        assert result is not None


# ---------------------------------------------------------------------------
# query_query_ai_suggestion_data
# ---------------------------------------------------------------------------
class TestQueryQueryAiSuggestionData:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.FileDependenceSuggestion')
    def test_with_dependence_id(self, mock_model):
        from plugin.codemig.ai_assistant.query_ai_handler import query_query_ai_suggestion_data
        mock_model.get_ai_suggestion_data.return_value = ("task", "path", 1, 10, "sug")
        result = query_query_ai_suggestion_data(1, 1, 1, 1, 1, 99)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_conn')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_database_path')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_dependence_success(self, mock_tasks, mock_um, mock_db_path, mock_conn):
        from plugin.codemig.ai_assistant.query_ai_handler import query_query_ai_suggestion_data
        mock_tasks.get_task_name.return_value = "task1"
        mock_user = MagicMock()
        mock_user.user_name = "user1"
        mock_um.query_by_id.return_value = mock_user
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = mock_path
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("/path/file.c", 1, 1, 10, "sug")
        mock_c = MagicMock()
        mock_c.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_c
        result = query_query_ai_suggestion_data(1, 1, 1, 1, 1, None)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_task_name(self, mock_tasks):
        from plugin.codemig.ai_assistant.query_ai_handler import query_query_ai_suggestion_data
        mock_tasks.get_task_name.return_value = None
        result = query_query_ai_suggestion_data(1, 1, 1, 1, 1, None)
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_user(self, mock_tasks, mock_um):
        from plugin.codemig.ai_assistant.query_ai_handler import query_query_ai_suggestion_data
        mock_tasks.get_task_name.return_value = "task1"
        mock_um.query_by_id.return_value = None
        result = query_query_ai_suggestion_data(1, 1, 1, 1, 1, None)
        assert result is None


# ---------------------------------------------------------------------------
# query_file_info
# ---------------------------------------------------------------------------
class TestQueryFileInfo:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.FileDependence')
    def test_with_dependence_id(self, mock_model):
        from plugin.codemig.ai_assistant.query_ai_handler import query_file_info
        mock_model.get_task_name_and_file_path.return_value = ("task", "/path")
        result = query_file_info(1, 1, 1, 1, 99)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_task_name(self, mock_tasks):
        from plugin.codemig.ai_assistant.query_ai_handler import query_file_info
        mock_tasks.get_task_name.return_value = None
        result = query_file_info(1, 1, 1, 1, None)
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_conn')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_database_path')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_success(self, mock_tasks, mock_um, mock_db_path, mock_conn):
        from plugin.codemig.ai_assistant.query_ai_handler import query_file_info
        mock_tasks.get_task_name.return_value = "task1"
        mock_user = MagicMock()
        mock_user.user_name = "user1"
        mock_um.query_by_id.return_value = mock_user
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = mock_path
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("/path/file.c",)
        mock_c = MagicMock()
        mock_c.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_c
        result = query_file_info(1, 1, 1, 1, None)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_conn')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_database_path')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_result(self, mock_tasks, mock_um, mock_db_path, mock_conn):
        from plugin.codemig.ai_assistant.query_ai_handler import query_file_info
        mock_tasks.get_task_name.return_value = "task1"
        mock_user = MagicMock()
        mock_user.user_name = "user1"
        mock_um.query_by_id.return_value = mock_user
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = mock_path
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_c = MagicMock()
        mock_c.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_c
        result = query_file_info(1, 1, 1, 1, None)
        assert result is None


# ---------------------------------------------------------------------------
# query_ai_suggestion_data_for_agent
# ---------------------------------------------------------------------------
class TestQueryAiSuggestionDataForAgent:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.FileDependenceSuggestion')
    def test_with_dependence_id(self, mock_model):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_data_for_agent
        mock_model.get_all_ai_suggestion_data.return_value = [("task", "path", 1, 10, "sug")]
        result = query_ai_suggestion_data_for_agent(1, 1, 1, 1, 99)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_no_task_name(self, mock_tasks):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_data_for_agent
        mock_tasks.get_task_name.return_value = None
        result = query_ai_suggestion_data_for_agent(1, 1, 1, 1, None)
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_conn')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_database_path')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.UserManager')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.CodemigTasks')
    def test_success(self, mock_tasks, mock_um, mock_db_path, mock_conn):
        from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_data_for_agent
        mock_tasks.get_task_name.return_value = "task1"
        mock_user = MagicMock()
        mock_user.user_name = "user1"
        mock_um.query_by_id.return_value = mock_user
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_db_path.return_value = mock_path
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("/path/file.c", 1, 1, 10, "sug")]
        mock_c = MagicMock()
        mock_c.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_c
        result = query_ai_suggestion_data_for_agent(1, 1, 1, 1, None)
        assert result is not None
        assert len(result) == 1


# ---------------------------------------------------------------------------
# create_agent_content - more branches
# ---------------------------------------------------------------------------
class TestCreateAgentContentExtended:
    def test_all_asm(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        f = tmp_path / "test.s"
        f.write_text("mov rax, rbx\n")
        query_data = [
            ("task1", str(f), SolverType.INLINE_ASM.value, 1, 1, "fix"),
        ]
        result = create_agent_content(query_data, "test.s")
        assert "migrate" in result or "汇编" in result or "agent" in result.lower()

    def test_all_non_asm(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        f = tmp_path / "Makefile"
        f.write_text("CC=gcc\nall:\n\t$(CC) main.c\n")
        query_data = [
            ("task1", str(f), SolverType.MAKEFILE.value, 1, 1, "建议修改"),
        ]
        result = create_agent_content(query_data, "Makefile")
        assert result is not None

    def test_mixed_asm_and_non_asm(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        f1 = tmp_path / "test.s"
        f1.write_text("mov rax, rbx\n")
        f2 = tmp_path / "Makefile"
        f2.write_text("CC=gcc\n")
        query_data = [
            ("task1", str(f1), SolverType.INLINE_ASM.value, 1, 1, "asm fix"),
            ("task2", str(f2), SolverType.MAKEFILE.value, 1, 1, "make fix"),
        ]
        result = create_agent_content(query_data, "mixed")
        assert result is not None

    def test_file_read_error(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        query_data = [
            ("task1", "/nonexistent/file.c", SolverType.MAKEFILE.value, 1, 1, "fix"),
        ]
        result = create_agent_content(query_data, "file.c")
        assert result is not None

    def test_fallback_hint_for_unmapped_type(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        f = tmp_path / "test.py"
        f.write_text("print('hello')\n")
        query_data = [
            ("task1", str(f), SolverType.PYTHON_SOURCE_CODE.value, 1, 1, "fix python"),
        ]
        result = create_agent_content(query_data, "test.py")
        assert result is not None

    def test_fallback_hint_for_none_type(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import create_agent_content
        f = tmp_path / "unknown"
        f.write_text("content\n")
        query_data = [
            ("task1", str(f), None, 1, 1, "fix unknown"),
        ]
        result = create_agent_content(query_data, "unknown")
        assert result is not None


# ---------------------------------------------------------------------------
# _get_selected_lines_data
# ---------------------------------------------------------------------------
class TestGetSelectedLinesData:
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_solver_type_from_file')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info')
    def test_success(self, mock_qfi, mock_solver):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_selected_lines_data
        mock_qfi.return_value = ("task1", "/data/123/proj/file.c")
        mock_solver.return_value = (SolverType.ASM_FILE.value, SolverType.ASM_FILE)
        result = _get_selected_lines_data(1, 1, 1, 1, None, 10, 20)
        assert result is not None
        assert result["task_name"] == "task1"

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info')
    def test_file_not_found(self, mock_qfi):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_selected_lines_data
        mock_qfi.return_value = None
        result = _get_selected_lines_data(1, 1, 1, 1, None, 10, 20)
        assert result is None


# ---------------------------------------------------------------------------
# _get_suggestion_data
# ---------------------------------------------------------------------------
class TestGetSuggestionData:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_query_ai_suggestion_data')
    def test_success(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_suggestion_data
        mock_query.return_value = ("task1", "/data/123/proj/file.c", 1, 1, 10, "suggestion")
        result = _get_suggestion_data(1, 1, 1, 1, 1, None)
        assert result is not None
        assert result["task_name"] == "task1"

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_query_ai_suggestion_data')
    def test_not_found(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_suggestion_data
        mock_query.return_value = None
        result = _get_suggestion_data(1, 1, 1, 1, 1, None)
        assert result is None


# ---------------------------------------------------------------------------
# _get_code_and_suggestion
# ---------------------------------------------------------------------------
class TestGetCodeAndSuggestion:
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_selected_lines_data')
    def test_selected_lines_returns_none(self, mock_sel):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_code_and_suggestion
        mock_sel.return_value = None
        result = _get_code_and_suggestion(1, 1, 1, 1, None, None, 10, 20, "normal")
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler._handle_agent_mode_data')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_selected_lines_data')
    def test_agent_mode(self, mock_sel, mock_agent):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_code_and_suggestion
        mock_sel.return_value = {"task_name": "t", "file_path": "/f", "file_dir": "/d", "file_name": "f.c",
                                 "query_data": {"file_path": "/f", "start_line": 1, "end_line": 10, "suggestion": "s"}}
        mock_agent.return_value = {"type": "agent", "task_name": "t"}
        result = _get_code_and_suggestion(1, 1, 1, 1, None, None, 10, 20, "agent")
        assert result is not None
        assert result["type"] == "agent"

    @patch('plugin.codemig.ai_assistant.query_ai_handler._handle_suggestion_mode_data')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_selected_lines_data')
    def test_suggestion_mode_with_selected(self, mock_sel, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_code_and_suggestion
        mock_sel.return_value = {"task_name": "t", "file_path": "/f", "file_dir": "/d", "file_name": "f.c",
                                 "query_data": {"file_path": "/f", "start_line": 1, "end_line": 10, "suggestion": "s"}}
        mock_sug.return_value = {"type": "suggestion", "task_name": "t"}
        result = _get_code_and_suggestion(1, 1, 1, 1, None, None, 10, 20, "normal")
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler._handle_suggestion_mode_data')
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_selected_lines_data')
    def test_no_valid_params(self, mock_sel, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _get_code_and_suggestion
        mock_sug.return_value = None
        result = _get_code_and_suggestion(1, 1, 1, 1, None, None, None, None, "normal")
        assert result is None


# ---------------------------------------------------------------------------
# _handle_agent_mode_data
# ---------------------------------------------------------------------------
class TestHandleAgentModeData:
    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_selected_lines_data')
    def test_with_valid_selected(self, mock_sel):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode_data
        mock_sel.return_value = {"task_name": "t", "file_path": "/f", "file_dir": "/d", "file_name": "f.c",
                                 "query_data": {"file_path": "/f", "start_line": 1, "end_line": 10, "suggestion": "s"}}
        result = _handle_agent_mode_data(1, 1, 1, 1, None, mock_sel.return_value, True, None)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_suggestion_data')
    def test_with_change_id(self, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode_data
        mock_sug.return_value = {"task_name": "t", "file_path": "/data/123/f.c", "file_dir": "/d",
                                 "file_name": "f.c", "query_data": {"file_path": "/f", "type": 1,
                                 "start_line": 1, "end_line": 10, "suggestion": "s"}, "change_id": 1}
        result = _handle_agent_mode_data(1, 1, 1, 1, 1, None, False, 1)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_suggestion_data')
    def test_change_id_not_found(self, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode_data
        mock_sug.return_value = None
        result = _handle_agent_mode_data(1, 1, 1, 1, 1, None, False, 1)
        assert result is None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion_data_for_agent')
    def test_query_all_suggestions(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode_data
        mock_query.return_value = [("task", "/data/123/f.c", None, 1, 10, "sug")]
        result = _handle_agent_mode_data(1, 1, 1, 1, None, None, False, None)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion_data_for_agent')
    def test_no_suggestions(self, mock_query):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_agent_mode_data
        mock_query.return_value = None
        result = _handle_agent_mode_data(1, 1, 1, 1, None, None, False, None)
        assert result is None


# ---------------------------------------------------------------------------
# _handle_suggestion_mode_data
# ---------------------------------------------------------------------------
class TestHandleSuggestionModeData:
    def test_with_valid_selected(self):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_suggestion_mode_data
        selected_data = {"task_name": "t", "file_path": "/f", "file_dir": "/d",
                         "file_name": "f.c", "query_data": {"k": "v"}}
        result = _handle_suggestion_mode_data(1, 1, 1, 1, None, None, selected_data, True)
        assert result is not None
        assert result["type"] == "suggestion"

    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_suggestion_data')
    def test_with_change_id(self, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_suggestion_mode_data
        mock_sug.return_value = {"task_name": "t", "file_path": "/data/123/f.c",
                                 "file_dir": "/d", "file_name": "f.c",
                                 "query_data": {"file_path": "/f", "type": 1, "start_line": 1,
                                                "end_line": 10, "suggestion": "s"},
                                 "change_id": 1}
        result = _handle_suggestion_mode_data(1, 1, 1, 1, 1, None, False, 1)
        assert result is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler._get_suggestion_data')
    def test_change_id_not_found(self, mock_sug):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_suggestion_mode_data
        mock_sug.return_value = None
        result = _handle_suggestion_mode_data(1, 1, 1, 1, 1, None, False, 1)
        assert result is None

    def test_no_params(self):
        from plugin.codemig.ai_assistant.query_ai_handler import _handle_suggestion_mode_data
        result = _handle_suggestion_mode_data(1, 1, 1, 1, None, None, False, None)
        assert result is None


# ---------------------------------------------------------------------------
# rescan_file - extended
# ---------------------------------------------------------------------------
class TestRescanFileExtended:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_file_suggestion_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.process_updated_file')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info_from_database')
    def test_file_not_changed(self, mock_query, mock_process, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import rescan_file
        from plugin.codemig.ai_assistant.query_ai_handler import FileSource
        f = tmp_path / "file.c"
        f.write_text("int main(){}")
        mock_query.return_value = (True, (str(f), FileSource.ORIGINAL.value, 0, True))
        result = rescan_file("user", 1, 1)
        assert result is False

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_file_suggestion_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.process_updated_file')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.query_file_info_from_database')
    def test_success(self, mock_query, mock_process, mock_update, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import rescan_file
        from plugin.codemig.ai_assistant.query_ai_handler import FileSource
        f = tmp_path / "file.c"
        f.write_text("int main(){}")
        mock_query.return_value = (True, (str(f), FileSource.CHANGED.value, 0, True))
        mock_process.return_value = [("sug1", 1, 10)]
        mock_update.return_value = True
        result = rescan_file("user", 1, 1)
        assert result is True


# ---------------------------------------------------------------------------
# create_ai_agent_file
# ---------------------------------------------------------------------------
class TestCreateAiAgentFile:
    def test_no_request_uuid(self):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_agent_file
        resp = create_ai_agent_file("/path/file.c", 1, [], "model", "openai", "user", 1, None)
        assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    def test_no_model(self, mock_config):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_agent_file
        resp = create_ai_agent_file("/data/123/proj/file.c", 123, [], None, "openai", "user", 1, "uuid")
        assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_agent_process')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_ai_info_to_database')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    def test_success(self, mock_config, mock_git, mock_db, mock_proc):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_agent_file
        mock_config.return_value = {"api_key": "k", "base_url": "u", "model": "m"}
        mock_git.return_value = (True, "ok")
        mock_proc_instance = MagicMock()
        mock_proc_instance.stdout.readline.side_effect = ['']
        mock_proc_instance.poll.return_value = 0
        mock_proc_instance.returncode = 0
        mock_proc.return_value = mock_proc_instance
        with patch('plugin.codemig.ai_assistant.query_ai_handler.get_codemig_data_path', return_value="/tmp"):
            with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_result'):
                resp = create_ai_agent_file("/data/123/proj/file.c", 123, [], "model", "openai",
                                           "user", 1, "uuid-123")
                assert resp is not None

    @patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.save_intermediate_state_on_failure')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.create_agent_process')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.commit_git_repo')
    @patch('plugin.codemig.ai_assistant.query_ai_handler.get_agent_config_from_db')
    def test_exception(self, mock_config, mock_git, mock_create_proc, mock_save_mid, mock_exc):
        from plugin.codemig.ai_assistant.query_ai_handler import create_ai_agent_file
        mock_config.return_value = {"api_key": "k", "base_url": "u", "model": "m"}
        mock_git.return_value = (True, "ok")
        mock_create_proc.side_effect = Exception("docker fail")
        with patch('plugin.codemig.ai_assistant.query_ai_handler.update_ai_exception'):
            resp = create_ai_agent_file("/data/123/proj/file.c", 123, [], "model", "openai",
                                       "user", 1, "uuid-123")
            assert resp is not None
            # V7：异常路径不再 restore_workspace，改为中间态 commit 留痕
            mock_save_mid.assert_called_once_with("user", 123, reason='intermediate-error')


# ---------------------------------------------------------------------------
# _create_suggestion_content - extended
# ---------------------------------------------------------------------------
class TestCreateSuggestionContentExtended:
    def test_returns_none_tuple_on_empty(self, tmp_path):
        from plugin.codemig.ai_assistant.query_ai_handler import _create_suggestion_content
        code_data = {
            'query_data': {
                'file_path': str(tmp_path / "nonexistent.c"),
                'type': SolverType.GO_RELEASER_TML.value,
                'start_line': 1, 'end_line': 2,
                'suggestion': 'fix', 'is_selected_lines': False
            }
        }
        result = _create_suggestion_content(code_data)
        # GO_RELEASER_TML returns None from _create_content_by_solver_type → returns (None, None, None, None)
        assert result == (None, None, None, None)


# ---------------------------------------------------------------------------
# truncate_suggestion_for_db
# ---------------------------------------------------------------------------
class TestTruncateSuggestionForDb:
    def test_short_content_unchanged(self):
        assert truncate_suggestion_for_db("hello") == "hello"
        assert truncate_suggestion_for_db("") == ""

    def test_exact_boundary_not_truncated(self):
        text = "a" * (300_000 + 100_000)
        assert truncate_suggestion_for_db(text) == text

    def test_over_limit_head_tail_preserved(self):
        head = "H" * 300_000
        mid = "M" * 50_000
        tail = "T" * 100_000
        text = head + mid + tail
        result = truncate_suggestion_for_db(text)
        assert result.startswith("H" * 1000)
        assert result.endswith("T" * 1000)
        assert len(result) < len(text)
        assert "已省略" in result
        # 中段 M 不应残留（除省略标记里的数字外）
        assert "M" * 100 not in result

    def test_custom_limits(self):
        text = "a" * 10 + "b" * 10
        result = truncate_suggestion_for_db(text, head_limit=5, tail_limit=5)
        assert result.startswith("aaaaa")
        assert result.endswith("bbbbb")
        assert "已省略 10 字符" in result

    def test_non_string_passthrough(self):
        assert truncate_suggestion_for_db(None) is None
        assert truncate_suggestion_for_db(123) == 123


# ---------------------------------------------------------------------------
# list_project_migrate_history_handler - F3：max_count=200 回归
# ---------------------------------------------------------------------------
class TestListProjectMigrateHistoryHandler:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.list_project_history')
    def test_success_passes_max_count_200(self, mock_history):
        """F3 回归：必须显式传 max_count=200，否则超长任务历史下拉被默认 50 截断"""
        from plugin.codemig.ai_assistant.query_ai_handler import (
            list_project_migrate_history_handler)
        mock_history.return_value = (True, [{'hash': 'aaa', 'time': '2025-01-01 00:00:00'}])

        result = list_project_migrate_history_handler('user1', 1)

        mock_history.assert_called_once_with('user1', 1, max_count=200)
        assert result == {'code': 0, 'data': [{'hash': 'aaa', 'time': '2025-01-01 00:00:00'}]}

    @patch('plugin.codemig.ai_assistant.query_ai_handler.list_project_history')
    def test_failure_returns_code_1(self, mock_history):
        from plugin.codemig.ai_assistant.query_ai_handler import (
            list_project_migrate_history_handler)
        mock_history.return_value = (False, "Code path does not exist.")

        result = list_project_migrate_history_handler('user1', 1)

        assert result == {'code': 1, 'msg': "Code path does not exist."}


# ---------------------------------------------------------------------------
# generate_project_patch_handler - 增量补丁导出
# ---------------------------------------------------------------------------
class TestGenerateProjectPatchHandler:
    @patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between')
    def test_empty_from_hash_rejected(self, mock_between):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_project_patch_handler
        result = generate_project_patch_handler('user1', 1, '')
        assert result['code'] == 1
        mock_between.assert_not_called()

    @patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between')
    def test_success_without_to_hash(self, mock_between):
        """to_hash 缺省时应以位置参数 None 透传（后端自动取 HEAD）"""
        from plugin.codemig.ai_assistant.query_ai_handler import generate_project_patch_handler
        mock_between.return_value = (True, "# patch content")

        result = generate_project_patch_handler('user1', 1, 'aaa11111')

        mock_between.assert_called_once_with('user1', 1, 'aaa11111', None)
        assert result == {'code': 0, 'data': "# patch content"}

    @patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between')
    def test_success_with_to_hash(self, mock_between):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_project_patch_handler
        mock_between.return_value = (True, "# patch content")

        result = generate_project_patch_handler('user1', 1, 'aaa11111', 'bbb22222')

        mock_between.assert_called_once_with('user1', 1, 'aaa11111', 'bbb22222')
        assert result == {'code': 0, 'data': "# patch content"}

    @patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between')
    def test_git_failure_returns_code_1(self, mock_between):
        from plugin.codemig.ai_assistant.query_ai_handler import generate_project_patch_handler
        mock_between.return_value = (False, "Git command error: boom")

        result = generate_project_patch_handler('user1', 1, 'aaa11111')

        assert result == {'code': 1, 'msg': "Git command error: boom"}
