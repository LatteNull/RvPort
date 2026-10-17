import pytest
from flask import Flask
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_report_manager.views import codemig_report_bp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """创建并配置 Flask 测试应用，注册 report 蓝图。"""
    _app = Flask(__name__)
    _app.config['TESTING'] = True
    _app.secret_key = 'test-secret-key'
    _app.register_blueprint(codemig_report_bp)
    return _app


@pytest.fixture
def client(app):
    """返回 Flask 测试客户端。"""
    return app.test_client()


# ---------------------------------------------------------------------------
# TestCodemigReportBlueprint - 蓝图结构与注册
# ---------------------------------------------------------------------------

class TestCodemigReportBlueprint:
    """验证 codemig_report_bp 的基本属性。"""

    def test_blueprint_name(self):
        assert codemig_report_bp.name == 'report'

    def test_blueprint_url_prefix(self):
        assert codemig_report_bp.url_prefix == '/report'

    def test_register_blueprint(self):
        app = Flask(__name__)
        app.register_blueprint(codemig_report_bp)
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert '/report/download' in rules
        assert '/report/download_patch' in rules

    def test_download_route_methods(self):
        """确保 /report/download 仅接受 POST。"""
        app = Flask(__name__)
        app.register_blueprint(codemig_report_bp)
        for rule in app.url_map.iter_rules():
            if rule.rule == '/report/download':
                assert 'POST' in rule.methods
                assert 'GET' not in rule.methods
                break

    def test_download_patch_route_methods(self):
        """确保 /report/download_patch 仅接受 POST。"""
        app = Flask(__name__)
        app.register_blueprint(codemig_report_bp)
        for rule in app.url_map.iter_rules():
            if rule.rule == '/report/download_patch':
                assert 'POST' in rule.methods
                assert 'GET' not in rule.methods
                break


# ---------------------------------------------------------------------------
# TestDownloadReportRoute - /report/download
# ---------------------------------------------------------------------------

