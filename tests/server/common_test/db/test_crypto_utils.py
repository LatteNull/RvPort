import os
import pytest
from unittest.mock import MagicMock, patch

from common.db.crypto_utils import get_key, KEY_FILE, NONCE_FILE, TARGET_FILE
from common import crypto


def _write_key_files(config_path, plaintext=b"my-secret-password"):
    """在目录下生成一套合法密钥文件（真实 AESGCM 加密），返回密文原文。"""
    key = crypto.generate_key_file(config_path / KEY_FILE)
    nonce = crypto.generate_nonce_file(config_path / NONCE_FILE)
    data = crypto.aes_gcm_encrypt(key, nonce, plaintext)
    (config_path / TARGET_FILE).write_bytes(data)
    return data


class TestGetKey:
    """测试 get_key 函数"""

    def test_returns_none_when_files_missing(self, tmp_path):
        config_path = str(tmp_path / "config")
        result = get_key(path=config_path)
        assert result is None

    def test_returns_none_when_target_file_missing(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        (config_path / KEY_FILE).write_bytes(b"\x00" * 32)
        (config_path / NONCE_FILE).write_bytes(b"\x00" * 12)
        result = get_key(path=str(config_path))
        assert result is None

    def test_returns_none_when_key_file_missing(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        (config_path / NONCE_FILE).write_bytes(b"\x00" * 12)
        (config_path / TARGET_FILE).write_bytes(b"target")
        result = get_key(path=str(config_path))
        assert result is None

    def test_returns_none_when_nonce_file_missing(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        (config_path / KEY_FILE).write_bytes(b"\x00" * 32)
        (config_path / TARGET_FILE).write_bytes(b"target")
        result = get_key(path=str(config_path))
        assert result is None

    def test_returns_cached_key_from_db_info(self):
        mock_db_info = MagicMock()
        mock_db_info.key = "cached-password"
        result = get_key(db_info=mock_db_info)
        assert result == "cached-password"

    def test_decrypt_success_and_cache(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        _write_key_files(config_path, b"my-secret-password")

        mock_db_info = MagicMock()
        mock_db_info.key = None
        result = get_key(db_info=mock_db_info, path=str(config_path))
        assert result == "my-secret-password"
        mock_db_info.update_key.assert_called_once_with("my-secret-password")

    def test_decrypt_failure_returns_none(self, tmp_path):
        """密钥与密文不匹配（InvalidTag）→ None"""
        config_path = tmp_path / "config"
        config_path.mkdir()
        _write_key_files(config_path, b"my-secret-password")
        # 换一把随机密钥，解密必然认证失败
        crypto.generate_key_file(config_path / KEY_FILE)

        result = get_key(path=str(config_path))
        assert result is None

    def test_invalid_key_size_returns_none(self, tmp_path):
        """密钥文件长度非法（ValueError）→ None"""
        config_path = tmp_path / "config"
        config_path.mkdir()
        _write_key_files(config_path, b"another-password")
        (config_path / KEY_FILE).write_bytes(b"short-key")

        result = get_key(path=str(config_path))
        assert result is None

    def test_no_db_info_no_cache(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        _write_key_files(config_path, b"another-password")

        result = get_key(path=str(config_path))
        assert result == "another-password"

    def test_empty_target_file(self, tmp_path):
        config_path = tmp_path / "config"
        config_path.mkdir()
        (config_path / KEY_FILE).write_bytes(b"\x00" * 32)
        (config_path / NONCE_FILE).write_bytes(b"\x00" * 12)
        (config_path / TARGET_FILE).write_bytes(b"")

        result = get_key(path=str(config_path))
        assert result is None

    def test_roundtrip_with_generated_files(self, tmp_path):
        """生成的密钥文件 + 加密写回 → get_key 解出原文（端到端 roundtrip）"""
        config_path = tmp_path / "config"
        config_path.mkdir()
        _write_key_files(config_path, b"p@ssw0rd-16ch")
        assert get_key(path=str(config_path)) == "p@ssw0rd-16ch"
