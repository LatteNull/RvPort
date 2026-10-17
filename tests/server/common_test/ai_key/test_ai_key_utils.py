import os
import pytest
from unittest.mock import patch

from common.ai_key.ai_key_utils import (
    AIKey, MODELS, get_ai_url, get_model, load_ai_magic_values
)


class TestAIKey:
    """测试 AIKey 类"""

    def setup_method(self):
        AIKey.API_KEY = None

    def test_initial_api_key_is_none(self):
        assert AIKey.get_api_key() is None

    def test_update_api_key(self):
        AIKey.update_api_key("test-key-123")
        assert AIKey.get_api_key() == "test-key-123"

    def test_update_api_key_overwrite(self):
        AIKey.update_api_key("key1")
        AIKey.update_api_key("key2")
        assert AIKey.get_api_key() == "key2"

    def test_update_api_key_empty_string(self):
        AIKey.update_api_key("")
        assert AIKey.get_api_key() == ""

    def test_update_api_key_none(self):
        AIKey.update_api_key(None)
        assert AIKey.get_api_key() is None


class TestGetAIUrl:
    """测试 get_ai_url 函数（已不内置默认端点，统一报错引导配置）"""

    def test_known_model_raises_config_error(self):
        # 已知模型：不再返回内置 URL，而是报"未配置 Base URL"引导配置
        for model_name in MODELS:
            with pytest.raises(ValueError, match="未配置推理服务地址"):
                get_ai_url(model_name)

    def test_unknown_model_raises_error(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_ai_url("NonExistentModel")

    def test_empty_model_raises_error(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_ai_url("")

    def test_models_have_no_builtin_url(self):
        # 确保模型表不再携带任何内置端点（防回归）
        for model_name in MODELS:
            assert "URL" not in MODELS[model_name], f"{model_name} 不应再内置 URL"


class TestGetModel:
    """测试 get_model 函数"""

    def test_get_qwen3_model(self):
        model = get_model("Qwen3")
        assert model == "Qwen3-235B-A22B"

    def test_get_deepseek_model(self):
        model = get_model("DeepSeek")
        assert model == "DeepSeek-V3"

    def test_get_deepseek_v3_model(self):
        model = get_model("DeepSeek-V3")
        assert model == "DeepSeek-V3"

    def test_get_kimi_model(self):
        model = get_model("Kimi-K2-Instruct")
        assert model == "Kimi-K2-Instruct"

    def test_unknown_model_raises_error(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("NonExistentModel")

    def test_all_models_have_model_name(self):
        for model_name in MODELS:
            model = get_model(model_name)
            assert isinstance(model, str)
            assert len(model) > 0


class TestLoadAIMagicValues:
    """测试 load_ai_magic_values 函数（真实 AESGCM + luminous 对半格式）"""

    def _make_key_files(self, tmp_path, api_key="sk-test-api-key-123"):
        """生成 serendipity/ethereal/luminous 三件套（对半格式），返回 (key, nonce, raw)"""
        from common import crypto
        data_path = tmp_path / "data"
        data_path.mkdir(exist_ok=True)
        key = crypto.generate_key_file(data_path / "serendipity")
        nonce = crypto.generate_nonce_file(data_path / "ethereal")
        data = crypto.aes_gcm_encrypt(key, nonce, api_key.encode())
        ct, tag = data[:-16], data[-16:]
        # 对半格式：ct || tag || 零填充（两段均 len(ct) 字节）
        padded = ct + tag + b'\x00' * (len(ct) - 16)
        (data_path / "luminous").write_bytes(padded)
        return key, nonce, padded

    def test_missing_key_files_raises_exception(self, tmp_path):
        data_path = str(tmp_path / "data")
        os.makedirs(data_path, exist_ok=True)

        with patch('common.ai_key.ai_key_utils.ROOT_PATH', str(tmp_path)):
            with pytest.raises(Exception, match="Could not find AI key files"):
                load_ai_magic_values()

    def test_empty_target_file_raises(self, tmp_path):
        data_path = tmp_path / "data"
        data_path.mkdir()
        (data_path / "serendipity").write_bytes(b"\x00" * 32)
        (data_path / "ethereal").write_bytes(b"\x00" * 12)
        (data_path / "luminous").write_bytes(b"")

        with patch('common.ai_key.ai_key_utils.ROOT_PATH', str(tmp_path)):
            with pytest.raises(Exception, match="The AI key file is empty"):
                load_ai_magic_values()

    def test_wrong_key_raises_decrypt_failed(self, tmp_path):
        """密钥不匹配 → InvalidTag → Password decryption failed"""
        self._make_key_files(tmp_path)
        from common import crypto
        data_path = tmp_path / "data"
        crypto.generate_key_file(data_path / "serendipity")

        with patch('common.ai_key.ai_key_utils.ROOT_PATH', str(tmp_path)):
            with pytest.raises(Exception, match="Password decryption failed"):
                load_ai_magic_values()

    def test_successful_load(self, tmp_path):
        self._make_key_files(tmp_path, "sk-test-api-key-123")

        with patch('common.ai_key.ai_key_utils.ROOT_PATH', str(tmp_path)):
            AIKey.API_KEY = None
            load_ai_magic_values()
            assert AIKey.get_api_key() is not None
            assert "sk-test-api-key-123" in AIKey.get_api_key()

    def test_successful_load_with_pipe_suffix(self, tmp_path):
        """明文含 | 分隔符时取第一段为 api key（历史 C 端行为）"""
        self._make_key_files(tmp_path, "sk-piped-key|extra|fields")

        with patch('common.ai_key.ai_key_utils.ROOT_PATH', str(tmp_path)):
            AIKey.API_KEY = None
            load_ai_magic_values()
            assert AIKey.get_api_key() == "sk-piped-key"
