import sys
import types

import pytest
from unittest.mock import patch, MagicMock


def _setup_gunicorn_mock():
    """确保 gunicorn 模块已被 mock，这样 main.py 可以被导入。"""
    if 'gunicorn' in sys.modules and isinstance(sys.modules.get('gunicorn'), types.ModuleType):
        gm = sys.modules['gunicorn']
        if hasattr(gm, 'app') and hasattr(gm.app, 'base') and hasattr(gm.app.base, 'BaseApplication'):
            return

    mock_gunicorn = types.ModuleType('gunicorn')
    mock_gunicorn.app = types.ModuleType('gunicorn.app')
    mock_gunicorn.app.base = types.ModuleType('gunicorn.app.base')

    class MockBaseApplication:
        def __init__(self):
            pass

    mock_gunicorn.app.base.BaseApplication = MockBaseApplication

    sys.modules['gunicorn'] = mock_gunicorn
    sys.modules['gunicorn.app'] = mock_gunicorn.app
    sys.modules['gunicorn.app.base'] = mock_gunicorn.app.base

    # 如果 main 已经被加载过且用了旧的 gunicorn，需要重载
    if 'main' in sys.modules:
        del sys.modules['main']


_setup_gunicorn_mock()
from main import StandaloneApplication


class TestStandaloneApplication:
    """测试 StandaloneApplication 类"""

    def test_load_returns_application(self):
        mock_app = MagicMock()
        sa = StandaloneApplication.__new__(StandaloneApplication)
        sa.application = mock_app
        sa.options = {}
        sa.cfg = MagicMock()
        sa.cfg.settings = {}
        result = sa.load()
        assert result is mock_app

    def test_load_config_sets_values(self):
        mock_app = MagicMock()
        sa = StandaloneApplication.__new__(StandaloneApplication)
        sa.application = mock_app
        sa.options = {'bind': '0.0.0.0:8080', 'workers': 1}
        sa.cfg = MagicMock()
        sa.cfg.settings = {'bind': MagicMock(), 'workers': MagicMock()}

        sa.load_config()
        assert sa.cfg.set.call_count == 2

    def test_load_config_ignores_none_values(self):
        mock_app = MagicMock()
        sa = StandaloneApplication.__new__(StandaloneApplication)
        sa.application = mock_app
        sa.options = {'bind': '0.0.0.0:8080', 'workers': None}
        sa.cfg = MagicMock()
        sa.cfg.settings = {'bind': MagicMock(), 'workers': MagicMock()}

        sa.load_config()
        assert sa.cfg.set.call_count == 1

    def test_load_config_empty_options(self):
        mock_app = MagicMock()
        sa = StandaloneApplication.__new__(StandaloneApplication)
        sa.application = mock_app
        sa.options = {}
        sa.cfg = MagicMock()
        sa.cfg.settings = {'bind': MagicMock()}

        sa.load_config()
        sa.cfg.set.assert_not_called()

    def test_load_config_ignores_unknown_settings(self):
        mock_app = MagicMock()
        sa = StandaloneApplication.__new__(StandaloneApplication)
        sa.application = mock_app
        sa.options = {'bind': '0.0.0.0:8080', 'custom_option': 'value'}
        sa.cfg = MagicMock()
        sa.cfg.settings = {'bind': MagicMock()}

        sa.load_config()
        assert sa.cfg.set.call_count == 1

    def test_init_with_options(self):
        sa = StandaloneApplication(mock_app := MagicMock(), {'bind': '0.0.0.0:9090'})
        assert sa.application is mock_app
        assert sa.options == {'bind': '0.0.0.0:9090'}

    def test_init_default_options(self):
        sa = StandaloneApplication(mock_app := MagicMock())
        assert sa.application is mock_app
        assert sa.options == {}

    def test_init_none_options(self):
        sa = StandaloneApplication(MagicMock(), None)
        assert sa.options == {}
