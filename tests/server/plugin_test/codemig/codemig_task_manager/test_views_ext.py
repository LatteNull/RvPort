"""
为 plugin/codemig/codemig_task_manager/views.py 提供补充测试。
重点覆盖：用户校验、session 缺失、JSON 参数校验以及各个分支返回结构。
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask, session as flask_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_task_manager import views as v
from plugin.codemig.codemig_task_manager.views import codemig_task_bp


@pytest.fixture
def app():
    """构造带 codemig_task_bp 的 Flask 测试应用"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.secret_key = 'test-secret'
    app.register_blueprint(codemig_task_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _mock_request(app):
    """每个测试自动 patch flask.request 为一个普通 MagicMock。

    用 patch.object(v, 'request') 时 mock 会把 flask.request 当 async 对象处理，
    导致 get_json() 返回 coroutine。这里直接用 patch(path, new=mock) 绕过。

    同时在 app.test_request_context() 中执行，让 flask.session 等代理可用。
    """
    mock_req = MagicMock()
    mock_req.user_id = 'uid'
    mock_req.remote_addr = '127.0.0.1'
    with app.test_request_context():
        with patch('plugin.codemig.codemig_task_manager.views.request', mock_req):
            yield mock_req


# ------------------- check_user -------------------

def test_check_user_unknown_user(app, _mock_request):
    with app.test_request_context():
        with patch.object(v.UserManager, 'query_by_id', return_value=None):
            code, msg = v.check_user('someone')
            assert code == -1
            assert msg == "Unkown user."


def test_check_user_no_privilege(app, _mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'real_user'
    with app.test_request_context():
        with patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
            code, msg = v.check_user('other_name')
            assert code == -1
            assert msg == 'no privilege'


def test_check_user_ok(app, _mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    with app.test_request_context():
        with patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
            code, msg = v.check_user('me')
            assert code == 0
            assert msg is None


# ------------------- /create -------------------

def test_create_and_process_unknown_user(_mock_request):
    _mock_request.get_json.return_value = {'user_name': 'me'}
    with patch.object(v.UserManager, 'query_by_id', return_value=None):
        result = v.create_and_process()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_create_and_process_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'real_user'
    _mock_request.get_json.return_value = {'user_name': 'other', 'task_name': 't'}
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'record_operation_log'):
        result = v.create_and_process()
        assert result['code'] == -1
        assert result['msg'] == 'no privilege'


def test_create_and_process_no_files(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me', 'upload_file_info_lists': None}
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_and_process()
        assert result == {"code": -1, "msg": "No file uploaded."}


def test_create_and_process_multiple_files(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me',
        'upload_file_info_lists': [[1, 'a'], [2, 'b']]}
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_and_process()
        assert result == {"code": -1, "msg": "Only single file can be uploaded."}


def test_create_and_process_unsupported_language(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me',
        'upload_file_info_lists': [[1, 'file.zip']],
        'scan_dependencies': 'yes',
        'dependencies': 'rust',
    }
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_and_process()
        assert result == {"code": -1, "msg": "Unsupported language."}


def test_create_and_process_python_lang(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me',
        'upload_file_info_lists': [[1, 'file.zip']],
        'scan_dependencies': 'yes',
        'dependencies': 'python',
        'python_interpreter': '/usr/bin/python3',
        'python_image_source': 'src',
    }
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'start_task', return_value={'code': 0}) as mock_start:
        result = v.create_and_process()
        assert result == {'code': 0}
        args, _ = mock_start.call_args
        dep_info = args[4]
        assert dep_info.lang == 'python'
        assert dep_info.python == '/usr/bin/python3'


def test_create_and_process_go_lang(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me',
        'upload_file_info_lists': [[1, 'file.zip']],
        'scan_dependencies': 'yes',
        'dependencies': 'go',
        'go_install_path': '/opt/go',
        'go_environment': 'env',
    }
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'start_task', return_value={'code': 0}) as mock_start:
        result = v.create_and_process()
        assert result == {'code': 0}
        args, _ = mock_start.call_args
        dep_info = args[4]
        assert dep_info.lang == 'go'
        assert dep_info.go == '/opt/go'


def test_create_and_process_no_scan(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'user_name': 'me',
        'upload_file_info_lists': [[1, 'file.zip']],
        'scan_dependencies': 'no',
    }
    with patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'start_task', return_value={'code': 0}) as mock_start:
        v.create_and_process()
        args, _ = mock_start.call_args
        dep_info = args[4]
        assert dep_info.scan == 0


