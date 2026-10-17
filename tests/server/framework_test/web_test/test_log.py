import pytest
from flask import session
import json
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.log_manager.operation_constant import OpLogResult, OpLogEvent
from framework.user_manager.user_db import UserManager
from framework_test.public.random_pw import random_pw
from framework_test.web_test.test_checker import get_last_operation_log, flush_and_cleanup, flush_logs

from session_cache import UserSessionCache
from unittest.mock import patch

admin_init_pw = random_pw()
admin_pw = random_pw()
admin_name, normal_name = 'AdminTest', 'pppp1'
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
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': admin_init_pw})
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

    request.addfinalizer(cleanup)


@pytest.fixture(autouse=False)
def client2(app):
    return app.test_client()


@pytest.fixture(scope="function", autouse=False)
def mock_normal_setup(client2, request):
    # db_path = os.path.join(os.path.dirname(__file__), 'user.db')
    status, test1_id = UserManager.save('pppp1', 'normal', admin_init_pw)
    global normal_id, normal_token
    normal_id = test1_id
    with client2:
        response = client2.post('/action/auth/login',
                                json={'username': normal_name, 'password': admin_init_pw})
        token = response.headers.get('X-Csrftoken')
        response = client2.post(
            '/action/auth/modify-password',
            json={'username': normal_name, 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        response = client2.post(
            '/action/auth/login', json={'username': normal_name, 'password': admin_pw})
        token2 = response.headers.get('X-Csrftoken')
        normal_token = token2
    yield

    def cleanup():
        UserManager.delete_user(test1_id)

    # os.remove(db_path)
    request.addfinalizer(cleanup)


def test_list_filter(client, app, mock_admin_setup):
    with client:
        response = client.get('action/logmanager/filter', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert len(rsp.get('data')) == 2
    opr_log = get_last_operation_log(admin_id)
    assert opr_log.get('event') == OpLogEvent.LOGIN


def test_list_log_name(client, app, mock_admin_setup, mock_normal_setup):
    with client:
        response = client.post('action/logmanager/list', json={'filter': {'user_name': 'test'}},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3


def test_list_log_per_page(client, app, mock_admin_setup, mock_normal_setup):
    with client:
        response = client.post('action/logmanager/list', json={'per_page': 10},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 6
        response = client.post('action/logmanager/list', json={'per_page': 2},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 6
        assert len(rsp.get('msg').get('operation_log_list')) == 2


def test_list_log_2filter(client, app, mock_admin_setup, mock_normal_setup):
    with client:
        response = client.post('action/logmanager/list',
                               json={'per_page': 2, 'filter': {'user_name': 'test2'}},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 0

        response = client.post('action/logmanager/list',
                               json={'per_page': 2, 'filter': {'user_name': 'test', 'ip': '127'}},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3


def test_list_log_2filter_2name(client, app, mock_admin_setup, mock_normal_setup):
    with client:
        response = client.post('action/logmanager/list',
                               json={'per_page': 2,
                                     'filter': {'user_name': 'test,pp', 'ip': '127'}},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 6


def test_normal_list_log_name(client2, app, mock_admin_setup, mock_normal_setup):
    with client2:
        response = client2.post('action/logmanager/list', json={'filter': {'user_name': 'test'}},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 0


def test_normal_list_log_per_page(client2, app, mock_admin_setup, mock_normal_setup):
    with client2:
        response = client2.post('action/logmanager/list', json={'per_page': 10},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3
        response = client2.post('action/logmanager/list', json={'per_page': 2},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3
        assert len(rsp.get('msg').get('operation_log_list')) == 2


def test_normal_list_log_2filter(client2, app, mock_admin_setup, mock_normal_setup):
    with client2:
        response = client2.post('action/logmanager/list',
                                json={'per_page': 2, 'filter': {'user_name': 'test2'}},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 0

        response = client2.post('action/logmanager/list',
                                json={'per_page': 2, 'filter': {'user_name': 'pp', 'ip': '127'}},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3


def test_normal_list_log_2filter_2name(client2, app, mock_admin_setup, mock_normal_setup):
    with client2:
        response = client2.post('action/logmanager/list',
                                json={'per_page': 2,
                                      'filter': {'user_name': 'test,pp', 'ip': '127'}},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3


def test_download_log(client, app, mock_normal_setup, mock_admin_setup):
    with client:
        response = client.get('action/logmanager/csv', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        csv_file = rsp.get('data')
        response = client.post('action/logmanager/download', json={'csvfile': csv_file},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = response.data.decode('utf-8').splitlines()
        assert len(rsp) == 7
        log = get_last_operation_log(admin_id)
        assert log.get('event') == OpLogEvent.LOG_DOWNLOAD


def test_normal_download_log(client2, app, mock_normal_setup, mock_admin_setup):
    with client2:
        response = client2.get('action/logmanager/csv', headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        csv_file = rsp.get('data')
        response = client2.post('action/logmanager/download', json={'csvfile': csv_file},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = response.data.decode('utf-8').splitlines()
        assert len(rsp) == 4
        log = get_last_operation_log(normal_id)
        assert log.get('event') == OpLogEvent.LOG_DOWNLOAD


def test_download_log_illegal(client, client2, app, mock_normal_setup, mock_admin_setup):
    with client:
        response = client.get('action/logmanager/csv', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        csv_file = rsp.get('data')
    with client2:
        response = client2.post('action/logmanager/download', json={'csvfile': csv_file},
                                headers={'X-Csrftoken': normal_token})
        assert response.status_code == 200
        rsp = json.loads(response.data.decode('utf-8'))
        assert rsp.get('code') == -1
        log = get_last_operation_log(normal_id)
        assert log.get('event') == OpLogEvent.LOG_DOWNLOAD
        assert log.get('result') == OpLogResult.FAILED


def test_list_log_over(client, app, mock_admin_setup):
    with client:
        response = client.post('action/logmanager/list', json={'per_page': 10},
                               headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert rsp.get('msg').get('total_log_count') == 3
        response = client.get('action/logmanager/csv', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        csv_file = rsp.get('data')
        with patch('framework.log_manager.operation_log.get_max_log_size', return_value=100):
            for i in range(96):
                response = client.post('action/logmanager/download', json={'csvfile': csv_file},
                                       headers={'X-Csrftoken': admin_token})
            # 旧版 record 同步落库后即触发超限清理；WAL 重构后改为后台周期触发，
            # 测试中显式调用以对齐旧行为
            flush_and_cleanup()
            response = client.post('action/logmanager/list', json={'per_page': 10},
                                   headers={'X-Csrftoken': admin_token})
            assert response.status_code == 200
            rsp = json.loads(response.data)
            assert rsp.get('code') == 0
            assert rsp.get('msg').get('total_log_count') == 99
            client.post('action/logmanager/download', json={'csvfile': csv_file},
                        headers={'X-Csrftoken': admin_token})
            # 异步落库：list 前刷盘，保证第 100 条 download 日志可见
            flush_logs()
            response = client.post('action/logmanager/list', json={'per_page': 10},
                                   headers={'X-Csrftoken': admin_token})
            assert response.status_code == 200
            rsp = json.loads(response.data)
            assert rsp.get('code') == 0
            assert rsp.get('msg').get('total_log_count') == 100
            client.post('action/logmanager/download', json={'csvfile': csv_file},
                        headers={'X-Csrftoken': admin_token})
            flush_and_cleanup()
            response = client.post('action/logmanager/list', json={'per_page': 10},
                                   headers={'X-Csrftoken': admin_token})
            assert response.status_code == 200
            rsp = json.loads(response.data)
            assert rsp.get('code') == 0
            assert rsp.get('msg').get('operation_log_list')[0].get('event') == 'Cleanup Log'
            assert rsp.get('msg').get('total_log_count') == 100