class TestDownloadReportRoute:
    """测试 download_report 视图函数。"""

    def test_download_report_no_session_returns_error(self, client):
        """未登录时返回 code=-1。"""
        response = client.post('/report/download', json={"task_id": 1})
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == -1
        assert 'Unkown user' in data['msg']

    def test_download_report_no_session_no_json_body(self, client):
        """未登录且不发送 JSON 时仍应返回 code=-1。"""
        response = client.post('/report/download', content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == -1

    def test_download_report_get_method_not_allowed(self, client):
        """GET 方法不被路由接受，应返回 405。"""
        response = client.get('/report/download')
        assert response.status_code == 405

    @patch('plugin.codemig.codemig_report_manager.views.create_report_response')
    def test_download_report_with_session_calls_create(self, mock_create, client):
        """登录后应调用 create_report_response 并透传返回值。"""
        mock_create.return_value = {"code": 0, "msg": "ok"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download', json={"task_id": 42})
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == 'testuser'
        assert call_args[0][1] == 42

    @patch('plugin.codemig.codemig_report_manager.views.create_report_response')
    def test_download_report_passes_request_object(self, mock_create, client):
        """create_report_response 的第三个参数应是 Flask request 代理对象。"""
        mock_create.return_value = {"code": 0, "msg": "ok"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        client.post('/report/download', json={"task_id": 1})
        call_args = mock_create.call_args
        from flask.globals import request as flask_request
        assert call_args[0][2] is flask_request

    @patch('plugin.codemig.codemig_report_manager.views.create_report_response')
    def test_download_report_returns_response_directly(self, mock_create, client):
        """当 create_report_response 返回 Flask Response 对象时应直接透传。"""
        from flask import Response
        fake_response = Response("file content", mimetype="application/octet-stream")
        mock_create.return_value = fake_response
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download', json={"task_id": 1})
        assert response.status_code == 200
        assert response.data == b"file content"

    @patch('plugin.codemig.codemig_report_manager.views.create_report_response')
    def test_download_report_preserves_error_response(self, mock_create, client):
        """当 create_report_response 返回错误时应透传。"""
        mock_create.return_value = {"code": -1, "msg": "No task found"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download', json={"task_id": 999})
        data = response.get_json()
        assert data['code'] == -1
        assert data['msg'] == "No task found"

    @patch('plugin.codemig.codemig_report_manager.views.create_report_response')
    def test_download_report_extracts_task_id_from_json(self, mock_create, client):
        """task_id 应从 request JSON body 中正确提取。"""
        mock_create.return_value = {"code": 0}
        with client.session_transaction() as sess:
            sess['user_name'] = 'alice'
        client.post('/report/download', json={"task_id": 7})
        assert mock_create.call_args[0][1] == 7


# ---------------------------------------------------------------------------
# TestDownloadPatchRoute - /report/download_patch
# ---------------------------------------------------------------------------

class TestDownloadPatchRoute:
    """测试 download_patch 视图函数。"""

    def test_download_patch_no_session_returns_error(self, client):
        """未登录时返回 code=-1。"""
        response = client.post('/report/download_patch', json={"task_id": 1})
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == -1
        assert 'Unkown user' in data['msg']

    def test_download_patch_no_session_no_json_body(self, client):
        """未登录且不发送 JSON 时仍应返回 code=-1。"""
        response = client.post('/report/download_patch', content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == -1

    def test_download_patch_get_method_not_allowed(self, client):
        """GET 方法不被路由接受，应返回 405。"""
        response = client.get('/report/download_patch')
        assert response.status_code == 405

    @patch('plugin.codemig.codemig_report_manager.views.create_patch_response')
    def test_download_patch_with_session_calls_create(self, mock_create, client):
        """登录后应调用 create_patch_response 并透传返回值。"""
        mock_create.return_value = {"code": 0, "msg": "ok"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download_patch', json={"task_id": 42})
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == 0
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == 'testuser'
        assert call_args[0][1] == 42

    @patch('plugin.codemig.codemig_report_manager.views.create_patch_response')
    def test_download_patch_passes_request_object(self, mock_create, client):
        """create_patch_response 的第三个参数应是 Flask request 代理对象。"""
        mock_create.return_value = {"code": 0, "msg": "ok"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        client.post('/report/download_patch', json={"task_id": 1})
        call_args = mock_create.call_args
        from flask.globals import request as flask_request
        assert call_args[0][2] is flask_request

    @patch('plugin.codemig.codemig_report_manager.views.create_patch_response')
    def test_download_patch_returns_response_directly(self, mock_create, client):
        """当 create_patch_response 返回 Flask Response 对象时应直接透传。"""
        from flask import Response
        fake_response = Response(b"patch content", mimetype="text/plain")
        mock_create.return_value = fake_response
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download_patch', json={"task_id": 1})
        assert response.status_code == 200
        assert response.data == b"patch content"

    @patch('plugin.codemig.codemig_report_manager.views.create_patch_response')
    def test_download_patch_preserves_error_response(self, mock_create, client):
        """当 create_patch_response 返回错误时应透传。"""
        mock_create.return_value = {"code": 1, "msg": "Generate patch failed: Task not found"}
        with client.session_transaction() as sess:
            sess['user_name'] = 'testuser'
        response = client.post('/report/download_patch', json={"task_id": 999})
        data = response.get_json()
        assert data['code'] == 1
        assert "Generate patch failed" in data['msg']

    @patch('plugin.codemig.codemig_report_manager.views.create_patch_response')
    def test_download_patch_extracts_task_id_from_json(self, mock_create, client):
        """task_id 应从 request JSON body 中正确提取。"""
        mock_create.return_value = {"code": 0}
        with client.session_transaction() as sess:
            sess['user_name'] = 'bob'
        client.post('/report/download_patch', json={"task_id": 99})
        assert mock_create.call_args[0][1] == 99
