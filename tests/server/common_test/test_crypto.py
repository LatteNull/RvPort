import os
import pytest
from cryptography.exceptions import InvalidTag

from common import crypto


class TestGenerateFiles:
    def test_generate_key_file(self, tmp_path):
        path = tmp_path / "key"
        data = crypto.generate_key_file(path)
        assert len(data) == crypto.KEY_SIZE == 32
        assert path.read_bytes() == data

    def test_generate_nonce_file(self, tmp_path):
        path = tmp_path / "nonce"
        data = crypto.generate_nonce_file(path)
        assert len(data) == crypto.NONCE_SIZE == 12
        assert path.read_bytes() == data

    def test_generate_overwrites(self, tmp_path):
        path = tmp_path / "key"
        path.write_bytes(b"\x00" * 32)
        crypto.generate_key_file(path)
        assert path.read_bytes() != b"\x00" * 32  # 覆盖写


class TestReadFiles:
    def test_read_key_file(self, tmp_path):
        path = tmp_path / "key"
        crypto.generate_key_file(path)
        assert crypto.read_key_file(path) == path.read_bytes()

    def test_read_nonce_file(self, tmp_path):
        path = tmp_path / "nonce"
        crypto.generate_nonce_file(path)
        assert crypto.read_nonce_file(path) == path.read_bytes()

    def test_read_key_wrong_size_raises(self, tmp_path):
        path = tmp_path / "key"
        path.write_bytes(b"short")
        with pytest.raises(ValueError, match="invalid size"):
            crypto.read_key_file(path)

    def test_read_nonce_wrong_size_raises(self, tmp_path):
        path = tmp_path / "nonce"
        path.write_bytes(b"short")
        with pytest.raises(ValueError, match="invalid size"):
            crypto.read_nonce_file(path)

    def test_read_missing_file_raises(self, tmp_path):
        with pytest.raises(OSError):
            crypto.read_key_file(tmp_path / "nonexistent")


class TestEncryptDecrypt:
    def test_roundtrip_bytes(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        plaintext = b"hello aes-256-gcm"
        cipher = crypto.aes_gcm_encrypt(key, nonce, plaintext)
        assert cipher == crypto.aes_gcm_encrypt(key, nonce, plaintext)  # 确定性
        assert crypto.aes_gcm_decrypt(key, nonce, cipher) == plaintext

    def test_roundtrip_str_automatic_utf8(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = crypto.aes_gcm_encrypt(key, nonce, "密码测试✓")
        assert crypto.aes_gcm_decrypt(key, nonce, cipher) == "密码测试✓".encode()

    def test_ciphertext_layout_ct_then_tag(self):
        """密文格式必须与 C 库一致：ciphertext || tag(16B)"""
        key = os.urandom(32)
        nonce = os.urandom(12)
        plaintext = b"0123456789abcdef"  # 16B，与 tag 等长便于验证
        cipher = crypto.aes_gcm_encrypt(key, nonce, plaintext)
        assert len(cipher) == len(plaintext) + crypto.TAG_SIZE
        ct, tag = cipher[:-16], cipher[-16:]
        assert ct != plaintext  # GCM 加密后密文不等于明文
        assert len(tag) == 16

    def test_empty_plaintext_roundtrip(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = crypto.aes_gcm_encrypt(key, nonce, b"")
        assert len(cipher) == 16  # 仅 tag
        assert crypto.aes_gcm_decrypt(key, nonce, cipher) == b""

    def test_tampered_ciphertext_raises_invalid_tag(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = bytearray(crypto.aes_gcm_encrypt(key, nonce, b"payload"))
        cipher[0] ^= 0xFF
        with pytest.raises(InvalidTag):
            crypto.aes_gcm_decrypt(key, nonce, bytes(cipher))

    def test_tampered_tag_raises_invalid_tag(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = bytearray(crypto.aes_gcm_encrypt(key, nonce, b"payload"))
        cipher[-1] ^= 0x01
        with pytest.raises(InvalidTag):
            crypto.aes_gcm_decrypt(key, nonce, bytes(cipher))

    def test_wrong_key_raises_invalid_tag(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = crypto.aes_gcm_encrypt(key, nonce, b"payload")
        with pytest.raises(InvalidTag):
            crypto.aes_gcm_decrypt(os.urandom(32), nonce, cipher)

    def test_wrong_nonce_raises_invalid_tag(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        cipher = crypto.aes_gcm_encrypt(key, nonce, b"payload")
        with pytest.raises(InvalidTag):
            crypto.aes_gcm_decrypt(key, os.urandom(12), cipher)

    def test_invalid_key_size_raises(self):
        with pytest.raises(ValueError):
            crypto.aes_gcm_encrypt(b"short-key", os.urandom(12), b"x")

    def test_nonce_size_not_enforced_by_aesgcm(self):
        """cryptography 的 AESGCM 接受 8/16B 等非标准 nonce（GHASH 兼容）；
        项目内统一经 read_nonce_file 校验 12B，这里只记录该库行为。"""
        key = os.urandom(32)
        cipher = crypto.aes_gcm_encrypt(key, os.urandom(16), b"x")
        assert len(cipher) == len(b"x") + crypto.TAG_SIZE
