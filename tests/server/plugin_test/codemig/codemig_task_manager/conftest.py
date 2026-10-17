"""
测试配置文件，提供共享的 fixtures 和清理逻辑
"""
import os
import shutil
import pytest
from pathlib import Path

# 获取 MODULE_PATH（与 test_request_processor.py 中的逻辑一致）
MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))


@pytest.fixture(scope="session", autouse=True)
def cleanup_abc_directory():
    """
    在所有测试用例运行前和运行后清理 abc 目录
    
    这个 fixture 会在所有测试用例运行前清理可能存在的 abc 目录，
    并在所有测试用例运行后再次清理，确保测试环境干净。
    """
    abc_path = Path(MODULE_PATH) / 'abc'
    
    # 测试前清理（如果存在）
    if abc_path.exists():
        shutil.rmtree(abc_path, ignore_errors=True)
    
    yield
    
    # 测试后清理（确保即使测试失败也清理）
    if abc_path.exists():
        shutil.rmtree(abc_path, ignore_errors=True)
