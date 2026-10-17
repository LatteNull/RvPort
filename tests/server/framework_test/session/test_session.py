import json
import os
import shutil
import sys
import time

import sqlite3
import tempfile

from unittest.mock import MagicMock, patch

import pytest
from flask import session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from framework_test.public.random_pw import random_pw
from app import create_app
from common.response.code2string import getI18n
from common.response.response_code import ResponseCode
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.user_manager import user_manager, weak_pwd
from framework.user_manager.user_db import UserManager, UserLoginFailedTime, UserFailedLogin, \
    IPFailedLogin
from session_cache import UserSessionCache
from common.db.SQLOperation import DB_INFO
import common.db.SQLOperation as sql_op
from common.db.SQLOperation import Base, engine as global_engine

test_pw = random_pw()
test_pw2 = random_pw()
key = random_pw(15)
mock_request = None
admin_id = None


@pytest.fixture
def session_app():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
        db_path = db_file.name

    try:
        # 创建表结构
        conn = sqlite3.connect(db_path)
        sql_file = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                                                 'scripts', 'install', 'sqlite.sql'))
        with open(sql_file, "r") as f:
            sql = f.read()
        try:
            conn.executescript(sql)
            print(f"Executed SQL from: {sql_file}")
        except Exception as e:
            print(f"Executed SQL error from: {sql_file}: {e}")
        conn.commit()
        conn.close()

        # 重新初始化引擎以使用测试数据库
        if hasattr(sql_op, 'engine'):
            global_engine.dispose()

        # 创建新引擎（测试环境不使用加密）
        new_engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )

        # 创建新的会话工厂
        new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
        new_db_session = scoped_session(new_session_local)

        # 临时替换全局变量
        original_engine = sql_op.engine
        original_session = sql_op.db_session
        sql_op.engine = new_engine
        sql_op.db_session = new_db_session

        # 确保表存在
        Base.metadata.create_all(bind=new_engine)

        # 设置环境变量，让 Config 使用测试数据库路径
        old_env_uri = os.environ.get('SQLITE_DATABASE_URI')
        os.environ['SQLITE_DATABASE_URI'] = f'sqlite:///{db_path}'

        try:
            # 初始化配置
            SysConfig.list_all()

            global mock_request
            mock_request = MagicMock()
            mock_request.user_id = 1
            mock_request.user_name = 'test'
            mock_request.remote_addr = '127.0.0.1'
            SysConfig.update(ConfigKeys.SESSION_TIMEOUT, '10')

            global app_instance
            app_instance = create_app(key, {
                'TESTING': True,
            })

            yield app_instance
        finally:
            # 恢复环境变量
            if old_env_uri is not None:
                os.environ['SQLITE_DATABASE_URI'] = old_env_uri
            elif 'SQLITE_DATABASE_URI' in os.environ:
                del os.environ['SQLITE_DATABASE_URI']

            # 恢复原始引擎和会话
            sql_op.engine = original_engine
            sql_op.db_session = original_session
            if hasattr(sql_op, 'engine'):
                new_engine.dispose()
    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def session_client(session_app):
    return session_app.test_client()


@pytest.fixture
def session_client2(session_app):
    return session_app.test_client()


# 用于每个模块执行一次
@pytest.fixture(scope="function", autouse=False)
def mock_db_setup(request):
    status, user_id = UserManager.save('tester', 'normal', test_pw)
    if not status:
        tester = UserManager.query(user_name='tester')
        user_id = tester.user_id

    status, user_id2 = UserManager.save('tester2', 'normal', test_pw)
    if not status:
        tester = UserManager.query(user_name='tester2')
        user_id2 = tester.user_id
    status, user_id3 = UserManager.save('tester3', 'normal', test_pw)
    if not status:
        tester = UserManager.query(user_name='tester3')
        user_id3 = tester.user_id

    status, user_id4 = UserManager.save('tester4', 'normal', test_pw)
    if not status:
        tester = UserManager.query(user_name='tester4')
        user_id4 = tester.user_id
    admin = UserManager.query(nopw=False, user_name='Admin')
    global admin_id
    admin_id = admin.user_id
    yield

    def cleanup():
        request = MagicMock()
        request.user_id = 1
        request.remote_addr = 'test'
        user_manager.delete_user(user_id, {'admin_password': admin.pw, 'delete_task': 'False'},
                                 mock_request)
        user_manager.delete_user(user_id2, {'admin_password': admin.pw, 'delete_task': 'False'},
                                 mock_request)
        user_manager.delete_user(user_id3, {'admin_password': admin.pw, 'delete_task': 'False'},
                                 mock_request)
        user_manager.delete_user(user_id4, {'admin_password': admin.pw, 'delete_task': 'False'},
                                 mock_request)
        UserSessionCache.delete_user_session(user_id)
        UserSessionCache.delete_user_session(user_id2)
        UserSessionCache.delete_user_session(user_id3)
        UserSessionCache.delete_user_session(user_id4)
        # ORM 类不需要 delete_instance

    request.addfinalizer(cleanup)