# ------------------- /list -------------------

def test_query_task(_mock_request):
    with patch.object(v, 'query_user_tasks', return_value={'code': 0, 'data': []}) as mock_q:
        result = v.query_task()
        mock_q.assert_called_once_with('uid')
        assert result == {'code': 0, 'data': []}


# ------------------- /files -------------------

def test_query_task_files_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_task_files()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_task_files_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.query_task_files()
        assert result['code'] == -1


def test_query_task_files_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_user_task_files',
                         return_value={'code': 0, 'data': []}) as mock_qu:
        result = v.query_task_files()
        assert result == {'code': 0, 'data': []}
        mock_qu.assert_called_once_with('me', 1, 'uid')


# ------------------- /changes -------------------

def test_query_changes_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_changes()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_changes_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.query_changes()
        assert result['code'] == -1


def test_query_changes_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_changes_for_file',
                         return_value={'code': 0}) as mock_qc:
        v.query_changes()
        mock_qc.assert_called_once_with('me', 1, 2, 3)


# ------------------- /dependence_changes -------------------

def test_query_dependence_changes_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_changes()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_changes_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'dependence_id': 4}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence_changes_for_file',
                         return_value={'code': 0}) as mock_qc:
        v.query_dependence_changes()
        mock_qc.assert_called_once_with('me', 1, 2, 3, 4)


# ------------------- /generate -------------------

def test_query_generate_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_generate()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_generate_no_uuid(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'request_uuid': ''}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.query_generate()
        assert result == {"code": -2, "msg": "There is no request uuid in parameters"}


def test_query_generate_lock_error(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3,
        'request_uuid': 'uuid-1', 'model': 'm',
        'reference_arch_paths': [], 'api_format': 'fmt'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.query_generate()
        assert result == {"code": -1, "msg": "locked"}


def test_query_generate_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3,
        'request_uuid': 'uuid-1', 'model': 'm',
        'reference_arch_paths': [], 'api_format': 'fmt'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_generate_for_file',
                         return_value={'code': 0}) as mock_qg, \
            patch.object(v, 'task_file_lock'):
        v.query_generate()
        mock_qg.assert_called_once()


# ------------------- /dependence_generate -------------------

def test_query_dependence_generate_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_generate()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_generate_ok(_mock_request):
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'dependence_id': 4}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v, 'query_dependence_generate_for_file',
                         return_value={'code': 0}) as mock_qg:
        v.query_dependence_generate()
        mock_qg.assert_called_once_with('me', 1, 2, 3, 4, 'uid')


# ------------------- /filetree -------------------

def test_query_file_tree_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_file_tree()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_file_tree_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dir_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_file_tree_processor',
                         return_value={'code': 0}) as mock_qf:
        v.query_file_tree()
        mock_qf.assert_called_once_with('me', 'uid', 1, 2)


# ------------------- /original_file -------------------

def test_query_original_file_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_original_file()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_original_file_ok(_mock_request):
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_path': 'foo.py'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v, 'query_original_file_processor',
                         return_value={'code': 0}) as mock_q:
        v.query_original_file()
        mock_q.assert_called_once_with('me', 1, 2, 'foo.py')


# ------------------- /dependence_filetree -------------------

def test_query_dependence_file_tree_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_file_tree()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_file_tree_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dependence_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence_file_tree_processor',
                         return_value={'code': 0}) as mock_qf:
        v.query_dependence_file_tree()
        mock_qf.assert_called_once_with('me', 1, 2, 'uid')


# ------------------- /changesave -------------------

def test_save_edited_file_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.save_edited_file()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_save_edited_file_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'content': 'x'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.save_edited_file()
        assert result['code'] == -1


def test_save_edited_file_dependence_id_rejected(_mock_request):
    """dependence_id 存在时不允许修改源码"""
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3,
        'content': 'x', 'dependence_id': 5}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.save_edited_file()
        assert result == {"code": -1, "msg": "依赖包不能修改源码"}


