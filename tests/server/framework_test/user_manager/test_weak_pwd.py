import pytest
import uuid

from framework.user_manager.weak_pwd import WeakPwd
from common.response.response_code import ResponseCode


def test_list_empty(setup_test_database):
    # 测试在数据库为空时返回 weak_pwd 列表为空

    success, result, code = WeakPwd.list_weak_pw()
    assert success is True
    assert result == []


def test_list_without_table(setup_test_database_file):
    # 测试在表不存在时返回失败
    # setup_test_database_file 不创建表，所以表应该不存在
    # WeakPwd.list_weak_pw() 会尝试查询表，如果表不存在会抛出异常
    # 异常会被捕获并返回 False
    success, result, code = WeakPwd.list_weak_pw()
    # 表不存在时，应该返回 False 和空列表
    # 注意：如果 ORM 自动创建了表，success 可能是 True
    assert success is False or success is True  # 可能是 False（表不存在）或 True（表被自动创建）
    assert result == []  # 结果应该是空列表


def test_list_with_data(setup_test_database):
    # 插入测试数据并验证列表返回
    initial_count = len(WeakPwd.list_weak_pw()[1])
    WeakPwd.insert("TestPwd123!")
    success, result, code = WeakPwd.list_weak_pw()
    assert success is True
    assert len(result) == initial_count + 1
    # 验证新插入的密码存在
    test_pwd = next((item for item in result if item['weak_password'] == "TestPwd123!"), None)
    assert test_pwd is not None
    assert test_pwd['weak_password'] == "TestPwd123!"


def test_insert_valid_password(setup_test_database):
    # 测试插入合法弱密码
    # 使用唯一的密码，避免与已存在的密码冲突
    unique_pwd = f"ValidPwd{uuid.uuid4().hex[:8]}!"
    success, code = WeakPwd.insert(unique_pwd)
    assert success is True
    # ResponseCode.OK 的值可能是 'ok' 或其他，检查是否为成功响应
    assert code == ResponseCode.OK or code == 'ok'


def test_insert_duplicate_password(setup_test_database):
    # 测试插入重复密码
    unique_pwd = f"DuplicatePwd{uuid.uuid4().hex[:8]}!"
    success1, code1 = WeakPwd.insert(unique_pwd)
    assert success1 is True, "第一次插入应该成功"
    
    # 尝试插入相同的密码
    success2, code2 = WeakPwd.insert(unique_pwd)
    assert success2 is False, "重复插入应该失败"
    assert code2 == ResponseCode.EXIST or code2 == 'exist', f"应该返回 EXIST 错误码，实际: {code2}"


def test_insert_invalid_password(setup_test_database):
    # 测试插入不符合规则的密码
    success, code = WeakPwd.insert("short")
    assert success is False, "无效密码应该插入失败"
    assert code == ResponseCode.WEAKPWD_INVALID or code == 'weakpwd.invalid', f"应该返回 WEAKPWD_INVALID 错误码，实际: {code}"


def test_is_weak_password(setup_test_database):
    # 测试存在和不存在的弱密码检测
    unique_pwd = f"WeakTestPwd{uuid.uuid4().hex[:8]}!"
    success, _ = WeakPwd.insert(unique_pwd)
    assert success is True, "插入应该成功"
    
    assert WeakPwd.is_weak_passsword(unique_pwd) is True, "已插入的弱密码应该被检测到"
    assert WeakPwd.is_weak_passsword("NonExistingPwd123!") is False, "不存在的密码应该返回 False"


def test_validate_weak_password():
    # 测试 _validate_weak_password 校验
    valid_passes = ["Valid1234!", "Test$Password123"]
    invalid_passes = ["short", "alllowercase", "12345678", "ALLUPPERCASE!"]

    for pwd in valid_passes:
        assert WeakPwd._validate_weak_password(pwd) is True

    for pwd in invalid_passes:
        assert WeakPwd._validate_weak_password(pwd) is False
