import os
import sys
from unittest.mock import patch, MagicMock
import tempfile
import pytest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.response.response_code import ResponseCode
from framework.user_manager import user_manager
from framework.user_manager.user_db import Role, UserManager
from framework.user_manager.weak_pwd import WeakPwd
from framework_test.public.random_pw import random_pw

test_pw = random_pw()
test_pw2 = random_pw()


# 测试 _check_username_legal 方法
@pytest.mark.parametrize("username, exist, expected", [
    ("validUser", None, (True, ResponseCode.OK)),  # 合法用户名
    ("123user", None, (False, ResponseCode.USER_NAME_ILLEGAL)),
    ("", None, (False, ResponseCode.USER_NAME_ILLEGAL)),  # 非法：以数字开头
    ("U>user", None, (False, ResponseCode.USER_NAME_ILLEGAL)),
    ("@invalid", None, (False, ResponseCode.USER_NAME_ILLEGAL)),  # 非法字符
    ("tooloooooooooooooooooooooooooooooooooooooooooooong", None,
     (False, ResponseCode.USER_NAME_LENGTH_OVER)),  # 超长
    ("validUser", [], (False, ResponseCode.USER_NAME_DUPLICATE)),  # 已存在
])
@patch("framework.user_manager.user_db.UserManager.query")
def test_check_username_legal(mock_query, username, exist, expected):
    mock_query.return_value = exist  # 模拟数据库中不存在这个用户名
    assert user_manager._check_username_legal(username) == expected


# 测试 _check_password_legal 方法
@pytest.mark.parametrize("password, username, weak, expected", [
    ("Valid123!", "user", False, (True, ResponseCode.OK)),  # 合法密码
    ("short", "user", False, (False, ResponseCode.USER_PASSWORD_ILLEGAL)),  # 密码短
    (123, "user", False, (False, ResponseCode.USER_PASSWORD_ILLEGAL)),  # 非字符串
    ("Weak1234", "Weak1234", False, (False, ResponseCode.USER_PASSWORD_HASUSERNAME)),  # 内容为用户名
    ("password123", "user", True, (False, ResponseCode.USER_PASSWORD_ILLEGAL)),  # 弱密码
])
@patch("framework.user_manager.weak_pwd.WeakPwd.is_weak_passsword")  # Mock 弱密码检查
def test_check_password_legal(mock_is_weak_password, password, username, weak, expected):
    mock_is_weak_password.return_value = weak
    assert user_manager._check_password_legal(password, username) == expected


@pytest.fixture(scope="function", autouse=False)
def mock_admin_setup(request, setup_user_manager):
    # setup_user_manager 已经初始化了数据库和默认用户
    tester = UserManager.query(user_name='Admin')
    if tester is None:
        # 如果 Admin 用户不存在，创建它
        UserManager.init_default_user()
        tester = UserManager.query(user_name='Admin')

    admin_id = tester.user_id
    request_obj = MagicMock()
    request_obj.user_id = admin_id
    result, user_id = UserManager.save("testAdmin", Role.ADMIN, test_pw)
    # status, error, user_id = user_manager.create(
    #     {"user_name": "testAdmin", "password": test_pw, "role": Role.ADMIN},
    #     op_usr_id=admin_id)
    # status, user_id = User_DB.save('testAdmin', 'admin', test_pw)
    if not result:
        tester = UserManager.query(user_name='testAdmin')
        if tester:
            user_id = tester.user_id
        else:
            user_id = None

    yield

    def cleanup():
        if user_id:
            UserManager.delete_user(user_id)

    request.addfinalizer(cleanup)


@pytest.fixture(scope="function", autouse=False)
def setup_user_manager():
    """设置测试数据库环境并初始化默认用户"""
    # 导入 conftest 中的共享函数
    try:
        from .conftest import setup_test_database_helper
    except ImportError:
        # 如果相对导入失败，使用绝对导入
        import sys
        import os
        conftest_dir = os.path.dirname(os.path.abspath(__file__))
        if conftest_dir not in sys.path:
            sys.path.insert(0, conftest_dir)
        from conftest import setup_test_database_helper

    for context in setup_test_database_helper(create_tables=True, init_default_user=True):
        yield


