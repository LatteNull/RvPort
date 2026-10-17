"""
加密工具模块
用于处理数据库密钥的解密
"""
import os

from common import crypto
from common.public.public import ROOT_PATH

KEY_FILE = "himalayan"
NONCE_FILE = "qomolangma"
TARGET_FILE = "8848"
config_path = os.path.join(ROOT_PATH, "data", "config")


def get_key(db_info=None, path=None):
    """
    获取解密后的数据库密钥

    Args:
        db_info: DBInfo 实例，用于缓存密钥。如果为 None，则不使用缓存。

    Returns:
        str: 解密后的密钥，如果解密失败则返回 None
    """
    # 如果提供了 db_info 且已缓存密钥，直接返回
    if db_info is not None and db_info.key is not None:
        return db_info.key

    if path is None:
        path = config_path

    target = os.path.join(path, TARGET_FILE)
    nonce_path = os.path.join(path, NONCE_FILE)
    key_path = os.path.join(path, KEY_FILE)

    # 检查必要的文件是否存在
    if not (os.path.exists(target) and os.path.exists(nonce_path) and os.path.exists(key_path)):
        return None

    try:
        # 读取加密数据（格式：ciphertext || tag(16B)）
        with open(target, "rb") as file:
            read_data = file.read()

        if not read_data:
            return None

        key = crypto.read_key_file(key_path)
        nonce = crypto.read_nonce_file(nonce_path)
        plaintext = crypto.aes_gcm_decrypt(key, nonce, read_data)
    except (OSError, ValueError):
        # 文件读写失败 / 密钥尺寸非法
        return None
    except Exception:
        # InvalidTag 等解密失败（密钥错误或数据被篡改）
        return None

    plaintext = plaintext.decode()

    # 如果提供了 db_info，缓存密钥
    if db_info is not None:
        db_info.update_key(plaintext)

    return plaintext