def test_save_edited_file_lock_error(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'content': 'x'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.save_edited_file()
        assert result == {"code": -1, "msg": "locked"}


def test_save_edited_file_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'content': 'x'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'save_updated_file_with_content',
                         return_value={'code': 0}) as mock_save, \
            patch.object(v, 'task_file_lock'):
        v.save_edited_file()
        mock_save.assert_called_once_with('me', 2, 3, 'x')


# ------------------- /software -------------------

def test_query_software_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_software_data_route()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_software_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_software',
                         return_value={'code': 0}) as mock_qs:
        v.query_software_data_route()
        mock_qs.assert_called_once_with('me', 1)


# ------------------- /missing_files -------------------

def test_query_missing_files_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_missing_files_data_route()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_missing_files_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_missing_files',
                         return_value={'code': 0}) as mock_qm:
        v.query_missing_files_data_route()
        mock_qm.assert_called_once_with('me', 1)


# ------------------- /existing_arch -------------------

def test_query_existing_arch_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_existing_arch_info()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_existing_arch_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_existing_arch',
                         return_value={'code': 0}) as mock_qe:
        v.query_existing_arch_info()
        mock_qe.assert_called_once_with('me', 3, 1, 2)


# ------------------- /dependence -------------------

def test_query_dependence_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_data_info()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence',
                         return_value={'code': 0}) as mock_qd:
        v.query_dependence_data_info()
        mock_qd.assert_called_once_with('me', 1, 'uid')


# ------------------- /depsum -------------------

def test_query_dependence_summary_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_summary_info()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_summary_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence_summary',
                         return_value={'code': 0}) as mock_qs:
        v.query_dependence_summary_info()
        mock_qs.assert_called_once_with('me', 1, 'uid')


# ------------------- /dependence_files -------------------

def test_query_task_dependence_files_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_task_dependence_files()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_task_dependence_files_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dependence_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_user_task_dependence_files',
                         return_value={'code': 0}) as mock_qf:
        v.query_task_dependence_files()
        mock_qf.assert_called_once_with('me', 1, 2, 'uid')


# ------------------- /dependence_software -------------------

def test_query_task_dependence_software_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_task_dependence_software()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_task_dependence_software_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dependence_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence_software',
                         return_value={'code': 0}) as mock_qs:
        v.query_task_dependence_software()
        mock_qs.assert_called_once_with('me', 1, 2, 'uid')


# ------------------- /dependence_missing_files -------------------

def test_query_dependence_missing_files_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.query_dependence_missing_files_info()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_query_dependence_missing_files_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'task_id': 1, 'dependence_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'query_dependence_missing_files',
                         return_value={'code': 0}) as mock_qm:
        v.query_dependence_missing_files_info()
        mock_qm.assert_called_once_with('me', 1, 2, 'uid')


# ------------------- /dependence_existing_arch -------------------

def test_query_dependence_existing_arch_ok(_mock_request):
    """此路由不检查 session 与 user，直接转发"""
    _mock_request.get_json.return_value = {'file_id': 1, 'dependence_id': 2}
    with patch.object(v, 'query_dependence_existing_arch',
                      return_value={'code': 0}) as mock_qe:
        v.query_dependence_existing_arch_info()
        mock_qe.assert_called_once_with(1, 2)


# ------------------- /query_init_configuration -------------------

def test_query_init_configuration_ok(_mock_request):
    with patch.object(v, 'get_init_configuration',
                      return_value={'code': 0}) as mock_init:
        v.query_init_configuration()
        mock_init.assert_called_once_with('uid')


# ------------------- /check_file_exists -------------------

def test_check_file_exists_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.check_file_exists()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_check_file_exists_ok(_mock_request):
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3, 'dependence_id': 4}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v, 'check_file_exists_handler',
                         return_value={'code': 0}) as mock_chk:
        v.check_file_exists()
        mock_chk.assert_called_once_with('me', 1, 2, 3, 4)


# ------------------- /save_file_content -------------------

def test_save_file_content_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.save_file_content()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_save_file_content_lock_error(_mock_request):
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3,
        'dependence_id': 0, 'content': 'x'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.save_file_content()
        assert result == {"code": -1, "msg": "locked"}


def test_save_file_content_ok(_mock_request):
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3,
        'dependence_id': 0, 'content': 'x'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v, 'save_file_content_handler',
                         return_value={'code': 0}) as mock_save, \
            patch.object(v, 'task_file_lock'):
        v.save_file_content()
        mock_save.assert_called_once()


