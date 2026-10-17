import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage


class TestCodemigDirectoryStorageModel:

    def test_tablename(self):
        assert CodemigDirectoryStorage.__tablename__ == 'codemig_directory_storage'

    def test_has_columns(self):
        columns = [c.name for c in CodemigDirectoryStorage.__table__.columns]
        assert 'user_id' in columns
        assert 'dir_id' in columns
        assert 'has_linked_task' in columns
        assert 'has_removed' in columns
        assert 'created_at' in columns

    def test_primary_key(self):
        pk_columns = [c.name for c in CodemigDirectoryStorage.__table__.primary_key.columns]
        assert 'dir_id' in pk_columns

    def test_column_count(self):
        columns = list(CodemigDirectoryStorage.__table__.columns)
        assert len(columns) == 5

    def test_user_id_not_nullable(self):
        col = CodemigDirectoryStorage.__table__.columns['user_id']
        assert col.nullable is False

    def test_has_linked_task_not_nullable(self):
        col = CodemigDirectoryStorage.__table__.columns['has_linked_task']
        assert col.nullable is False

    def test_has_removed_not_nullable(self):
        col = CodemigDirectoryStorage.__table__.columns['has_removed']
        assert col.nullable is False

    def test_has_linked_task_default(self):
        col = CodemigDirectoryStorage.__table__.columns['has_linked_task']
        assert col.default is not None
        assert col.default.arg == 0

    def test_has_removed_default(self):
        col = CodemigDirectoryStorage.__table__.columns['has_removed']
        assert col.default is not None
        assert col.default.arg == 0

    def test_dir_id_autoincrement(self):
        col = CodemigDirectoryStorage.__table__.columns['dir_id']
        assert col.autoincrement is True

    def test_user_id_is_string(self):
        col = CodemigDirectoryStorage.__table__.columns['user_id']
        assert col.type.python_type is str

    def test_dir_id_is_integer(self):
        col = CodemigDirectoryStorage.__table__.columns['dir_id']
        assert col.type.python_type is int

    def test_created_at_is_datetime(self):
        from datetime import datetime
        col = CodemigDirectoryStorage.__table__.columns['created_at']
        assert col.type.python_type is datetime

    def test_has_check_constraints(self):
        constraint_names = [
            ck.name for ck in CodemigDirectoryStorage.__table__.constraints
            if hasattr(ck, 'name')
        ]
        assert 'ck_codemig_directory_storage_has_linked_task' in constraint_names
        assert 'ck_codemig_directory_storage_has_removed' in constraint_names