def test_create_user(setup_user_manager):
    tester = UserManager.query(user_name='Admin')
    params = {"user_name": "newuser", "password": test_pw, "role": Role.NORMAL}
    request = MagicMock()
    request.user_id = 1
    request.remote_addr = '127.0.0.1'
    status, error_list, login_user = user_manager.create(params, request)
    assert status is False
    assert error_list == [ResponseCode.NON_PRIVILEGED]


def test_create_user_ok(setup_user_manager, mock_admin_setup):
    admin = UserManager.query(user_name='testAdmin')
    params = {"user_name": "newuser", "password": test_pw, "role": Role.NORMAL,
              'admin_password': test_pw}

    request = MagicMock()
    request.user_id = admin.user_id
    request.remote_addr = '127.0.0.1'
    status, error_list, login_user = user_manager.create(params, request)
    assert status is True
    assert error_list == []
    assert login_user['user_name'] == "newuser"


def test_create_user_multi_error(setup_user_manager, mock_admin_setup):
    admin = UserManager.query(user_name='testAdmin')
    admin_id = admin.user_id
    params = {"user_name": "newuser", "password": test_pw, "role": Role.NORMAL,
              'admin_password': test_pw}
    request = MagicMock()
    request.user_id = admin.user_id
    request.remote_addr = '127.0.0.1'
    status, error_list, login_user = user_manager.create(params, request)
    assert status is True
    assert error_list == []
    params = {"user_name": "newuser", "password": test_pw, "role": Role.ADMIN,
              'admin_password': test_pw}
    status, error_list, login_user = user_manager.create(params, request)
    assert status is False
    assert error_list == [ResponseCode.USER_NAME_DUPLICATE]
    params = {"user_name": "newu", "password": "Valid", "role": 'test', 'admin_password': test_pw}
    status, error_list, login_user = user_manager.create(params, request)
    assert status is False
    assert error_list == [ResponseCode.USER_NAME_ILLEGAL, ResponseCode.USER_PASSWORD_ILLEGAL,
                          ResponseCode.USER_ROLE_ILLEGAL]


def test_modify_password_no_pri(setup_user_manager, mock_admin_setup):
    params = {"user_name": "Admin", "old_password": test_pw2, "new_password": test_pw}
    request = MagicMock()
    request.user_id = 1
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED
    admin = UserManager.query(user_name='testAdmin')
    request.user_id = admin.user_id

    tester = {"user_name": "tester", "password": test_pw, "role": Role.NORMAL,
              'admin_password': test_pw}
    status, error_list, login_user = user_manager.create(tester, request)
    request.user_id = login_user['user_id']
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED


def test_modify_password_error_pwd(setup_user_manager):
    # 确保 Admin 用户存在
    UserManager.init_default_user()
    admin = UserManager.query(nopw=False, role=Role.ADMIN)
    if admin is None:
        # 如果查询失败，尝试通过 user_name 查询
        admin = UserManager.query(nopw=False, user_name='Admin')
    assert admin is not None, "Admin 用户应该存在"
    admin_id = admin.user_id
    params = {"user_name": "Admin", "old_password": test_pw2, "new_password": test_pw}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_AUTH_FAILED


def test_modify_password_user_not_exist(setup_user_manager):
    admin_id = UserManager.query(nopw=False, role=Role.ADMIN).user_id
    params = {"user_name": "test", "old_password": test_pw2, "new_password": test_pw}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_NOT_EXIST


def test_modify_password_user_illegal_pwd(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": random_pw(3)}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_modify_password_user_conseuitve_char_pwd(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw,
              "new_password": f'{random_pw(6)}aaa'}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.CONSECUTIVE_CHAR_ERROR_CODE


def test_modify_password(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw2}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is True
    assert code == ResponseCode.OK


def test_modify_password_equal(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_NOCHANGE


def test_modify_password_hisory(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw2}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is True
    assert code == ResponseCode.OK
    params = {"user_name": 'testAdmin', "old_password": test_pw2, "new_password": test_pw}
    status, code = user_manager.modify(params, request)
    assert status is True
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw2}
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_HISTORY_PW


