import sys

import pytest
from flask import Flask

import os
from unittest.mock import patch

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from session_cache import UserSessionCache
from bp import action_bp
from common.response.response_code import ResponseCode
from framework_test.public.random_pw import random_pw

key = random_pw(15)


def create_app():
    """创建 Flask 测试应用"""
    app = Flask(__name__)
    app.secret_key = key  # 测试用的密钥

    @action_bp.route('/auth/login', methods=['GET'])
    def login():
        return {"code": 0, "message": "Login API"}, 200

    @action_bp.route('/test', methods=['GET'])
    def test_action():
        return {"code": 0, "message": "Test action"}, 200

    @action_bp.route("/<test>", methods=['GET', 'POST', 'DELETE'])
    @action_bp.route("/<test>/<test2>", methods=['GET', 'POST', 'DELETE'])
    def testfuc(test, test2):
        return {"code": 0, "test": test}, 200

    app.register_blueprint(action_bp)
    return app


@pytest.fixture(scope='session')
def client():
    """测试客户端"""
    app = create_app()
    with app.test_client() as client:
        yield client


# Started by AICoder, pid:uc7f9a09edc74c3146450b9ca1ee940b26318d2a
def test_blocked_invalid_characters(client):
    """测试含有非法字符的 URL 被禁止访问"""
    response = client.get('/action/.bash_history')
    assert response.status_code == 400

    response = client.get('/action/../test')
    assert response.status_code == 400

    response = client.get('/action/./test')
    assert response.status_code == 400


# Ended by AICoder, pid:uc7f9a09edc74c3146450b9ca1ee940b26318d2a

def test_skip_auth_login(client):
    """测试登录路径被允许访问"""
    response = client.get('/action/auth/login')
    assert response.status_code == 200
    assert response.json.get('message') == "Login API"


def test_csrf_rejection_missing_token(client):
    """测试缺少 CSRF Token 时拒绝访问"""
    with client.session_transaction() as session:
        session["X-Csrftoken"] = "valid_csrf"
        session["user_id"] = 1
        session["user_name"] = "test_user"
        session["logged_in"] = True

    response = client.get('/action/test')
    assert response.status_code == 401


def test_csrf_rejection_invalid_token(client):
    """测试 CSRF Token 无效时拒绝访问"""
    with client.session_transaction() as session:
        session["X-Csrftoken"] = "valid_csrf"
        session["user_id"] = 1
        session["user_name"] = "test_user"
        session["logged_in"] = True

    headers = {"X-Csrftoken": "invalid_csrf"}
    response = client.get('/action/test', headers=headers)
    assert response.status_code == 401


def test_valid_csrf_and_login(client):
    """测试包含有效 CSRF Token 以及用户已登录时可访问"""
    with client.session_transaction() as session:
        session["X-Csrftoken"] = "valid_csrf"
        session["user_id"] = 1
        session["user_name"] = "test_user"
        session["logged_in"] = True
    UserSessionCache.set_user_session(1, "valid_csrf", '127.0.0.1')
    headers = {"X-Csrftoken": "valid_csrf"}
    with patch('bp.SysConfig.query_system_configuration', return_value=(True, 30, ResponseCode.OK)):
        response = client.get('/action/test', headers=headers)
    assert response.status_code == 200
    assert response.json.get('message') == "Test action"
    UserSessionCache.delete_user_session(1)


def test_not_logged_in(client):
    """测试用户未登录时拒绝访问"""
    with client.session_transaction() as session:
        session["X-Csrftoken"] = "valid_csrf"
        session.pop("user_id", None)
        session.pop("logged_in")

    headers = {"X-Csrftoken": "valid_csrf"}
    response = client.get('/action/test', headers=headers)
    assert response.status_code == 401
