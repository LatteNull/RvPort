from time import sleep

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

import pytest
from flask import session
import json
from common.response.response_code import ResponseCode
from common.response.code2string import getI18n
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.log_manager.operation_constant import OpLogResult
from framework.user_manager.user_db import UserManager, encrypt_password
from framework_test.public.random_pw import random_pw
from framework_test.web_test.test_checker import get_last_operation_log
from session_cache import UserSessionCache

admin_init_pw = random_pw()
admin_pw = random_pw()
admin_name = 'AdminTest'
admin_id = None


# 用于每个模块执行一次
@pytest.fixture(scope="function", autouse=False)
def mock_admin_setup(request):
    # db_path = os.path.join(os.path.dirname(__file__), 'user.db')
    status, user_id = UserManager.save('AdminTest', 'admin', admin_init_pw)
    global admin_id
    admin_id = user_id

    yield

    def cleanup():
        UserManager.delete_user(user_id)

    # os.remove(db_path)
    request.addfinalizer(cleanup)


@pytest.fixture(scope="function", autouse=False)
def mock_super_setup(request):
    user = UserManager.query(user_name='Admin')
    status = UserManager.update(user.user_id, is_first_login=0, password=encrypt_password(admin_init_pw))

    yield user.user_id

    def cleanup():
        UserManager.delete_user(user.user_id)

    # os.remove(db_path)
    request.addfinalizer(cleanup)


