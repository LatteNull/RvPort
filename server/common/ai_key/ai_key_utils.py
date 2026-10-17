import os

from common import crypto
from common.public.public import ROOT_PATH


# 自定义 HTTP User-Agent。
# 原因：部分模型网关（如智谱 open.bigmodel.cn 的 ZenZGA）会对 requests 默认的
# `python-requests/x.x` 与空 UA 做差别限流，返回 HTTP 429 + error.code=1305
# 修改前请勿删除——否则 _test_openai_api_key / 推理流式请求会复现 1305。
DEFAULT_AI_HTTP_UA = "OpenAI/Python 1.30.0"


# 模型别名 → 模型名映射（供请求体的 "model" 字段使用）。
# 不内置任何推理服务端点：URL 一律来自用户在页面「API Key 管理」中配置的
# Base URL（未配置时推理请求直接报错引导配置，不再兜底默认地址）。
MODELS = {
    "Qwen3":            {"MODEL": "Qwen3-235B-A22B"},
    "DeepSeek":         {"MODEL": "DeepSeek-V3"},
    "DeepSeek-V3":      {"MODEL": "DeepSeek-V3"},
    "Kimi-K2-Instruct": {"MODEL": "Kimi-K2-Instruct"},
}

class AIKey():
    API_KEY = None
    @classmethod
    def get_api_key(cls):
        return cls.API_KEY

    @classmethod
    def update_api_key(cls, key):
        cls.API_KEY = key


def get_ai_url(model_name):
    """获取指定模型的推理 URL。

    已不内置默认端点：推理 URL 必须由用户配置（页面「API Key 管理」的 Base URL）。
    保留本函数以统一"未配置即报错"的语义，model_name 仅用于错误提示。
    """
    raise ValueError(
        f"未配置推理服务地址(Base URL)，请先在「API Key 管理」中配置 {model_name} 的 API Key"
        if model_name in MODELS else f"Unknown model: {model_name}"
    )


def get_model(model_name):
    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name}")
    return MODELS[model_name]["MODEL"]


def load_ai_magic_values():
    data_path = os.path.join(ROOT_PATH, 'data')

    key_path = os.path.join(data_path, "serendipity")
    nonce_path = os.path.join(data_path, "ethereal")
    target_path = os.path.join(data_path, "luminous")
    help_message = 'Please run: python scripts/create_ai_key.py "<api_key>"'
    if not (os.path.exists(target_path) and os.path.exists(nonce_path) and
            os.path.exists(key_path)):
        raise Exception("Could not find AI key files. " + help_message)
    with open(target_path, "rb") as file:
        read_data = file.read()
    if not read_data:
        raise Exception("The AI key file is empty. " + help_message)
    key_length = len(read_data) // 2
    ciphertext = read_data[:key_length]
    tag = read_data[key_length:key_length + 16]

    try:
        key = crypto.read_key_file(key_path)
        nonce = crypto.read_nonce_file(nonce_path)
        plaintext = crypto.aes_gcm_decrypt(key, nonce, ciphertext + tag)
    except (OSError, ValueError, Exception):
        raise Exception("Password decryption failed. " + help_message)
    plaintext = plaintext.decode()
    result = plaintext.split('|')
    AIKey.update_api_key(result[0])