# ------------------- /delete -------------------

def test_delete_task_ok(_mock_request):
    _mock_request.get_json.return_value = {'task_id': 42}
    with patch.object(v, 'mark_as_deleted',
                      return_value={'code': 0}) as mock_del:
        v.delete_task()
        mock_del.assert_called_once_with(42, _mock_request)


# ------------------- /create_file_or_directory -------------------

def test_create_file_or_directory_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.create_file_or_directory()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_create_file_or_directory_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_path': '/foo'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_file_or_directory()
        assert result['code'] == -1


def test_create_file_or_directory_empty_path(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_path': ''}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_file_or_directory()
        assert result == {"code": -1, "msg": "文件路径不能为空"}


def test_create_file_or_directory_dependence_rejected(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_path': '/foo', 'dependence_id': 5}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.create_file_or_directory()
        assert result == {"code": -1, "msg": "依赖包不支持创建文件或目录"}


def test_create_file_or_directory_lock_error(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_path': '/foo'}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.create_file_or_directory()
        assert result == {"code": -1, "msg": "locked"}


def test_create_file_or_directory_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_path': '/foo', 'is_directory': False}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'create_file_or_directory_handler',
                         return_value={'code': 0}) as mock_create, \
            patch.object(v, 'task_file_lock'):
        v.create_file_or_directory()
        mock_create.assert_called_once_with('me', 'uid', 1, '/foo', False)


# ------------------- /delete_file_or_directory -------------------

def test_delete_file_or_directory_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.delete_file_or_directory()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_delete_file_or_directory_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {'dir_id': 1, 'file_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.delete_file_or_directory()
        assert result['code'] == -1


def test_delete_file_or_directory_dependence_rejected(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_id': 2, 'dependence_id': 5}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.delete_file_or_directory()
        assert result == {"code": -1, "msg": "依赖包不支持创建文件或目录"}


def test_delete_file_or_directory_lock_error(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'dir_id': 1, 'file_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.delete_file_or_directory()
        assert result == {"code": -1, "msg": "locked"}


def test_delete_file_or_directory_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {'dir_id': 1, 'file_id': 2}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'delete_file_or_directory_handler',
                         return_value={'code': 0}) as mock_del, \
            patch.object(v, 'task_file_lock'):
        v.delete_file_or_directory()
        mock_del.assert_called_once_with('me', 1, 2)


# ------------------- /update_suggestion_ignored -------------------

def test_update_suggestion_ignored_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.update_suggestion_ignored()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_update_suggestion_ignored_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_id': 2, 'change_id': 3, 'ignored': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.update_suggestion_ignored()
        assert result['code'] == -1


def test_update_suggestion_ignored_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'dir_id': 1, 'file_id': 2, 'change_id': 3, 'ignored': 1}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'update_suggestion_ignored_handler',
                         return_value={'code': 0}) as mock_upd:
        v.update_suggestion_ignored()
        mock_upd.assert_called_once_with('me', 1, 2, 3, 1)


# ------------------- /rollback_file -------------------

def test_file_rollback_no_session(_mock_request):
    with patch.dict(flask_session, {}, clear=True):
        _mock_request.get_json.return_value = {}
        result = v.file_rollback()
        assert result == {"code": -1, "msg": "Unkown user."}


def test_file_rollback_no_privilege(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'someone_else'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user):
        result = v.file_rollback()
        assert result['code'] == -1
        assert result['content'] == ''


def test_file_rollback_lock_error(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'task_file_lock') as mock_lock:
        mock_lock.return_value.__enter__.side_effect = RuntimeError("locked")
        result = v.file_rollback()
        assert result == {"code": -1, "msg": "locked"}


def test_file_rollback_ok(_mock_request):
    mock_user = MagicMock()
    mock_user.user_name = 'me'
    _mock_request.get_json.return_value = {
        'task_id': 1, 'dir_id': 2, 'file_id': 3}
    with patch.dict(flask_session, {'user_name': 'me'}, clear=True), \
            patch.object(v.UserManager, 'query_by_id', return_value=mock_user), \
            patch.object(v, 'file_rollback_handler',
                         return_value={'code': 0}) as mock_rb, \
            patch.object(v, 'task_file_lock'):
        v.file_rollback()
        mock_rb.assert_called_once_with('me', 2, 3)
