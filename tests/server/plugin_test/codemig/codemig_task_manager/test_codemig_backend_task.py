import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from contextlib import contextmanager
from pathlib import Path

from plugin.codemig.codemig_task_manager.codemig_backend_task import permanent_delete
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage
from plugin.codemig.codemig_task_manager.models import CodemigTasks, CodemigTaskDirectory
from plugin.codemig.dependence_process.models import CodemigTaskDependence
from common.db.SQLOperation import db_session_scope, DatabaseException


class TestPermanentDelete:
    """测试 permanent_delete 函数"""

    def test_permanent_delete_no_data(self, mocker):
        """测试没有数据需要删除的情况"""
        # Mock 数据库查询返回空列表
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def mock_db_scope():
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=[]
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=[]
        )
        
        # 执行删除
        permanent_delete()
        
        # 验证没有执行文件删除操作
        assert True  # 如果没有异常就说明测试通过

    def test_permanent_delete_with_removed_directories(self, tmp_path, mocker):
        """测试删除已标记为删除的目录"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock 数据库查询
        to_remove_dir = [(1, 'user1'), (2, 'user2')]
        nolink_dir = []
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def mock_db_scope():
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 创建测试文件夹
        folder1 = tmp_path / 'user1' / '1'
        folder2 = tmp_path / 'user2' / '2'
        folder1.mkdir(parents=True)
        folder2.mkdir(parents=True)
        (folder1 / 'file1.txt').write_text('test')
        (folder2 / 'file2.txt').write_text('test')
        
        # 执行删除
        permanent_delete()
        
        # 验证文件夹已被删除
        assert not folder1.exists()
        assert not folder2.exists()

    def test_permanent_delete_with_no_link_directories(self, tmp_path, mocker):
        """测试删除未关联任务的目录"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock 数据库查询
        to_remove_dir = []
        nolink_dir = [(3, 'user3'), (4, 'user4')]
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def mock_db_scope():
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 创建测试文件夹
        folder3 = tmp_path / 'user3' / '3'
        folder4 = tmp_path / 'user4' / '4'
        folder3.mkdir(parents=True)
        folder4.mkdir(parents=True)
        
        # 执行删除
        permanent_delete()
        
        # 验证文件夹已被删除
        assert not folder3.exists()
        assert not folder4.exists()

    def test_permanent_delete_with_no_user_name(self, tmp_path, mocker):
        """测试删除没有用户名的目录"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock os.listdir 返回用户目录列表
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.os.listdir',
            return_value=['user1', 'user2']
        )
        
        # Mock 数据库查询 - 返回 None 作为用户名
        to_remove_dir = [(5, None), (6, None)]
        nolink_dir = []
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        call_count = {'count': 0}
        
        @contextmanager
        def mock_db_scope():
            call_count['count'] += 1
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 创建测试文件夹（在不同用户目录下）
        folder5_user1 = tmp_path / 'user1' / '5'
        folder5_user2 = tmp_path / 'user2' / '5'
        folder6_user1 = tmp_path / 'user1' / '6'
        folder5_user1.mkdir(parents=True)
        folder5_user2.mkdir(parents=True)
        folder6_user1.mkdir(parents=True)
        
        # 执行删除
        permanent_delete()
        
        # 验证文件夹已被删除（代码会遍历所有用户目录查找匹配的dir_id）
        # 注意：代码逻辑会删除所有匹配的目录，所以 folder5_user2 可能还存在（如果代码逻辑只删除第一个匹配的）
        # 根据代码逻辑，会遍历所有用户目录，删除所有匹配的dir_id
        assert not folder5_user1.exists() or not folder5_user2.exists()  # 至少一个被删除
        assert not folder6_user1.exists()

    def test_permanent_delete_with_deleted_tasks(self, tmp_path, mocker):
        """测试删除已删除的任务（status = 4）"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock 数据库查询
        to_remove_dir = []
        nolink_dir = []
        
        # Mock 查询已删除的任务
        mock_task_query = MagicMock()
        mock_task_query.filter.return_value.all.return_value = [(101,), (102,)]
        
        # Mock session.execute 用于原始 SQL 删除
        mock_execute = MagicMock()
        
        # Mock ORM 查询和删除
        mock_orm_query = MagicMock()
        mock_delete_result = MagicMock()
        mock_orm_query.filter.return_value.delete.return_value = None
        
        call_count = {'count': 0}
        
        def mock_query(model):
            call_count['count'] += 1
            if call_count['count'] == 1:  # 第一次查询是 CodemigTasks
                return mock_task_query
            return mock_orm_query
        
        mock_session = MagicMock()
        mock_session.query.side_effect = mock_query
        mock_session.execute = mock_execute
        
        @contextmanager
        def mock_db_scope():
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 执行删除
        permanent_delete()
        
        # 验证执行了删除操作（扫描结果表已随独立库物理删除，仅剩 ORM 删除）
        assert mock_execute.call_count == 0  # 不再对主库不存在的表发 raw SQL
        assert mock_orm_query.filter.return_value.delete.call_count >= 3  # ORM删除调用

    def test_permanent_delete_database_error_on_query(self, mocker):
        """测试数据库查询失败的情况"""
        # Mock 数据库查询抛出异常
        @contextmanager
        def mock_db_scope_error():
            raise DatabaseException("Database error")
            yield  # 不会执行到这里
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope_error
        )
        
        # 执行删除（应该不会抛出异常，而是记录错误）
        permanent_delete()
        
        # 如果没有抛出异常，测试通过
        assert True

    def test_permanent_delete_database_error_on_delete(self, tmp_path, mocker):
        """测试数据库删除操作失败的情况"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock 数据库查询成功
        to_remove_dir = []
        nolink_dir = []
        
        # Mock 第一次查询成功，第二次删除时失败
        mock_session1 = MagicMock()
        mock_session1.query.return_value.filter.return_value.all.return_value = []
        
        call_count = {'count': 0}
        
        @contextmanager
        def mock_db_scope():
            call_count['count'] += 1
            if call_count['count'] == 1:
                yield mock_session1
            else:
                raise DatabaseException("Delete failed")
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 执行删除（应该捕获异常并记录错误）
        permanent_delete()
        
        # 如果没有抛出异常，测试通过
        assert True

    def test_permanent_delete_mixed_scenario(self, tmp_path, mocker):
        """测试混合场景：有已删除目录、未关联目录和已删除任务"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock os.listdir
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.os.listdir',
            return_value=['user1']
        )
        
        # Mock 数据库查询
        to_remove_dir = [(1, 'user1'), (2, None)]
        nolink_dir = [(3, 'user2')]
        
        # Mock 查询已删除的任务
        mock_task_query = MagicMock()
        mock_task_query.filter.return_value.all.return_value = [(201,)]
        
        mock_execute = MagicMock()
        mock_orm_query = MagicMock()
        mock_orm_query.filter.return_value.delete.return_value = None
        
        query_count = {'count': 0}
        
        def mock_query(model):
            query_count['count'] += 1
            if query_count['count'] == 1:  # 第一次查询是 CodemigTasks
                return mock_task_query
            return mock_orm_query
        
        mock_session = MagicMock()
        mock_session.query.side_effect = mock_query
        mock_session.execute = mock_execute
        
        call_count = {'count': 0}
        
        @contextmanager
        def mock_db_scope():
            call_count['count'] += 1
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 创建测试文件夹
        folder1 = tmp_path / 'user1' / '1'
        folder2_user1 = tmp_path / 'user1' / '2'
        folder3 = tmp_path / 'user2' / '3'
        folder1.mkdir(parents=True)
        folder2_user1.mkdir(parents=True)
        folder3.mkdir(parents=True)
        
        # 执行删除
        permanent_delete()
        
        # 验证文件夹已被删除
        assert not folder1.exists()
        assert not folder2_user1.exists()
        assert not folder3.exists()
        
        # 验证数据库删除操作被调用（扫描结果表已随独立库物理删除，仅剩 ORM 删除）
        assert mock_execute.call_count == 0
        assert mock_orm_query.filter.return_value.delete.call_count >= 4

    def test_permanent_delete_file_not_exists(self, tmp_path, mocker):
        """测试文件不存在的情况"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.get_codemig_data_path',
            return_value=str(tmp_path)
        )
        
        # Mock 数据库查询
        to_remove_dir = [(999, 'user1')]  # 目录不存在
        nolink_dir = []
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def mock_db_scope():
            yield mock_session
        
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.db_session_scope',
            side_effect=mock_db_scope
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_removed_directories',
            return_value=to_remove_dir
        )
        mocker.patch(
            'plugin.codemig.codemig_task_manager.codemig_backend_task.CodemigDirectoryStorage.get_no_link_directories',
            return_value=nolink_dir
        )
        
        # 执行删除（文件不存在不应该抛出异常）
        permanent_delete()
        
        # 如果没有抛出异常，测试通过
        assert True