def test_login_one_session(session_client, session_app, mock_db_setup, session_client2):
    #     一个用户只能在一个session登录
    with session_client:
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('msg') == getI18n(ResponseCode.USER_FIRST_LOGIN, 'zh')
        token = response.headers.get('X-Csrftoken')
        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token})
        token = response.headers.get('X-Csrftoken')
        assert token is None
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        token = response.headers.get('X-Csrftoken')
        user = json.loads(json.loads(response.data).get('msg'))
        assert user.get('last_login') != '--'
        assert user.get('last_login_duration') != '--'
        assert user.get('last_login_ip') == '127.0.0.1'
        response = session_client2.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        token2 = response.headers.get('X-Csrftoken')
        user_id = json.loads(json.loads(response.data).get('msg')).get('user_id')
        last_time = UserSessionCache.get_user_last_time(user_id)
        time.sleep(2)
        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw2, 'new_password': test_pw},
            headers={'X-Csrftoken': token})
        assert response.status_code == 401
        last_time2 = UserSessionCache.get_user_last_time(user_id)
        assert last_time2 == last_time
        time.sleep(2)
        response = session_client2.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw2, 'new_password': test_pw},
            headers={'X-Csrftoken': token2})
        assert response.status_code == 200
        last_time3 = UserSessionCache.get_user_last_time(user_id)
        assert last_time3 is None


def test_login_two_user_one_session(session_client, session_app, mock_db_setup, session_client2):
    #     第二个登录用户会踢掉上一个登录的用户
    with session_client:
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        token = response.headers.get('X-Csrftoken')
        session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token})
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        token = response.headers.get('X-Csrftoken')
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw})
        assert response.status_code == 200
        token2 = response.headers.get('X-Csrftoken')
        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw2, 'new_password': test_pw},
            headers={'X-Csrftoken': token})
        assert response.status_code == 401

        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester2', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token2})
        assert response.status_code == 200
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw2})
        assert response.status_code == 200


def test_login_max_online(session_app, mock_db_setup):
    #     一个用户只能在一个session登录

    SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '3')
    client1 = session_app.test_client()
    client2 = session_app.test_client()
    client3 = session_app.test_client()
    client4 = session_app.test_client()
    with client1 and client2 and client3 and client4:
        response = client1.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw})
        token = response.headers.get('X-Csrftoken')
        response = client1.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token})
        assert response.status_code == 200
        response = client1.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        token = response.headers.get('X-Csrftoken')
        assert response.status_code == 200

        response = client2.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw})
        token2 = response.headers.get('X-Csrftoken')
        assert response.status_code == 200
        response = client2.post(
            '/action/auth/modify-password',
            json={'username': 'tester2', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token2})
        assert response.status_code == 200
        response = client2.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw2})
        token2 = response.headers.get('X-Csrftoken')
        assert response.status_code == 200

        response = client3.post(
            '/action/auth/login', json={'username': 'tester3', 'password': test_pw})
        token3 = response.headers.get('X-Csrftoken')
        response = client3.post(
            '/action/auth/modify-password',
            json={'username': 'tester3', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token3})
        assert response.status_code == 200
        response = client3.post(
            '/action/auth/login', json={'username': 'tester3', 'password': test_pw2})
        token3 = response.headers.get('X-Csrftoken')
        assert response.status_code == 200

        response = client4.post(
            '/action/auth/login', json={'username': 'tester4', 'password': test_pw})
        assert response.status_code == 400

        SysConfig.update(ConfigKeys.MAX_ONLINE_USERS, '4')
        response = client4.post(
            '/action/auth/login', json={'username': 'tester4', 'password': test_pw})
        assert response.status_code == 200


def test_session(session_client, session_app, mock_db_setup, session_client2):
    with session_client:
        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 2
        assert session['user_name'] == 'tester'
        assert session['user_id'] is not None
        token = response.headers.get('X-Csrftoken')
        assert token is not None
        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        tokenm = response.headers.get('X-Csrftoken')
        assert tokenm is None
        response2 = session_client2.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw})
        token_client2 = response2.headers.get('X-Csrftoken')
        response2 = session_client2.post(
            '/action/auth/modify-password',
            json={'username': 'tester2', 'old_password': test_pw, 'new_password': test_pw2},
            headers={'X-Csrftoken': token_client2})

        response = session_client.post(
            '/action/auth/login', json={'username': 'tester', 'password': test_pw2})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == 0
        token2 = response.headers.get('X-Csrftoken')
        assert token2 is not None
        assert token2 != token
        response2 = session_client2.post(
            '/action/auth/login', json={'username': 'tester2', 'password': test_pw2})
        assert response2.status_code == 200
        assert json.loads(response2.data).get('code') == 0
        token_client2 = response.headers.get('X-Csrftoken')
        assert token_client2 is not None

        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw2, 'new_password': random_pw(4)},
            headers={'X-Csrftoken': token2})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == -1
        token3 = response.headers.get('X-Csrftoken')
        assert token3 is None

        time.sleep(10)
        response = session_client.post(
            '/action/auth/modify-password',
            json={'username': 'tester', 'old_password': test_pw2, 'new_password': random_pw(4)},
            headers={'X-Csrftoken': token2})
        assert response.status_code == 200
        assert json.loads(response.data).get('code') == -1
        token3 = response.headers.get('X-Csrftoken')
        assert token3 is None
        # time.sleep(10 * 60 + 10)
        with patch('bp.UserSessionCache.get_user_last_time', return_value=1):
            response = session_client.post(
                '/action/auth/modify-password',
                json={'username': 'tester', 'old_password': test_pw2, 'new_password': random_pw(4)},
                headers={'X-Csrftoken': token2})
            assert response.status_code == 401
