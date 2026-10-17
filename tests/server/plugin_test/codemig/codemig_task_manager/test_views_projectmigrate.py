"""codemig_task_manager/views.py 补充测试：rescan 状态机 / 项目迁移路由 / 下载路由"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_task_manager import views as v
from plugin.codemig.codemig_task_manager.views import codemig_task_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.secret_key = 'test-secret'
    app.register_blueprint(codemig_task_bp)

    from flask import request as real_request

    @app.before_request
    def _inject_user_id():
        real_request.user_id = 'uid'

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _session_login(client):
    with client.session_transaction() as s:
        s['user_name'] = 'tester'


def _user_ok():
    user = MagicMock()
    user.user_name = 'tester'
    return user


# ---------------------------------------------------------------- rescan 状态机
def test_rescan_state_machine():
    key = ('tester', 1)
    v._rescan_states.pop(key, None)
    # 初始
    assert v._is_rescan_running('tester', 1) is False
    st = v._get_rescan_state('tester', 1)
    assert st == {"status": 0, "processed": 0, "total": 0, "fail_reason": ""}
    # 标记运行
    assert v._try_mark_rescan_running('tester', 1) is True
    assert v._is_rescan_running('tester', 1) is True
    assert v._try_mark_rescan_running('tester', 1) is False  # 重入被拒
    # 更新状态
    v._set_rescan_state('tester', 1, processed=2, total=5)
    assert v._get_rescan_state('tester', 1)['processed'] == 2
    v._set_rescan_state('tester', 1, status=2)
    assert v._is_rescan_running('tester', 1) is False
    v._rescan_states.pop(key, None)


def test_count_and_query_changed_files(tmp_path, monkeypatch):
    import sqlite3
    db_dir = tmp_path / 'tester' / '1'
    db_dir.mkdir(parents=True)
    db = db_dir / '1.db'
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE codemig_task_directory_file ("
        "file_id INTEGER PRIMARY KEY, file_path TEXT, type INTEGER,"
        " has_removed INTEGER, file_source TEXT)")
    conn.executemany(
        "INSERT INTO codemig_task_directory_file VALUES (?,?,?,?,?)",
        [(1, 'a.c', 0, 0, 'changed'), (2, 'b.c', 0, 1, 'changed'),
         (3, 'c.c', 0, 0, 'original'), (4, 'd.c', 2, 0, 'changed')])
    conn.commit()
    conn.close()
    monkeypatch.setattr(v, 'get_database_path', lambda u, d: db)
    assert v._count_changed_files('tester', 1) == 1
    files = v._query_changed_files('tester', 1)
    assert files == [{'file_id': 1, 'file_path': 'a.c'}]


def test_count_changed_files_no_db(tmp_path, monkeypatch):
    monkeypatch.setattr(v, 'get_database_path',
                        lambda u, d: tmp_path / 'nope.db')
    assert v._count_changed_files('tester', 1) == 0
    assert v._query_changed_files('tester', 1) == []


def test_do_rescan_all_files(monkeypatch):
    key = ('tester', 9)
    v._rescan_states.pop(key, None)
    monkeypatch.setattr(v, '_query_changed_files',
                        lambda u, d: [{'file_id': 1}, {'file_id': 2}])
    with patch.object(v, 'rescan_file', side_effect=[None, ValueError('boom')]):
        v._do_rescan_all_files('tester', 9)
    st = v._get_rescan_state('tester', 9)
    assert st['status'] == 2
    assert st['processed'] == 2
    v._rescan_states.pop(key, None)


def test_do_rescan_all_files_fatal(monkeypatch):
    key = ('tester', 9)
    v._rescan_states.pop(key, None)
    def _fail(u, d):
        raise OSError('disk')

    monkeypatch.setattr(v, '_query_changed_files', _fail)
    v._do_rescan_all_files('tester', 9)
    st = v._get_rescan_state('tester', 9)
    assert st['status'] == 3
    assert 'disk' in st['fail_reason']
    v._rescan_states.pop(key, None)


# ---------------------------------------------------------------- /task/rescan
def test_rescan_route_no_session(client):
    resp = client.post('/task/rescan', json={})
    assert resp.get_json()['code'] == -1


def test_rescan_route_no_privilege(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=None):
        resp = client.post('/task/rescan', json={'dir_id': 1})
    assert resp.get_json()['code'] == -1


def test_rescan_route_missing_dir(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()):
        resp = client.post('/task/rescan', json={})
    assert 'missing dir_id' in resp.get_json()['msg']


def test_rescan_route_ok(client):
    _session_login(client)
    v._rescan_states.pop(('tester', 5), None)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, '_count_changed_files', return_value=3), \
         patch.object(v, '_do_rescan_all_files'):
        resp = client.post('/task/rescan', json={'dir_id': 5})
    body = resp.get_json()
    assert body == {'code': 0, 'msg': 'OK', 'total': 3}
    v._rescan_states.pop(('tester', 5), None)


def test_rescan_status_route(client):
    _session_login(client)
    v._set_rescan_state('tester', 7, status=1, processed=2, total=4)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()):
        resp = client.post('/task/rescan_status', json={'dir_id': 7})
    body = resp.get_json()
    assert body['status'] == 1 and body['total'] == 4
    v._rescan_states.pop(('tester', 7), None)


# ---------------------------------------------------------------- 项目迁移路由
def test_migrate_project_no_session(client):
    resp = client.post('/task/migrate_project', json={})
    assert resp.get_json()['code'] == -1


def test_migrate_project_lock_error(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'task_file_lock',
                      side_effect=RuntimeError('lock timeout')):
        resp = client.post('/task/migrate_project',
                           json={'dir_id': 1, 'task_id': 1})
    assert 'lock timeout' in resp.get_json()['msg']


def test_rollback_project_route(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'rollback_project_migrate_handler',
                      return_value={'code': 0, 'msg': 'ok'}) as rb:
        resp = client.post('/task/rollback_project_migrate',
                           json={'dir_id': 1, 'target_hash': 'abc'})
    assert resp.get_json()['code'] == 0
    rb.assert_called_once_with('tester', 1, 'abc')


def test_reopen_project_ai(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'query_project_ai_suggestion',
                      return_value=(True, 1, {'s': 1})):
        resp = client.post('/task/reopen_project_ai', json={'dir_id': 1})
    assert resp.get_json()['code'] == 0


def test_reopen_project_ai_fail(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'query_project_ai_suggestion',
                      return_value=(False, None, None)):
        resp = client.post('/task/reopen_project_ai', json={'dir_id': 1})
    assert resp.get_json()['code'] == -1


def test_list_project_history_route(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'list_project_migrate_history_handler',
                      return_value={'code': 0, 'data': []}):
        resp = client.post('/task/list_project_history', json={'dir_id': 1})
    assert resp.get_json()['code'] == 0


def test_generate_project_patch_empty_from(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'generate_project_patch_handler',
                      return_value={'code': 1, 'msg': 'from_hash 不能为空'}):
        resp = client.post('/task/generate_project_patch',
                           json={'dir_id': 1, 'from_hash': ''})
    assert resp.get_json()['code'] == 1


def test_generate_project_patch_download(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch.object(v, 'generate_project_patch_handler',
                      return_value={'code': 0, 'data': 'diff --git a'}):
        resp = client.post('/task/generate_project_patch',
                           json={'dir_id': 1, 'from_hash': 'aabb1122',
                                 'to_hash': 'ccdd3344'})
    assert resp.status_code == 200
    assert b'diff --git a' in resp.data
    assert 'attachment' in resp.headers['Content-Disposition']
    assert 'aabb1122_to_ccdd3344' in resp.headers['Content-Disposition']


# ------------------------------------------- ①代码生成：缺失+新增文件清单
def test_project_migrate_extra_files_missing_params(client):
    resp = client.post('/task/project_migrate_missing_files', json={})
    assert resp.status_code == 400
    assert resp.get_json()['code'] == 400


def test_project_migrate_extra_files_no_privilege(client):
    with patch.object(v.UserManager, 'query_by_id', return_value=None):
        resp = client.post('/task/project_migrate_missing_files',
                           json={'task_id': 1, 'user_name': 'tester'})
    assert resp.get_json()['code'] == -1


def test_project_migrate_extra_files_task_not_found(client):
    _session_login(client)
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch('plugin.codemig.codemig_task_manager.query_processor.query_dir_id_by_task_id',
               return_value=(False, None)):
        resp = client.post('/task/project_migrate_missing_files',
                           json={'task_id': 1, 'user_name': 'tester'})
    assert resp.get_json()['code'] == -1


def test_project_migrate_extra_files_ok(client):
    """路由透传 processor 结果（code=0 + missing/generated 双清单）"""
    _session_login(client)
    payload = {'code': 0, 'msg': 'OK', 'data': {
        'missing': [{'file_id': 5, 'file_name': 'foo_riscv64.S',
                     'file_path': '/x/changed/foo_riscv64.S', 'is_file': True}],
        'generated': [{'file_id': 11, 'file_name': 'bar.S',
                       'file_path': '/x/changed/bar.S', 'is_file': True}]}}
    with patch.object(v.UserManager, 'query_by_id', return_value=_user_ok()), \
         patch('plugin.codemig.codemig_task_manager.query_processor.query_dir_id_by_task_id',
               return_value=(True, 7)), \
         patch('plugin.codemig.codemig_task_manager.query_processor.query_project_migrate_extra_files',
               return_value=payload) as mock_qp:
        resp = client.post('/task/project_migrate_missing_files',
                           json={'task_id': 1, 'user_name': 'tester'})
    body = resp.get_json()
    assert body['code'] == 0
    assert len(body['data']['missing']) == 1
    assert len(body['data']['generated']) == 1
    mock_qp.assert_called_once_with('tester', 7)
