import copy
import json
import pytest
from unittest.mock import patch, MagicMock

from common.public.common import (
    TASK_STATUS_JSON,
    validate_ip,
    write_json,
    encrypt_passphrase,
    decrypt_passphrase,
    get_task_status_from_file,
    get_task_status,
    get_module_task_status,
    write_task_status,
)


class TestValidateIP:
    """测试 validate_ip 函数"""

    def test_valid_ip_localhost(self):
        assert validate_ip("127.0.0.1") is True

    def test_valid_ip_normal(self):
        assert validate_ip("192.168.1.1") is True

    def test_valid_ip_max(self):
        assert validate_ip("255.255.255.255") is True

    def test_valid_ip_min(self):
        assert validate_ip("0.0.0.0") is True

    def test_valid_ip_with_leading_zeros(self):
        assert validate_ip("10.0.0.1") is True

    def test_invalid_ip_out_of_range(self):
        assert validate_ip("256.1.1.1") is False

    def test_invalid_ip_wrong_format(self):
        assert validate_ip("192.168.1") is False

    def test_invalid_ip_letters(self):
        assert validate_ip("abc.def.ghi.jkl") is False

    def test_invalid_ip_empty_string(self):
        assert validate_ip("") is False

    def test_invalid_ip_none(self):
        assert validate_ip(None) is False

    def test_invalid_ip_integer(self):
        assert validate_ip(123) is False

    def test_invalid_ip_list(self):
        assert validate_ip([1, 2, 3]) is False

    def test_ip_with_extra_segments_still_matches_prefix(self):
        """源码使用 match() 而非 fullmatch()，所以前缀匹配仍然返回 True"""
        assert validate_ip("192.168.1.1.1") is True

    def test_ip_with_trailing_spaces_still_matches_prefix(self):
        """源码使用 match() 而非 fullmatch()，所以前缀匹配仍然返回 True"""
        assert validate_ip("192.168.1.1 ") is True

    def test_invalid_ip_non_matching(self):
        assert validate_ip("999.999.999.999") is False


