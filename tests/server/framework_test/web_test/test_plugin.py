import time

import pytest

import json
import sqlite3
from common.db.SQLOperation import get_conn, DB_INFO

from framework.user_manager.user_db import UserManager
from framework_test.public.random_pw import random_pw

admin_init_pw = random_pw()
admin_pw = random_pw()
admin_name = 'AdminTest'
admin_id, admin_token = None, None
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


def test_list_plugin(client, app, mock_admin_setup):
    with client:
        response = client.get('action/pluginmanager/list', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == -1
        assert 'data' not in rsp
    LOCAL_PLUGIN_INFO_CODEMIG = {
        "plugin_type": 'codemig',
        "current_version": "V25.04.01.B02",
        "status": 3,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "progress_status": 100,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "plugin_meta_json": ""
    }
    conn = None
    try:
        conn = get_conn(DB_INFO.file)
        cursor = conn.cursor()

        sql = f"INSERT INTO plugin (plugin_type, current_version, status, update_time, progress_status, create_time, plugin_meta_json) \
                            VALUES (:plugin_type, :current_version, :status, :update_time, :progress_status, :create_time, :plugin_meta_json) ON CONFLICT(plugin_type) DO UPDATE SET \
                            current_version = excluded.current_version,  update_time = excluded.update_time;"
        cursor.execute(sql, (LOCAL_PLUGIN_INFO_CODEMIG))
        conn.commit()
    except sqlite3.Error as err:
        conn.rollback()
        raise Exception("Create error: %s", err)
    with client:
        response = client.get('action/pluginmanager/list', headers={'X-Csrftoken': admin_token})
        assert response.status_code == 200
        rsp = json.loads(response.data)
        assert rsp.get('code') == 0
        assert len(rsp.get('data')) == 1