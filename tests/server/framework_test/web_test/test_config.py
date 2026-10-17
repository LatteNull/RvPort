import pytest
from flask import session
import json
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.log_manager.operation_constant import OpLogResult
from framework.user_manager.user_db import UserManager
from framework_test.public.random_pw import random_pw
from framework_test.web_test.test_checker import get_last_operation_log

from session_cache import UserSessionCache

admin_init_pw = random_pw()
admin_pw = random_pw()
admin_name = 'AdminTest'
admin_id, admin_token = None, None
normal_id, normal_token = None, None


# 用于每个模块执行一次
@pytest.fixture(scope="function", autouse=False)
def mock_admin_setup(client, request):
    # db_path = os.path.join(os.path.dirname(__file__), 'user.db')
    status, user_id = UserManager.save('AdminTest', 'admin', admin_init_pw)
    global admin_id, admin_token
    admin_id = user_id
    with client:
        response = client.post('/action/auth/login', json={'username': admin_name, 'password': admin_init_pw})
        token = response.headers.get('X-Csrftoken')
        response = client.post(
            '/action/auth/modify-password',
            json={'username': admin_name, 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        response = client.post(
            '/action/auth/login', json={'username': admin_name, 'password': admin_pw})
        token2 = response.headers.get('X-Csrftoken')
        admin_token = token2
    yield

    def cleanup():
        UserManager.delete_user(user_id)

    # os.remove(db_path)
    request.addfinalizer(cleanup)


@pytest.fixture(scope="function", autouse=False)
def mock_normal_setup(client, request):
    # db_path = os.path.join(os.path.dirname(__file__), 'user.db')
    status, test1_id = UserManager.save('test1', 'normal', admin_init_pw)
    global normal_id, normal_token
    normal_id = test1_id
    with client:
        response = client.post('/action/auth/login', json={'username': 'test1', 'password': admin_init_pw})
        token = response.headers.get('X-Csrftoken')
        response = client.post(
            '/action/auth/modify-password',
            json={'username': 'test1', 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        response = client.post(
            '/action/auth/login', json={'username': 'test1', 'password': admin_pw})
        token2 = response.headers.get('X-Csrftoken')
        normal_token = token2
    yield

    def cleanup():
        UserManager.delete_user(test1_id)

    # os.remove(db_path)
    request.addfinalizer(cleanup)


def test_list_config(client, app, mock_admin_setup):
    with client:
        response = client.get('action/config', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert len(rsp.get('data')) > 0
    opr_log = get_last_operation_log(admin_id)
    assert opr_log.get('event') != 'Query Config'


def test_normal_user_list_config(client, app, mock_normal_setup):
    with client:
        response = client.get('action/config', headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        # 普通用户能查询，但只返回网络代理相关配置
        assert rsp.get('code') == 0
        keys = set(rsp.get('data', {}).keys())
        assert keys <= {'docker_http_proxy', 'docker_https_proxy', 'docker_no_proxy'}, \
            "普通用户只能看到网络代理相关配置"


def test_set_config(client, app, mock_admin_setup):
    with client:
        response = client.post('action/config',
                               json=[{'key': ConfigKeys.MAX_ONLINE_USERS, 'value': 5}],
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0

        opr_log = get_last_operation_log(admin_id)
        assert 'Modify' in opr_log.get('event')
        # 配置值超范围
        response = client.post('action/config',
                               json=[{'key': ConfigKeys.MAX_ONLINE_USERS, 'value': 21}],
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == -1

        opr_log = get_last_operation_log(admin_id)
        assert 'Modify' in opr_log.get('event')
        assert opr_log.get('result') == OpLogResult.FAILED
        # 配置值未变化
        response = client.post('action/config',
                               json=[{'key': ConfigKeys.MAX_ONLINE_USERS, 'value': 5}],
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == -1
        # 无效的配置字段
        response = client.post('action/config',
                               json=[{'key': 'test', 'value': 5}],
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == -1


def test_normal_user_set_config(client, app, mock_normal_setup):
    with client:
        response = client.post('action/config', json=[{'key': ConfigKeys.MAX_ONLINE_USERS, 'value': 5}],
                               headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == -1
        assert 'data' not in rsp
    opr_log = get_last_operation_log(None)
    assert opr_log.get('event') == 'Batch Modify max online users'
    assert opr_log.get('user_name') == 'test1'
    assert opr_log.get('result') == OpLogResult.FAILED
