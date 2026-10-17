import pytest
import json
from unittest.mock import patch, mock_open, MagicMock

from plugin.codemig.codemig_config.config import ConfigManager


@pytest.fixture(autouse=True)
def reset_singleton():
    yield
    ConfigManager._instance = None
    ConfigManager._initialized = False


class TestConfigManagerSingleton:
    def test_two_instances_are_the_same(self):
        with patch('builtins.open', mock_open(read_data='{}')), \
             patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root'), \
             patch('os.path.join', return_value='/fake/root/server/config.json'):
            a = ConfigManager()
            b = ConfigManager()
            assert a is b

    def test_new_creates_only_one_instance(self):
        with patch('builtins.open', mock_open(read_data='{}')), \
             patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root'), \
             patch('os.path.join', return_value='/fake/root/server/config.json'):
            inst1 = ConfigManager()
            inst2 = ConfigManager()
            assert inst1 is inst2
            assert ConfigManager._instance is inst1


class TestConfigManagerInit:
    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    @patch('builtins.open', mock_open(read_data='{"enable_dependence": "True"}'))
    def test_init_enable_true(self, mock_join):
        mgr = ConfigManager()
        assert mgr.enable_dependence is True

    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    @patch('builtins.open', mock_open(read_data='{"enable_dependence": "False"}'))
    def test_init_enable_false(self, mock_join):
        mgr = ConfigManager()
        assert mgr.enable_dependence is False

    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    def test_init_file_not_found(self, mock_join, capsys):
        with patch('builtins.open', side_effect=FileNotFoundError("no such file")):
            mgr = ConfigManager()
        assert mgr.enable_dependence is False
        captured = capsys.readouterr()
        assert "警告" in captured.out

    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    def test_init_json_decode_error(self, mock_join, capsys):
        with patch('builtins.open', mock_open(read_data='invalid json')):
            mgr = ConfigManager()
        assert mgr.enable_dependence is False
        captured = capsys.readouterr()
        assert "错误" in captured.out


class TestConfigManagerGetSet:
    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    @patch('builtins.open', mock_open(read_data='{}'))
    def test_set_and_get_enable_dependence(self, mock_join):
        ConfigManager.set_enable_dependence(True)
        assert ConfigManager.get_enable_dependence() is True
        ConfigManager.set_enable_dependence(False)
        assert ConfigManager.get_enable_dependence() is False

    @patch('os.path.join', return_value='/fake/root/server/config.json')
    @patch('plugin.codemig.codemig_config.config.ROOT_PATH', '/fake/root')
    @patch('builtins.open', mock_open(read_data='{"enable_dependence": "True"}'))
    def test_get_enable_dependence_returns_bool(self, mock_join):
        result = ConfigManager.get_enable_dependence()
        assert isinstance(result, bool)