def test_modify_password_hisory_max_2(setup_user_manager, mock_admin_setup):
    test_pw3 = random_pw()
    test_pw4 = random_pw()
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw2}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'
    status, code = user_manager.modify(params, request)
    assert status is True
    assert code == ResponseCode.OK
    params = {"user_name": 'testAdmin', "old_password": test_pw2, "new_password": test_pw3}
    status, code = user_manager.modify(params, request)
    assert status is True, f'code is {code}'
    assert code == ResponseCode.OK

    params = {"user_name": 'testAdmin', "old_password": test_pw3, "new_password": test_pw4}
    status, code = user_manager.modify(params, request)
    assert status is True
    params = {"user_name": 'testAdmin', "old_password": test_pw4, "new_password": test_pw}
    status, code = user_manager.modify(params, request)
    assert status is True
    params = {"user_name": 'testAdmin', "old_password": test_pw, "new_password": test_pw4}
    status, code = user_manager.modify(params, request)
    assert status is False
    assert code == ResponseCode.USER_HISTORY_PW


def test_reset_pw(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    tester = {"user_name": "tester", "password": test_pw, "role": Role.NORMAL,
              'admin_password': test_pw}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'  # 设置真实的 IP 地址字符串
    status, error_list, login_user = user_manager.create(tester, request)
    request.user_id = 1
    status, code = user_manager.reset_pw(
        {'user_name': login_user['user_name'], 'admin_password': test_pw, 'new_password': 'Fase'},
        request)
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED

    request.user_id = admin_id
    status, code = user_manager.reset_pw(
        {'user_name': 'xxx', 'admin_password': test_pw, 'new_password': 'Fase'}, request)
    assert status is False
    assert code == ResponseCode.USER_NOT_EXIST
    test_pw2 = random_pw()
    status, code = user_manager.reset_pw(
        {'user_name': login_user['user_name'], 'admin_password': test_pw2, 'new_password': 'Fase'},
        request)
    assert status is False
    assert code == ResponseCode.USER_AUTH_FAILED
    status, code = user_manager.reset_pw(
        {'user_name': login_user['user_name'], 'admin_password': test_pw, 'new_password': ''},
        request)
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL
    status, code = user_manager.reset_pw(
        {'user_name': login_user['user_name'], 'admin_password': test_pw, 'new_password': test_pw2},
        request)
    assert status is True
    assert code == ResponseCode.OK


# 测试 delete_user 功能

def test_delete_user(setup_user_manager, mock_admin_setup):
    admin_id = UserManager.query(nopw=False, user_name='testAdmin').user_id
    tester = {"user_name": "tester", "password": test_pw, "role": Role.NORMAL,
              'admin_password': test_pw}
    request = MagicMock()
    request.user_id = admin_id
    request.remote_addr = '127.0.0.1'  # 设置真实的 IP 地址字符串
    status, error_list, login_user = user_manager.create(tester, request)
    request.user_id = 1
    # login_user 是字典，需要提取 user_id
    user_id_to_delete = login_user['user_id'] if isinstance(login_user, dict) else login_user
    status, code = user_manager.delete_user(user_id_to_delete,
                                            {'admin_password': test_pw, 'delete_task': 'Fase'},
                                            request)
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED
    # status, code = user_manager.delete_user(login_user, {'admin_password':test_pw, 'delete_task':'Fase'},  request)
    # assert status is False
    # assert code == ResponseCode.NON_PRIVILEGED
    # 传递不存在的 user_id 字符串
    request.user_id = admin_id
    status, code = user_manager.delete_user("xx",
                                            {'admin_password': test_pw, 'delete_task': 'Fase'},
                                            request)
    assert status is False
    assert code == ResponseCode.USER_NOT_EXIST
    status, code = user_manager.delete_user(login_user['user_id'],
                                            {'admin_password': test_pw2, 'delete_task': 'Fase'},
                                            request)
    assert status is False
    assert code == ResponseCode.USER_AUTH_FAILED
    status, code = user_manager.delete_user(login_user['user_id'],
                                            {'admin_password': test_pw, 'delete_task': 'Fase'},
                                            request)
    assert status is True
    assert code == ResponseCode.OK


# 测试 list 功能

def test_list_users(setup_user_manager):
    status, code, users = user_manager.list_user(op_usr_id=1)
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED
    assert users == []
    status, code, users = user_manager.list_user()
    assert status is False
    assert code == ResponseCode.NON_PRIVILEGED
    assert users == []
    admin_id = UserManager.query(nopw=False, role=Role.ADMIN).user_id
    status, code, users = user_manager.list_user(op_usr_id=admin_id)
    assert status is True
    assert code == ResponseCode.OK
    assert len(users) == 1
