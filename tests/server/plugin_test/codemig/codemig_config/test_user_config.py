import os
import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_config.user_config import (
    get_init_configuration,
    find_executable_path,
)


class TestGetInitConfiguration:
    """测试 get_init_configuration 函数"""

    @patch('plugin.codemig.codemig_config.user_config.ConfigManager.get_enable_dependence',
           return_value=False)
    def test_dependence_disabled(self, _):
        result = get_init_configuration('user_123')
        assert result['code'] == 0
        assert result['data']['enable'] is False
        assert result['data']['python_interpreter'] == ''
        assert result['data']['go_install_path'] == ''

    @patch('plugin.codemig.codemig_config.user_config.UserConfiguration.query_user_configuration',
           return_value=(False, None))
    @patch('plugin.codemig.codemig_config.user_config.ConfigManager.get_enable_dependence',
           return_value=True)
    def test_query_failure(self, _, mock_query):
        result = get_init_configuration('user_123')
        assert result['code'] == -1
        assert 'failure' in result['msg']

    @patch('plugin.codemig.codemig_config.user_config.UserConfiguration.query_user_configuration',
           return_value=(True, None))
    @patch('plugin.codemig.codemig_config.user_config.ConfigManager.get_enable_dependence',
           return_value=True)
    @patch('plugin.codemig.codemig_config.user_config.find_executable_path')
    def test_no_config_returns_defaults(self, mock_find, _, mock_query):
        mock_find.side_effect = lambda name: f'/usr/bin/{name}' if name == 'python' else '/usr/local/go/bin/go'

        result = get_init_configuration('user_123')
        assert result['code'] == 0
        assert result['data']['enable'] is True
        assert result['data']['python_interpreter'] is not None
        assert result['data']['go_install_path'] is not None

    @patch('plugin.codemig.codemig_config.user_config.UserConfiguration.query_user_configuration',
           return_value=(True, ('user_123', 1, '/usr/bin/python3', 'https://pypi.org',
                                '/usr/local/go', 'GO_ENV=test')))
    @patch('plugin.codemig.codemig_config.user_config.ConfigManager.get_enable_dependence',
           return_value=True)
    def test_with_existing_config(self, _, mock_query):
        result = get_init_configuration('user_123')
        assert result['code'] == 0
        assert result['data']['python_interpreter'] == '/usr/bin/python3'
        assert result['data']['python_image_source'] == 'https://pypi.org'
        assert result['data']['go_install_path'] == '/usr/local/go'
        assert result['data']['go_environment'] == 'GO_ENV=test'
        assert result['data']['enable'] is True

    @patch('plugin.codemig.codemig_config.user_config.UserConfiguration.query_user_configuration',
           return_value=(True, ('user_123', 1, None, None, None, None)))
    @patch('plugin.codemig.codemig_config.user_config.ConfigManager.get_enable_dependence',
           return_value=True)
    @patch('plugin.codemig.codemig_config.user_config.find_executable_path',
           return_value='/usr/bin/python')
    def test_with_null_config_falls_back(self, mock_find, _, mock_query):
        result = get_init_configuration('user_123')
        assert result['code'] == 0
        assert result['data']['python_interpreter'] == '/usr/bin/python'


class TestFindExecutablePath:
    """测试 find_executable_path 函数"""

    def test_find_existing_executable(self):
        result = find_executable_path('python3')
        if result is not None:
            assert 'python3' in result or 'python' in result

    def test_find_nonexistent_executable(self):
        result = find_executable_path('nonexistent_command_xyz_12345')
        assert result is None

    @patch('plugin.codemig.codemig_config.user_config.subprocess.run')
    def test_timeout_handling(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=5)
        result = find_executable_path('test')
        assert result is None

    @patch('plugin.codemig.codemig_config.user_config.subprocess.run')
    def test_file_not_found_handling(self, mock_run):
        mock_run.side_effect = FileNotFoundError("not found")
        result = find_executable_path('test')
        assert result is None
