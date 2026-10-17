#!/usr/bin/env python3
"""
AI key 生成工具

生成/复用 data/ 下的三件套密钥文件：
  - serendipity : AES-256 密钥（32B，不存在时随机生成）
  - ethereal    : GCM nonce（12B，不存在时随机生成）
  - luminous    : 加密后的 API key

用法:
    python scripts/create_ai_key.py "<api_key>"
    python scripts/create_ai_key.py
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_PATH = os.path.realpath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, os.path.join(ROOT_PATH, 'server'))


from common import crypto


DEFAULT_AI_KEY = "dyje5p90ch1ji4a4vg8wmlx0p50n5lbd"

DATA_PATH = os.path.join(ROOT_PATH, 'data')
KEY_PATH = os.path.join(DATA_PATH, 'serendipity')
NONCE_PATH = os.path.join(DATA_PATH, 'ethereal')
TARGET_PATH = os.path.join(DATA_PATH, 'luminous')


def init_key():
    """密钥/nonce 文件不存在时生成。"""
    os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(KEY_PATH):
        crypto.generate_key_file(KEY_PATH)
        print(f"generated key file: {KEY_PATH}")
    if not os.path.exists(NONCE_PATH):
        crypto.generate_nonce_file(NONCE_PATH)
        print(f"generated nonce file: {NONCE_PATH}")


def write_ai_key(api_key):
    """加密 api_key 并按对半格式写 luminous。"""
    key = crypto.read_key_file(KEY_PATH)
    nonce = crypto.read_nonce_file(NONCE_PATH)
    data = crypto.aes_gcm_encrypt(key, nonce, api_key.encode('utf-8'))

    ct = data[:-crypto.TAG_SIZE]
    tag = data[-crypto.TAG_SIZE:]
    # 对半格式：ct || tag || 零填充（两段均 key_length 字节）
    padded = ct + tag + b'\x00' * (len(ct) - crypto.TAG_SIZE)
    with open(TARGET_PATH, 'wb') as f:
        f.write(padded)
    print(f"wrote AI key file: {TARGET_PATH}")


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AI_KEY
    if not api_key:
        print('Usage: python scripts/create_ai_key.py "<api_key>"')
        return
    init_key()
    write_ai_key(api_key)


if __name__ == '__main__':
    main()
