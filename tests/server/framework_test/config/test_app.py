import os
import sys
import json

import pytest
from unittest.mock import patch, MagicMock

TEST_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if TEST_DIR not in sys.path:
    sys.path.append(TEST_DIR)


class TestInitDb:
    """测试 init_db 函数"""

    @patch('app.OperationLog')
    @patch('app.SysConfig')
    @patch('app.UserManager')
    def test_init_db_calls_all(self, mock_user_mgr, mock_sys_config, mock_op_log):
        mock_user_mgr.init_default_user = MagicMock()
        mock_sys_config.list_all = MagicMock()
        mock_op_log.del_expire_log = MagicMock()

        from app import init_db
        init_db()

        mock_user_mgr.init_default_user.assert_called_once()
        mock_sys_config.list_all.assert_called_once()
        mock_op_log.del_expire_log.assert_called_once()


class TestListRoutes:
    """测试 list_routes 函数"""

    def test_list_routes_prints_output(self, capsys):
        from flask import Flask
        from app import list_routes

        app = Flask('test')
        @app.route('/test_route', methods=['GET'])
        def dummy():
            return 'ok'

        list_routes(app)
        captured = capsys.readouterr()
        assert 'test_route' in captured.out
        assert 'GET' in captured.out


class TestInitBackgroundProcess:
    """测试 init_background_process 函数"""

    @patch('app.multiprocessing.Process')
    def test_starts_daemon_process(self, mock_process_cls):
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        from app import init_background_process
        init_background_process()

        mock_process_cls.assert_called_once()
        mock_process.daemon = True
        mock_process.start.assert_called_once()


class TestInit:
    """测试 init 函数"""

    @patch('app.init_background_process')
    @patch('app.load_ai_magic_values')
    @patch('app.init_plugin')
    @patch('app.init_db')
    def test_init_with_no_test_config(self, mock_db, mock_plugin,
                                       mock_ai, mock_bg):
        from app import init
        init(None)

        mock_db.assert_called_once()
        mock_plugin.assert_called_once()
        mock_bg.assert_called_once()
        mock_ai.assert_called_once()

    @patch('app.init_background_process')
    @patch('app.load_ai_magic_values')
    @patch('app.init_plugin')
    @patch('app.init_db')
    def test_init_with_test_config_skips_bg(self, mock_db, mock_plugin,
                                             mock_ai, mock_bg):
        from app import init
        init({'test': True})

        mock_db.assert_called_once()
        mock_plugin.assert_called_once()
        mock_bg.assert_not_called()
        mock_ai.assert_not_called()


class TestCreateApp:
    """测试 create_app 函数"""

    @patch('app.init')
    @patch('app.static_bp', MagicMock())
    @patch('app.action_bp', MagicMock())
    def test_create_app_with_test_config(self, mock_init):
        from app import create_app, DB_INFO
        test_config = {'TESTING': True, 'DEBUG': True}
        app = create_app('test_key', test_config=test_config)
        assert app is not None
        assert app.secret_key == 'test_key'
        mock_init.assert_called_once_with(test_config)

    @patch('app.init')
    @patch('app.static_bp', MagicMock())
    @patch('app.action_bp', MagicMock())
    def test_create_app_with_db_file(self, mock_init):
        from app import create_app, DB_INFO
        test_config = {'db_file': '/tmp/test.db', 'DEBUG': True}
        app = create_app('key', test_config=test_config)
        assert DB_INFO.file == '/tmp/test.db'

    @patch('app.init')
    @patch('app.action_bp', MagicMock())
    def test_create_app_debug_registers_static_bp(self, mock_init):
        from app import create_app
        test_config = {'DEBUG': True}
        app = create_app('key', test_config=test_config)
        assert 'static' in app.blueprints

    @patch('app.init')
    @patch('app.static_bp', MagicMock())
    @patch('app.action_bp', MagicMock())
    def test_create_app_non_debug_sets_secure_cookies(self, mock_init):
        from app import create_app
        test_config = {'DEBUG': False}
        app = create_app('key', test_config=test_config)
        assert app.config.get('SESSION_COOKIE_SECURE') is True
        assert app.config.get('SESSION_COOKIE_HTTPONLY') is True
        assert app.config.get('SESSION_COOKIE_SAMESITE') == 'Lax'
