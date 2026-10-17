import pytest
from flask import Flask
from unittest.mock import patch

from plugin.codemig.codemig_bp.bp import codemig_bp


class TestCodemigBp:
    """测试 codemig_bp 蓝图注册"""

    def test_blueprint_name(self):
        assert codemig_bp.name == 'codemig'

    def test_blueprint_url_prefix(self):
        assert codemig_bp.url_prefix == '/codemig'

    def test_can_register_on_app(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(codemig_bp)
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert any('/codemig/' in r for r in rules)

    def test_sub_blueprints_registered(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(codemig_bp)
        names = [bp.name for bp in app.blueprints.values()]
        assert 'dir' in names or 'codemig.dir' in names
        assert 'task' in names or 'codemig.task' in names
        assert 'report' in names or 'codemig.report' in names


class TestGetCodemigVersion:
    """测试 /codemig/version 路由"""

    @pytest.fixture
    def client(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(codemig_bp)
        return app.test_client()

    @patch('plugin.codemig.codemig_bp.bp._get_codemig_version', return_value="1.2.3")
    def test_returns_version_in_data(self, mock_ver, client):
        """正常请求：返回 code=0, data.version"""
        resp = client.get('/codemig/version')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 0
        assert body["msg"] == "ok"
        assert body["data"]["version"] == "1.2.3"

    @patch('plugin.codemig.codemig_bp.bp._get_codemig_version', return_value="")
    def test_returns_empty_version(self, mock_ver, client):
        """空版本号：仍正常返回，仅 data.version 为空串"""
        resp = client.get('/codemig/version')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["code"] == 0
        assert body["data"]["version"] == ""

    @patch('plugin.codemig.codemig_bp.bp._get_codemig_version', side_effect=Exception("ver err"))
    def test_version_lookup_exception(self, mock_ver, client):
        """版本查询抛异常时，路由未捕获会 500"""
        resp = client.get('/codemig/version')
        assert resp.status_code == 500

