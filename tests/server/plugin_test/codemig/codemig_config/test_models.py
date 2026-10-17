import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_config.models import UserConfiguration


class TestUserConfigurationModel:

    def test_tablename(self):
        assert UserConfiguration.__tablename__ == 'user_configuration'

    def test_has_columns(self):
        columns = [c.name for c in UserConfiguration.__table__.columns]
        assert 'user_id' in columns
        assert 'configuration_id' in columns
        assert 'python_interpreter' in columns
        assert 'python_image_source' in columns
        assert 'go_install_path' in columns
        assert 'go_environment' in columns
        assert 'create_at' in columns

    def test_primary_key(self):
        pk_columns = [c.name for c in UserConfiguration.__table__.primary_key.columns]
        assert 'configuration_id' in pk_columns

    def test_column_count(self):
        columns = list(UserConfiguration.__table__.columns)
        assert len(columns) == 7

    def test_user_id_not_nullable(self):
        col = UserConfiguration.__table__.columns['user_id']
        assert col.nullable is False

    def test_configuration_id_autoincrement(self):
        col = UserConfiguration.__table__.columns['configuration_id']
        assert col.autoincrement is True

    def test_user_id_is_string(self):
        col = UserConfiguration.__table__.columns['user_id']
        assert col.type.python_type is str

    def test_configuration_id_is_integer(self):
        col = UserConfiguration.__table__.columns['configuration_id']
        assert col.type.python_type is int

    def test_python_interpreter_is_string(self):
        col = UserConfiguration.__table__.columns['python_interpreter']
        assert col.type.python_type is str

    def test_python_image_source_is_string(self):
        col = UserConfiguration.__table__.columns['python_image_source']
        assert col.type.python_type is str

    def test_go_install_path_is_string(self):
        col = UserConfiguration.__table__.columns['go_install_path']
        assert col.type.python_type is str

    def test_go_environment_is_string(self):
        col = UserConfiguration.__table__.columns['go_environment']
        assert col.type.python_type is str

    def test_create_at_is_datetime(self):
        from datetime import datetime
        col = UserConfiguration.__table__.columns['create_at']
        assert col.type.python_type is datetime

    def test_python_interpreter_nullable(self):
        col = UserConfiguration.__table__.columns['python_interpreter']
        assert col.nullable is True

    def test_python_image_source_nullable(self):
        col = UserConfiguration.__table__.columns['python_image_source']
        assert col.nullable is True

    def test_go_install_path_nullable(self):
        col = UserConfiguration.__table__.columns['go_install_path']
        assert col.nullable is True

    def test_go_environment_nullable(self):
        col = UserConfiguration.__table__.columns['go_environment']
        assert col.nullable is True

    def test_extend_existing(self):
        assert UserConfiguration.__table_args__.get('extend_existing') is True


class TestUserConfigurationQuery:
    """测试 UserConfiguration.query_user_configuration 方法"""
    
    @patch('plugin.codemig.codemig_config.models.db_session_scope')
    def test_query_success_with_configuration(self, mock_session_scope):
        """测试成功查询到配置"""
        # Mock session and config
        mock_session = MagicMock()
        mock_config = MagicMock()
        mock_config.user_id = 'user123'
        mock_config.configuration_id = 456
        mock_config.python_interpreter = '/usr/bin/python3'
        mock_config.python_image_source = 'https://pypi.org'
        mock_config.go_install_path = '/usr/local/go'
        mock_config.go_environment = '/etc/go.env'
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        status, configuration = UserConfiguration.query_user_configuration('user123')
        
        assert status is True
        assert configuration is not None
        assert configuration[0] == 'user123'
        assert configuration[1] == 456
        assert configuration[2] == '/usr/bin/python3'
        assert configuration[3] == 'https://pypi.org'
        assert configuration[4] == '/usr/local/go'
        assert configuration[5] == '/etc/go.env'
    
    @patch('plugin.codemig.codemig_config.models.db_session_scope')
    def test_query_success_no_configuration(self, mock_session_scope):
        """测试查询但没有找到配置"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        status, configuration = UserConfiguration.query_user_configuration('nonexistent')
        
        assert status is True
        assert configuration is None
    
    @patch('plugin.codemig.codemig_config.models.db_session_scope')
    def test_query_database_exception(self, mock_session_scope):
        """测试数据库异常"""
        from common.db.SQLOperation import DatabaseException
        
        mock_session = MagicMock()
        mock_session.query.side_effect = DatabaseException("DB error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        status, configuration = UserConfiguration.query_user_configuration('user123')
        
        assert status is False
        assert configuration is None
    
    @patch('plugin.codemig.codemig_config.models.db_session_scope')
    def test_query_os_error(self, mock_session_scope):
        """测试OS错误"""
        mock_session = MagicMock()
        mock_session.query.side_effect = OSError("OS error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        status, configuration = UserConfiguration.query_user_configuration('user123')
        
        assert status is False
        assert configuration is None
    
    @patch('plugin.codemig.codemig_config.models.db_session_scope')
    def test_query_io_error(self, mock_session_scope):
        """测试IO错误"""
        mock_session = MagicMock()
        mock_session.query.side_effect = IOError("IO error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        status, configuration = UserConfiguration.query_user_configuration('user123')
        
        assert status is False
        assert configuration is None
