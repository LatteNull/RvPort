import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_SIZE = 32    # AES-256
NONCE_SIZE = 12  # GCM IV96
TAG_SIZE = 16    # GCM 认证标签


def generate_key_file(path):
    """生成 32 字节随机 AES-256 密钥并写入文件（覆盖写）。"""
    data = os.urandom(KEY_SIZE)
    with open(path, "wb") as f:
        f.write(data)
    return data


def generate_nonce_file(path):
    """生成 12 字节随机 GCM nonce 并写入文件（覆盖写）。"""
    data = os.urandom(NONCE_SIZE)
    with open(path, "wb") as f:
        f.write(data)
    return data


def read_key_file(path):
    """读取密钥文件，长度非法时抛 ValueError。"""
    with open(path, "rb") as f:
        key = f.read()
    if len(key) != KEY_SIZE:
        raise ValueError(f"key file {path} has invalid size {len(key)}, expected {KEY_SIZE}")
    return key


def read_nonce_file(path):
    """读取 nonce 文件，长度非法时抛 ValueError。"""
    with open(path, "rb") as f:
        nonce = f.read()
    if len(nonce) != NONCE_SIZE:
        raise ValueError(f"nonce file {path} has invalid size {len(nonce)}, expected {NONCE_SIZE}")
    return nonce


def aes_gcm_encrypt(key, nonce, plaintext):
    """AES-256-GCM 加密，返回 ciphertext || tag(16B)（与 C 库格式一致）。

    plaintext 为 bytes/str（str 自动 utf-8 编码）。
    失败抛 InvalidTag/OSError 等异常，由调用方决定处理方式。
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    return AESGCM(key).encrypt(nonce, plaintext, None)


def aes_gcm_decrypt(key, nonce, data):
    """解密 ciphertext || tag(16B) 格式的数据，返回明文 bytes。

    密钥错误/数据被篡改抛 InvalidTag。
    """
    return AESGCM(key).decrypt(nonce, data, None)