def test_login(client, app, mock_admin_setup):
    with client:
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 2
        assert session['user_name'] == admin_name
        assert session['user_id'] is not None
        assert session['logged_in'] is False
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        assert admin_id in UserSessionCache._cache
        assert UserSessionCache.get_user_last_time(admin_id) is not None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert 'first login' in opr_log.get('detail')
        response = client.post(
            '/action/auth/modify-password',
            json={'username': admin_name, 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token = response.headers.get('X-Csrftoken')
        assert token is None
        assert 'user_name' not in session
        assert UserSessionCache.get_user_last_time(admin_id) is None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert opr_log.get('event') == 'Modify Password'
        response = client.post(
            '/action/auth/login', json={'username': admin_name, 'password': admin_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token2 = response.headers.get('X-Csrftoken')
        assert token2 is not None
        assert token2 != token
        assert session['user_name'] == admin_name
        assert session['user_id'] is not None
        assert session['logged_in'] is True
        assert UserSessionCache.get_user_last_time(admin_id) is not None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert opr_log.get('event') == 'Login'


def test_login_pw_error(client, app, mock_admin_setup):
    with client:
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        rsp = json.loads(response.data)
        assert rsp.get('code') == 1
        assert 'user_id' not in session
        assert 'logged_in' not in session
        token = response.headers.get('X-Csrftoken')
        assert token is None
        assert admin_id not in UserSessionCache._cache
        assert UserSessionCache.get_user_last_time(admin_id) is None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.FAILED
        assert getI18n(ResponseCode.USER_AUTH_FAILED) == opr_log.get('detail')
        response = client.post(
            '/action/auth/modify-password',
            json={'username': admin_name, 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        assert response.status_code == 401
        token = response.headers.get('X-Csrftoken')
        assert token is None
        assert 'user_name' not in session
        assert UserSessionCache.get_user_last_time(admin_id) is None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.FAILED
        assert opr_log.get('event') == 'Login'
        response = client.post(
            '/action/auth/login', json={'username': admin_name, 'password': admin_init_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 2
        token2 = response.headers.get('X-Csrftoken')
        assert token2 is not None
        assert token2 != token
        assert session['user_name'] == admin_name
        assert session['user_id'] is not None
        assert session['logged_in'] is False
        assert UserSessionCache.get_user_last_time(admin_id) is not None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert opr_log.get('event') == 'Login'


def test_login_max_online(client, app, mock_admin_setup):
    client2 = app.test_client()
    SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '1')
    status, test1_id = UserManager.save('test1', 'admin', admin_init_pw)
    status, test2_id = UserManager.save('test2', 'admin', admin_init_pw)
    with client:
        response = client.post('/action/auth/login',
                               json={'username': 'test1', 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 2
        assert session['user_name'] == 'test1'
        assert session['user_id'] is not None
        assert session['logged_in'] is False
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        assert test1_id in UserSessionCache._cache
        assert UserSessionCache.get_user_last_time(test1_id) is not None
    with client2:
        response = client2.post('/action/auth/login',
                                json={'username': 'test2', 'password': admin_init_pw})
        assert response.status_code == 400
        rsp = json.loads(response.data)
        assert rsp.get('code') == 1
        assert getI18n(ResponseCode.USER_OVER_MAX_ONLINE, 'zh') == rsp.get('msg')
        assert 'user_name' not in session
        assert 'user_id' not in session
        assert 'logged_in' not in session
        token = response.headers.get('X-Csrftoken')
        assert token is None
        assert test2_id not in UserSessionCache._cache
        assert UserSessionCache.get_user_last_time(test2_id) is None
    SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '2')
    with client2:
        response = client2.post('/action/auth/login',
                                json={'username': 'test2', 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 2
        assert session['user_id'] is not None
        assert session['logged_in'] is False
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        assert test2_id in UserSessionCache._cache
        assert UserSessionCache.get_user_last_time(test2_id) is not None

    client3 = app.test_client()
    SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '1')
    status, test3_id = UserManager.save('test3', 'admin', admin_init_pw)
    assert test1_id in UserSessionCache._cache
    assert test2_id in UserSessionCache._cache

    with client3:
        response = client3.post('/action/auth/login',
                                json={'username': 'test3', 'password': admin_init_pw})
        assert response.status_code == 400
        rsp = json.loads(response.data)
        assert rsp.get('code') == 1
    assert test1_id in UserSessionCache._cache
    assert test2_id in UserSessionCache._cache
    assert test3_id not in UserSessionCache._cache


def test_login_max_online_super(client, app, mock_admin_setup, mock_super_setup):
    client2 = app.test_client()
    client3 = app.test_client()
    SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '1')
    status, test1_id = UserManager.save('test1', 'admin', admin_init_pw)
    status, test2_id = UserManager.save('test2', 'admin', admin_init_pw)
    with client:
        response = client.post('/action/auth/login',
                               json={'username': 'Admin', 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        token = response.headers.get('X-Csrftoken')
        assert rsp.get('code') == 0

        assert UserSessionCache.get_user_last_time(mock_super_setup) is not None
        with client2:
            response = client2.post('/action/auth/login',
                                    json={'username': 'test1', 'password': admin_init_pw})
            assert response.status_code == 200
            rsp = json.loads(response.data)
            assert rsp.get('code') == 2
            assert UserSessionCache.get_user_last_time(test1_id) is not None
        with client3:
            response = client3.post('/action/auth/login',
                                    json={'username': 'test2', 'password': admin_init_pw})
            assert response.status_code == 400
            rsp = json.loads(response.data)
            assert rsp.get('code') == 1
            assert UserSessionCache.get_user_last_time(test2_id) is None
        response = client.post('/action/auth/logout', headers={'X-Csrftoken': token})
        assert UserSessionCache.get_user_last_time(mock_super_setup) is None
        response = client.post('/action/auth/login',
                               json={'username': 'Admin', 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0


def test_login_lock(client, app, mock_admin_setup):
    client.environ_base.update({
        'HTTP_X_FORWARDED_FOR': '2.2.2.2',
        'HTTP_X_REAL_IP': '2.2.2.2',
        'REMOTE_ADDR': '2.2.2.2'
    })

    with client:
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        client.environ_base.update({
            'HTTP_X_FORWARDED_FOR': '3.3.3.3',
            'HTTP_X_REAL_IP': '3.3.3.3',
            'REMOTE_ADDR': '3.3.3.3'
        })
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert getI18n(ResponseCode.USER_AUTH_FAILED, 'zh') == data.get('msg')
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': 'xxx'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert ResponseCode.USER_LOCKED == data.get('msg')
        response = client.post('/action/auth/login',
                               json={'username': 'notexist', 'password': 'xxx'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert getI18n(ResponseCode.USER_AUTH_FAILED, 'zh') == data.get('msg')
        response = client.post('/action/auth/login',
                               json={'username': 'notexist', 'password': 'xxx'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert getI18n(ResponseCode.USER_AUTH_FAILED, 'zh') == data.get('msg')
        response = client.post('/action/auth/login',
                               json={'username': 'notexist', 'password': 'xxx'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert getI18n(ResponseCode.IP_LOCKED, 'zh') == data.get('msg')
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': admin_init_pw})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert getI18n(ResponseCode.IP_LOCKED, 'zh') == data.get('msg')
    current_time = datetime.now()
    release_time = current_time + timedelta(minutes=3, seconds=1)
    with patch('time.time') as mock_time:
        mock_time.return_value = release_time.timestamp()
        with client:
            client.environ_base.update({
                'HTTP_X_FORWARDED_FOR': '2.2.2.2',
                'HTTP_X_REAL_IP': '2.2.2.2',
                'REMOTE_ADDR': '2.2.2.2'
            })
            response = client.post('/action/auth/login',
                                   json={'username': admin_name, 'password': 'xxx'})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert getI18n(ResponseCode.USER_AUTH_FAILED, 'zh') == data.get('msg')
            response = client.post('/action/auth/login',
                                   json={'username': admin_name, 'password': admin_init_pw})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert getI18n(ResponseCode.USER_FIRST_LOGIN, 'zh') == data.get('msg')
            client.environ_base.update({
                'HTTP_X_FORWARDED_FOR': '3.3.3.3',
                'HTTP_X_REAL_IP': '3.3.3.3',
                'REMOTE_ADDR': '3.3.3.3'
            })
            response = client.post('/action/auth/login',
                                   json={'username': admin_name, 'password': admin_init_pw})
            assert response.status_code == 400
            data = json.loads(response.data)
            assert getI18n(ResponseCode.IP_LOCKED, 'zh') == data.get('msg')
            release_time = current_time + timedelta(hours=2, seconds=1)
            mock_time.return_value = release_time.timestamp()
            response = client.post('/action/auth/login',
                                   json={'username': admin_name, 'password': admin_init_pw})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert getI18n(ResponseCode.USER_FIRST_LOGIN, 'zh') == data.get('msg')


def test_login_info(client, app, mock_admin_setup):
    with client:
        response = client.post('/action/auth/login',
                               json={'username': admin_name, 'password': admin_init_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 2
        assert session['user_name'] == admin_name
        assert session['user_id'] is not None
        assert session['logged_in'] is False
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        assert admin_id in UserSessionCache._cache
        last_time1 = UserSessionCache.get_user_last_time(admin_id)
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert 'first login' in opr_log.get('detail')
        response = client.post(
            '/action/auth/modify-password',
            json={'username': admin_name, 'old_password': admin_init_pw, 'new_password': admin_pw},
            headers={'X-Csrftoken': token})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token = response.headers.get('X-Csrftoken')
        assert token is None
        assert 'user_name' not in session
        last_time2 = UserSessionCache.get_user_last_time(admin_id)
        assert last_time2 is None
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert opr_log.get('event') == 'Modify Password'
        response = client.post(
            '/action/auth/login', json={'username': admin_name, 'password': admin_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token2 = response.headers.get('X-Csrftoken')
        assert token2 is not None
        assert token2 != token
        assert session['user_name'] == admin_name
        assert session['user_id'] is not None
        assert session['logged_in'] is True
        last_time3 = UserSessionCache.get_user_last_time(admin_id)
        opr_log = get_last_operation_log(admin_id)
        assert opr_log.get('result') == OpLogResult.SUCCESS
        assert opr_log.get('event') == 'Login'
        sleep(1)
        response = client.post('/action/auth/logout', headers={'X-Csrftoken': token2})
        response = client.post(
            '/action/auth/login', json={'username': admin_name, 'password': admin_pw})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert json.loads(rsp.get('msg')).get('last_login_duration') > 0
