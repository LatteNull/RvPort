import json
import os
import sys

import pytest
from flask import Flask, session
from unittest.mock import patch as mock_patch, MagicMock


MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.response.code2string import getI18n
from common.db.SQLOperation import DB_INFO
from common.response.response_code import ResponseCode
from framework.user_manager.user_db import UserManager, Role
from framework.user_manager.views import (
    auth_bp, user_bp, insert_session, clear_session, generic_login
)
from framework_test.public.random_pw import random_pw

test_pw2 = random_pw()
test_pw = random_pw()


# 用于每个模块执行一次
@pytest.fixture(scope="function", autouse=False)
def mock_db_setup(request):
    # 创建测试用户
    status, user_id = UserManager.save('tester', Role.NORMAL, test_pw)
    if not status:
        # 如果用户已存在，先删除再创建
        tester = UserManager.query(user_name='tester')
        if tester:
            user_id = tester.user_id
            UserManager.delete_user(user_id)
            status, user_id = UserManager.save('tester', Role.NORMAL, test_pw)
        else:
            user_id = None

    yield

    def cleanup():
        if user_id:
            UserManager.delete_user(user_id)

    request.addfinalizer(cleanup)


def test_login(client, app, mock_db_setup):
    with client:
        response = client.post('/action/auth/login',
                               json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 2
        assert session['user_name'] == 'tester'
        assert session['user_id'] is not None
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        response = client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token = response.headers.get('X-Csrftoken')
        assert token is None
        response = client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token2 = response.headers.get('X-Csrftoken')
        assert token2 is not None
        assert token2 != token


def test_login_error(client, app, mock_db_setup):
    with client:
        response = client.post('/action/auth/login',
                               json={'username': 'tester2', 'password': test_pw})
        assert response.status_code == 400
        assert json.loads(response.data).get('code') == 1
        assert json.loads(response.data).get('msg') == getI18n(ResponseCode.USER_AUTH_FAILED, 'zh')
        response = client.post(
            '/action/auth/login', json={'username': 'tester', 'password': 'wrong'})
        assert response.status_code == 400
        assert json.loads(response.data).get('code') == 1
        assert json.loads(response.data).get('msg') == getI18n(ResponseCode.USER_AUTH_FAILED, 'zh')
        response = client.post('/action/auth/login',
                               json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 2
        assert session['user_name'] == 'tester'
        assert session['user_id'] is not None
        token = response.headers.get('X-Csrftoken')
        response = client.post('/action/auth/modify-password',
                               json={'username': 'tester', 'old_password': 'xxx',
                                     'new_password': test_pw2},
                               headers={'X-Csrftoken': token})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == -1
        assert json.loads(response.data).get('msg') == getI18n(ResponseCode.USER_AUTH_FAILED, 'zh')
        response = client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 2
        assert session['user_name'] == 'tester'
        assert session['user_id'] is not None
        token2 = response.headers.get('X-Csrftoken')
        assert token2 != token
        # 测试不存在的用户登录（tester2 不存在）
        response = client.post('/action/auth/login',
                               json={'username': 'tester2', 'password': test_pw})
        # 用户不存在，应该返回 400
        assert response.status_code == 400
        assert json.loads(response.data).get('code') == 1


# =====================================================================
# 以下为 test_user_views_extra.py 合并的测试类（使用 mock 风格）
# =====================================================================

import secrets
from flask import Flask, session as flask_session, request as flask_request
from unittest.mock import patch as mock_patch, MagicMock


class TestInsertSession:
    """测试 insert_session 函数"""

    def test_insert_session_sets_values(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp)

        login_user = {
            'user_name': 'Admin',
            'user_id': 'user_001',
            'role': Role.ADMIN
        }

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.UserSessionCache') as mock_cache:
                insert_session(login_user, True)
                assert flask_session.get('logged_in') is True
                assert flask_session.get('user_name') == 'Admin'
                assert flask_session.get('user_id') == 'user_001'
                assert flask_session.get('X-Csrftoken') is not None
                mock_cache.set_user_session.assert_called_once()
                call_args = mock_cache.set_user_session.call_args
                assert call_args[0][0] == 'user_001'
                assert call_args[1]['role'] == 1

    def test_insert_session_normal_user_role_zero(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp)

        login_user = {
            'user_name': 'normaluser',
            'user_id': 'user_002',
            'role': Role.NORMAL
        }

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.UserSessionCache'):
                insert_session(login_user, True)
                call_args = flask_session.get('X-Csrftoken')
                assert call_args is not None


class TestClearSession:
    """测试 clear_session 函数"""

    def test_clear_session(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp)

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.UserSessionCache') as mock_cache:
                from flask import request
                request.user_id = 'user_001'
                flask_session['logged_in'] = True
                flask_session['user_name'] = 'test'
                clear_session()
                assert flask_session.get('logged_in') is None
                assert flask_session.get('user_name') is None
                mock_cache.delete_user_session.assert_called_once_with('user_001')


class TestGenericLogin:
    """测试 generic_login 函数"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp)
        return app

    def test_login_success(self):
        app = self._make_app()
        login_user = {
            'user_name': 'testuser',
            'user_id': 'user_001',
            'role': 'normal'
        }

        def fake_insert(user, logged_in):
            flask_session['X-Csrftoken'] = 'fake-csrf-token'

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.login_manager') as mock_lm, \
                 mock_patch('framework.user_manager.views.insert_session',
                       side_effect=fake_insert) as mock_insert, \
                 mock_patch('framework.user_manager.views.make_response') as mock_resp:
                mock_lm.login.return_value = (True, login_user, ResponseCode.OK)
                mock_resp.return_value = MagicMock()

                result = generic_login('testuser', 'password', '127.0.0.1')
                mock_insert.assert_called_once_with(login_user, True)
                assert mock_resp.called

    def test_login_failure(self):
        app = self._make_app()

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.login_manager') as mock_lm:
                mock_lm.login.return_value = (False, {}, ResponseCode.USER_AUTH_FAILED)
                result = generic_login('testuser', 'wrong', '127.0.0.1')
                assert result['code'] == 1

    def test_login_first_login(self):
        app = self._make_app()
        login_user = {
            'user_name': 'newuser',
            'user_id': 'user_002',
            'role': 'normal'
        }

        def fake_insert(user, logged_in):
            flask_session['X-Csrftoken'] = 'fake-csrf-token'

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.login_manager') as mock_lm, \
                 mock_patch('framework.user_manager.views.insert_session',
                       side_effect=fake_insert) as mock_insert, \
                 mock_patch('framework.user_manager.views.make_response') as mock_resp:
                mock_lm.login.return_value = (False, login_user, ResponseCode.USER_FIRST_LOGIN)
                mock_resp.return_value = MagicMock()
                result = generic_login('newuser', 'password', '127.0.0.1')
                mock_insert.assert_called_once_with(login_user, False)

    def test_login_pw_timeout(self):
        app = self._make_app()
        login_user = {
            'user_name': 'testuser',
            'user_id': 'user_003',
            'role': 'normal'
        }

        def fake_insert(user, logged_in):
            flask_session['X-Csrftoken'] = 'fake-csrf-token'

        with app.test_request_context('/'):
            with mock_patch('framework.user_manager.views.login_manager') as mock_lm, \
                 mock_patch('framework.user_manager.views.insert_session',
                       side_effect=fake_insert) as mock_insert, \
                 mock_patch('framework.user_manager.views.make_response') as mock_resp:
                mock_lm.login.return_value = (False, login_user, ResponseCode.PW_TIMEOUT)
                mock_resp.return_value = MagicMock()
                result = generic_login('testuser', 'password', '127.0.0.1')
                mock_insert.assert_called_once_with(login_user, False)


class TestLoginRoute:
    """测试 /auth/login 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp, url_prefix='/auth')
        return app

    def test_login_route(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.generic_login') as mock_gl:
            mock_gl.return_value = {"code": 0, "msg": "ok"}
            response = client.post('/auth/login',
                                   json={'username': 'test', 'password': 'pw'})
            mock_gl.assert_called_once_with('test', 'pw', '127.0.0.1')


class TestAdminRoute:
    """测试 /auth/admin 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp, url_prefix='/auth')
        return app

    def test_admin_route(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.generic_login') as mock_gl:
            mock_gl.return_value = {"code": 0, "msg": "ok"}
            response = client.post('/auth/admin',
                                   json={'username': 'admin', 'password': 'pw'})
            mock_gl.assert_called_once_with('admin', 'pw', '127.0.0.1', admin=True)


class TestLogoutRoute:
    """测试 /auth/logout 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp, url_prefix='/auth')
        return app

    def test_logout(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.login_manager') as mock_lm, \
             mock_patch('framework.user_manager.views.clear_session'):
            response = client.post('/auth/logout')
            data = response.get_json()
            assert data['code'] == 0
            assert data['msg'] == 'ok'
            mock_lm.logout.assert_called_once()


class TestModifyPasswordRoute:
    """测试 /auth/modify-password 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp, url_prefix='/auth')
        return app

    def test_modify_success(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um, \
             mock_patch('framework.user_manager.views.clear_session'):
            mock_um.modify.return_value = (True, 'ok')
            response = client.post('/auth/modify-password',
                                   json={'username': 'test',
                                         'old_password': 'old',
                                         'new_password': 'new'})
            data = response.get_json()
            assert data['code'] == 0

    def test_modify_failure(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.modify.return_value = (False, ResponseCode.USER_AUTH_FAILED)
            response = client.post('/auth/modify-password',
                                   json={'username': 'test',
                                         'old_password': 'old',
                                         'new_password': 'new'})
            data = response.get_json()
            assert data['code'] == -1


class TestResetPasswordRoute:
    """测试 /auth/reset-password 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(auth_bp, url_prefix='/auth')
        return app

    def test_reset_success(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.reset_pw.return_value = (True, 'ok')
            response = client.post('/auth/reset-password',
                                   json={'username': 'test',
                                         'admin_password': 'admin',
                                         'new_password': 'new'})
            data = response.get_json()
            assert data['code'] == 0

    def test_reset_failure(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.reset_pw.return_value = (False, ResponseCode.USER_AUTH_FAILED)
            response = client.post('/auth/reset-password',
                                   json={'username': 'test',
                                         'admin_password': 'admin',
                                         'new_password': 'new'})
            data = response.get_json()
            assert data['code'] == -1


class TestListUsersRoute:
    """测试 /user/list 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(user_bp, url_prefix='/user')
        return app

    def test_list_success(self):
        app = self._make_app()
        mock_user = MagicMock()
        mock_user.user_id = 'id1'
        mock_user.user_name = 'user1'
        mock_user.role = 'normal'
        mock_user.status = 'active'

        @app.before_request
        def inject():
            from flask import request
            request.user_id = 'admin_id'

        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.list_user.return_value = (True, 'ok', [mock_user])
            response = client.get('/user/list')
            data = response.get_json()
            assert data['code'] == 0
            assert len(data['data']) == 1
            assert data['data'][0]['user_name'] == 'user1'

    def test_list_failure(self):
        app = self._make_app()

        @app.before_request
        def inject():
            from flask import request
            request.user_id = 'admin_id'

        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.list_user.return_value = (False, 'error', None)
            response = client.get('/user/list')
            data = response.get_json()
            assert data['code'] == -1


class TestDeleteUserRoute:
    """测试 /user/rm/<user_id> 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(user_bp, url_prefix='/user')
        return app

    def test_delete_success(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um, \
             mock_patch('framework.user_manager.views.UserSessionCache') as mock_cache:
            mock_um.delete_user.return_value = (True, 'ok')
            response = client.post('/user/rm/user123',
                                   json={'admin_password': 'pw'})
            data = response.get_json()
            assert data['code'] == 0
            mock_cache.delete_user_session.assert_called_once_with('user123')

    def test_delete_failure(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um, \
             mock_patch('framework.user_manager.views.UserSessionCache') as mock_cache:
            mock_um.delete_user.return_value = (False, 'error')
            response = client.post('/user/rm/user123',
                                   json={'admin_password': 'pw'})
            data = response.get_json()
            assert data['code'] == -1
            mock_cache.delete_user_session.assert_not_called()


class TestCreateUserRoute:
    """测试 /user POST 路由"""

    def _make_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test_secret'
        app.register_blueprint(user_bp, url_prefix='/user')
        return app

    def test_create_success(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.create.return_value = (True, 'ok', {'user_id': 'new_id'})
            response = client.post('/user', json={
                'user_name': 'newuser',
                'password': 'pw',
                'admin_password': 'admin',
                'role': 'normal'
            })
            data = response.get_json()
            assert data['code'] == 0
            assert data['data'] == {'user_id': 'new_id'}

    def test_create_failure(self):
        app = self._make_app()
        with app.test_client() as client, \
             mock_patch('framework.user_manager.views.user_manager') as mock_um:
            mock_um.create.return_value = (False, ['error1', 'error2'], None)
            response = client.post('/user', json={
                'user_name': 'newuser',
                'password': 'pw'
            })
            data = response.get_json()
            assert data['code'] == -1