class TestCodemigDirectoryStorageMethods:
    """测试 CodemigDirectoryStorage 的静态方法"""
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_insert_directory_success(self, mock_session_scope):
        """测试成功插入目录"""
        mock_session = MagicMock()
        new_dir = MagicMock()
        new_dir.dir_id = 123
        
        # Mock the add and flush operations
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()
        
        # Mock the context manager
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock the constructor to return our mock directory
        with patch.object(CodemigDirectoryStorage, '__init__', return_value=None):
            with patch.object(CodemigDirectoryStorage, 'dir_id', 123, create=True):
                dir_id = CodemigDirectoryStorage.insert_directory('user123')
                
                assert dir_id == 123
                mock_session.add.assert_called_once()
                mock_session.flush.assert_called_once()
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_insert_directory_failure(self, mock_session_scope):
        """测试插入目录失败"""
        from common.db.SQLOperation import DatabaseException
        
        mock_session = MagicMock()
        mock_session.add.side_effect = DatabaseException("DB error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        dir_id = CodemigDirectoryStorage.insert_directory('user123')
        
        assert dir_id is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_mark_as_removed_success(self, mock_session_scope):
        """测试成功标记为已删除"""
        mock_session = MagicMock()
        mock_directory = MagicMock()
        mock_directory.has_removed = 0
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_directory
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.mark_as_removed(123)
        
        assert result is True
        assert mock_directory.has_removed == 1
        # Session should auto-commit
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_mark_as_removed_not_found(self, mock_session_scope):
        """测试标记不存在的目录"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.mark_as_removed(999)
        
        assert result is False
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_mark_as_removed_database_error(self, mock_session_scope):
        """测试数据库错误"""
        from common.db.SQLOperation import DatabaseException
        
        mock_session = MagicMock()
        mock_session.query.side_effect = DatabaseException("DB error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.mark_as_removed(123)
        
        assert result is False
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_removed_directories_with_session(self, mock_session_scope):
        """测试获取已删除目录（提供session）"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1, 'user1'), (2, 'user2')]
        mock_session.execute.return_value = mock_result
        
        result = CodemigDirectoryStorage.get_removed_directories(mock_session)
        
        assert result == [(1, 'user1'), (2, 'user2')]
        mock_session.execute.assert_called_once()
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_removed_directories_without_session(self, mock_session_scope):
        """测试获取已删除目录（不提供session）"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(3, 'user3')]
        mock_session.execute.return_value = mock_result
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_removed_directories()
        
        assert result == [(3, 'user3')]
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_removed_directories_failure(self, mock_session_scope):
        """测试获取已删除目录失败"""
        from common.db.SQLOperation import DatabaseException
        
        mock_session = MagicMock()
        mock_session.execute.side_effect = DatabaseException("DB error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_removed_directories()
        
        assert result is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_no_link_directories_with_session(self, mock_session_scope):
        """测试获取未关联任务的目录（提供session）"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(4, 'user4'), (5, 'user5')]
        mock_session.execute.return_value = mock_result
        
        result = CodemigDirectoryStorage.get_no_link_directories(mock_session)
        
        assert result == [(4, 'user4'), (5, 'user5')]
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_no_link_directories_without_session(self, mock_session_scope):
        """测试获取未关联任务的目录（不提供session）"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(6, 'user6')]
        mock_session.execute.return_value = mock_result
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_no_link_directories()
        
        assert result == [(6, 'user6')]
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_no_link_directories_failure(self, mock_session_scope):
        """测试获取未关联任务的目录失败"""
        from common.db.SQLOperation import DatabaseException
        
        mock_session = MagicMock()
        mock_session.execute.side_effect = DatabaseException("DB error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_no_link_directories()
        
        assert result is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_insert_directory_os_error(self, mock_session_scope):
        """测试OS错误"""
        mock_session = MagicMock()
        mock_session.add.side_effect = OSError("OS error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        dir_id = CodemigDirectoryStorage.insert_directory('user123')
        
        assert dir_id is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_insert_directory_io_error(self, mock_session_scope):
        """测试IO错误"""
        mock_session = MagicMock()
        mock_session.add.side_effect = IOError("IO error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        dir_id = CodemigDirectoryStorage.insert_directory('user123')
        
        assert dir_id is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_mark_as_removed_os_error(self, mock_session_scope):
        """测试OS错误"""
        mock_session = MagicMock()
        mock_session.query.side_effect = OSError("OS error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.mark_as_removed(123)
        
        assert result is False
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_mark_as_removed_io_error(self, mock_session_scope):
        """测试IO错误"""
        mock_session = MagicMock()
        mock_session.query.side_effect = IOError("IO error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.mark_as_removed(123)
        
        assert result is False
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_removed_directories_os_error(self, mock_session_scope):
        """测试OS错误"""
        mock_session = MagicMock()
        mock_session.execute.side_effect = OSError("OS error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_removed_directories()
        
        assert result is None
    
    @patch('plugin.codemig.codemig_dir_manager.models.db_session_scope')
    def test_get_no_link_directories_os_error(self, mock_session_scope):
        """测试OS错误"""
        mock_session = MagicMock()
        mock_session.execute.side_effect = OSError("OS error")
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        result = CodemigDirectoryStorage.get_no_link_directories()
        
        assert result is None
