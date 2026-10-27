"""冻结事实文件的原始字节合同，不静默修复输入。"""

import hashlib
import json
from pathlib import Path


def validate_fact_file(path, expected, manifest_sha):
    """核对 LF 字节、内容形状和 manifest，返回已验证的事实数据。"""
    path = Path(path)

    def fail(reason):
        raise ValueError(f"{path}: {reason}")

    try:
        raw = path.read_bytes()
    except OSError as error:
        fail(f"无法读取事实文件: {error}")
    if b"\r" in raw:
        fail("事实文件含 CR/CRLF；请核对 Git blob 和 LF 检出属性")
    if len(raw) != expected["bytes"]:
        fail(f"字节数不一致: expected={expected['bytes']}, actual={len(raw)}")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected["sha256"]:
        fail(f"SHA-256 不一致: expected={expected['sha256']}, actual={digest}")
    if digest != manifest_sha:
        fail("knowledge-manifest SHA-256 与事实文件不一致")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        fail(f"事实 JSON 无效: {error}")
    if not isinstance(data, dict):
        fail("事实 JSON 必须是对象")
    if data.get("source") != expected["source"]:
        fail("事实来源元数据不一致")
    for category, count in expected["counts"].items():
        values = data.get(category)
        if not isinstance(values, list) or len(values) != count:
            fail(f"事实分类计数或类型不一致: {category}")
    return data