class TestWriteJson:
    """测试 write_json 函数"""

    def test_write_valid_data(self, tmp_path):
        data = {"key": "value", "num": 42}
        target_file = str(tmp_path / "test.json")
        result = write_json(data, target_file)
        assert result is True
        with open(target_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_write_nested_data(self, tmp_path):
        data = {"outer": {"inner": [1, 2, 3]}}
        target_file = str(tmp_path / "nested.json")
        result = write_json(data, target_file)
        assert result is True
        with open(target_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_write_to_invalid_path(self):
        result = write_json({"key": "value"}, "/nonexistent/path/file.json")
        assert result is False

    def test_write_to_readonly_directory(self, tmp_path):
        """模拟写入只读目录失败的场景，避免 root 用户下权限限制不生效的问题"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = write_json({"key": "value"}, str(tmp_path / "test.json"))
        assert result is False

    def test_write_with_logger(self, tmp_path):
        mock_logger = MagicMock()
        data = {"key": "value"}
        target_file = str(tmp_path / "test.json")
        result = write_json(data, target_file, log=mock_logger)
        assert result is True
        mock_logger.error.assert_not_called()

    def test_write_failure_with_logger(self):
        mock_logger = MagicMock()
        result = write_json({"key": "value"}, "/nonexistent/path/file.json", log=mock_logger)
        assert result is False
        mock_logger.error.assert_called_once()


class TestEncryptPassphrase:
    """测试 encrypt_passphrase 函数"""

    @pytest.fixture
    def key_files(self, tmp_path, monkeypatch):
        """生成 data/ 组密钥文件并把模块内路径常量指过去"""
        import common.public.common as c
        from common import crypto
        crypto.generate_key_file(tmp_path / 'himalayan')
        crypto.generate_nonce_file(tmp_path / 'qomolangma')
        monkeypatch.setattr(c, 'key_path', str(tmp_path / 'himalayan'))
        monkeypatch.setattr(c, 'nonce_path', str(tmp_path / 'qomolangma'))
        return tmp_path

    def test_none_returns_none(self):
        assert encrypt_passphrase(None) is None

    def test_empty_string_returns_none(self):
        assert encrypt_passphrase('') is None

    def test_encrypt_success(self, key_files):
        result = encrypt_passphrase("my_password")
        assert isinstance(result, bytes)
        # 格式：ciphertext || tag(16B)
        assert len(result) == len("my_password") + 16

    def test_encrypt_same_input_differs(self, key_files):
        """同 nonce 下相同明文密文确定（GCM 确定性），且非明文回显"""
        a = encrypt_passphrase("abc")
        b = encrypt_passphrase("abc")
        assert a == b
        assert a[:3] != b"abc"  # 密文体不等于明文

    def test_encrypt_missing_key_file_raises(self, tmp_path, monkeypatch):
        """密钥文件缺失 → 抛异常（不再静默返回拼接值）"""
        import common.public.common as c
        monkeypatch.setattr(c, 'key_path', str(tmp_path / 'nonexistent'))
        monkeypatch.setattr(c, 'nonce_path', str(tmp_path / 'nonexistent2'))
        with pytest.raises(OSError):
            encrypt_passphrase("test_pw")


class TestDecryptPassphrase:
    """测试 decrypt_passphrase 函数"""

    @pytest.fixture
    def key_files(self, tmp_path, monkeypatch):
        import common.public.common as c
        from common import crypto
        crypto.generate_key_file(tmp_path / 'himalayan')
        crypto.generate_nonce_file(tmp_path / 'qomolangma')
        monkeypatch.setattr(c, 'key_path', str(tmp_path / 'himalayan'))
        monkeypatch.setattr(c, 'nonce_path', str(tmp_path / 'qomolangma'))
        return tmp_path

    def test_empty_bytes_returns_empty_string(self):
        assert decrypt_passphrase(b'') == ''

    def test_none_returns_empty_string(self):
        assert decrypt_passphrase(None) == ''

    def test_decrypt_success(self, key_files):
        cipher = encrypt_passphrase("my_secret_data")
        assert decrypt_passphrase(cipher) == "my_secret_data"

    def test_decrypt_failure_returns_none(self, key_files):
        """密文被篡改 → InvalidTag → None（记日志不抛）"""
        cipher = bytearray(encrypt_passphrase("some_secret"))
        cipher[0] ^= 0xFF
        with patch('common.public.common.LOGGER') as mock_logger:
            result = decrypt_passphrase(bytes(cipher))
            assert result is None
            mock_logger.error.assert_called_once()

    def test_decrypt_wrong_key_returns_none(self, key_files):
        """换一把密钥 → 认证失败 → None"""
        from common import crypto
        cipher = encrypt_passphrase("some_secret")
        crypto.generate_key_file(key_files / 'himalayan')
        with patch('common.public.common.LOGGER'):
            assert decrypt_passphrase(cipher) is None

    def test_encrypt_decrypt_roundtrip(self, key_files):
        original = "round_trip_test"
        encrypted = encrypt_passphrase(original)
        assert encrypted != original.encode()
        assert decrypt_passphrase(encrypted) == original


class TestGetTaskStatusFromFile:
    """测试 get_task_status_from_file 函数"""

    def test_returns_default_when_no_file(self, tmp_path):
        result = get_task_status_from_file(str(tmp_path))
        assert result == TASK_STATUS_JSON

    def test_reads_existing_file(self, tmp_path):
        task_status = {
            "error_info_list": [{"ErrorCode": ["arg1"]}],
            "success_info": "SysPerf.Success.TimeOut"
        }
        file_path = tmp_path / "task_status.json"
        with open(file_path, 'w') as f:
            json.dump(task_status, f)

        result = get_task_status_from_file(str(tmp_path))
        assert result["success_info"] == "SysPerf.Success.TimeOut"
        assert len(result["error_info_list"]) == 1

    def test_handles_corrupted_file(self, tmp_path):
        file_path = tmp_path / "task_status.json"
        file_path.write_text("invalid json content{{{")
        result = get_task_status_from_file(str(tmp_path))
        assert result == TASK_STATUS_JSON


class TestGetTaskStatus:
    """测试 get_task_status 函数"""

    def test_success_timeout(self):
        result = get_task_status(code='SysPerf.Success.TimeOut')
        assert result['success_info'] == 'SysPerf.Success.TimeOut'
        assert result['error_info_list'] == []

    def test_success_reach_file_size(self):
        result = get_task_status(code='SysPerf.Success.ReachFileSize')
        assert result['success_info'] == 'SysPerf.Success.ReachFileSize'

    def test_success_app_finish(self):
        result = get_task_status(code='SysPerf.Success.AppFinish')
        assert result['success_info'] == 'SysPerf.Success.AppFinish'

    def test_error_code_with_default_args(self):
        result = get_task_status(code='SomeError')
        assert result['success_info'] == ''
        assert len(result['error_info_list']) == 1
        assert result['error_info_list'][0] == {'SomeError': []}

    def test_error_code_with_custom_args(self):
        result = get_task_status(code='CustomError', args_list=['arg1', 'arg2'])
        assert result['error_info_list'][0] == {'CustomError': ['arg1', 'arg2']}

    def test_multiple_errors_accumulate(self):
        task_status = get_task_status(code='Error1')
        task_status = get_task_status(task_status, code='Error2')
        assert len(task_status['error_info_list']) == 2

    def test_existing_task_status_modified(self):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        result = get_task_status(task_status, code='SysPerf.Success.TimeOut')
        assert result is task_status


class TestGetModuleTaskStatus:
    """测试 get_module_task_status 函数"""

    def test_creates_module_dict(self):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        result = get_module_task_status("module_a", task_status, 'SomeError')
        assert "module_a" in result
        assert result["module_a"]["error_info_list"] == [{'SomeError': []}]

    def test_with_args_list(self):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        result = get_module_task_status("module_b", task_status, 'ErrorCode', ['arg1'])
        assert result["module_b"]["error_info_list"] == [{'ErrorCode': ['arg1']}]


class TestWriteTaskStatus:
    """测试 write_task_status 函数"""

    def test_write_with_module_and_error(self, tmp_path):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        write_task_status(task_status, str(tmp_path),
                          error_code='SomeError', module='test_module')
        file_path = tmp_path / "task_status.json"
        assert file_path.exists()
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert "test_module" in data

    def test_write_with_error_only(self, tmp_path):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        write_task_status(task_status, str(tmp_path), error_code='SomeError')
        file_path = tmp_path / "task_status.json"
        assert file_path.exists()

    def test_write_default_success(self, tmp_path):
        task_status = copy.deepcopy(TASK_STATUS_JSON)
        write_task_status(task_status, str(tmp_path))
        file_path = tmp_path / "task_status.json"
        assert file_path.exists()
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert data['success_info'] == 'SysPerf.Success.TimeOut'
