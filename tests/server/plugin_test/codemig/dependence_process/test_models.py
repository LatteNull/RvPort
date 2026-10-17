import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.dependence_process.models import (
    CodemigTaskDependence,
    DependencePackages,
    FileDependence,
    FileDependenceSuggestion,
    SoftwareDependenceSuggestion,
    DependenceExistingArchitecture,
    DependenceTask
)
from common.db.SQLOperation import DatabaseException


class TestCodemigTaskDependence:
    """测试 CodemigTaskDependence 模型"""

    @patch('plugin.codemig.dependence_process.models.CodemigTaskDependence')
    def test_get_dependencies_by_task_id_success(self, mock_model):
        """测试成功获取任务依赖"""
        mock_session = MagicMock()
        
        # Mock 查询结果
        mock_result1 = MagicMock()
        mock_result1.dependence_id = 100
        mock_result1.dependence_package = "pkg1"
        mock_result1.version = "1.0.0"
        mock_result1.status = 1
        mock_result1.fail_reason = None
        
        mock_result2 = MagicMock()
        mock_result2.dependence_id = 101
        mock_result2.dependence_package = "pkg2"
        mock_result2.version = "2.0.0"
        mock_result2.status = 1
        mock_result2.fail_reason = None
        
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_result1, mock_result2]
        mock_session.query.return_value = mock_query
        
        result = CodemigTaskDependence.get_dependencies_by_task_id(1, mock_session)
        
        assert len(result) == 2
        assert result[0] == (100, "pkg1", "1.0.0", 1, None)
        assert result[1] == (101, "pkg2", "2.0.0", 1, None)

    @patch('plugin.codemig.dependence_process.models.CodemigTaskDependence')
    def test_get_dependencies_by_task_id_empty(self, mock_model):
        """测试空结果"""
        mock_session = MagicMock()
        
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        
        result = CodemigTaskDependence.get_dependencies_by_task_id(1, mock_session)
        
        assert result == []


class TestDependencePackages:
    """测试 DependencePackages 模型"""

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_is_package_installed_found(self, mock_db_scope):
        """测试找到已安装的包"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.dependence_id = 123
        mock_session.query.return_value.filter.return_value.first.return_value = mock_result
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.is_package_installed("pkg_name", "1.0.0")
        
        assert result == 123

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_is_package_installed_not_found(self, mock_db_scope):
        """测试未找到已安装的包"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.is_package_installed("pkg_name", "1.0.0")
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_is_package_installed_database_error(self, mock_db_scope):
        """测试数据库错误"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependencePackages.is_package_installed("pkg_name", "1.0.0")
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_record_package_exists(self, mock_db_scope):
        """测试记录已存在的包"""
        mock_session = MagicMock()
        mock_existing = MagicMock()
        mock_existing.dependence_id = 456
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.record_package("pkg_name", "1.0.0", "/path", 1, None)
        
        assert result == 456

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_record_package_new(self, mock_db_scope):
        """测试记录新包"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_new_package = MagicMock()
        mock_new_package.dependence_id = 789
        
        def mock_add(obj):
            obj.dependence_id = 789
        
        mock_session.add = mock_add
        mock_session.flush = lambda: None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.record_package("pkg_name", "1.0.0", "/path", 1, None)
        
        assert result == 789

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_record_package_error(self, mock_db_scope):
        """测试记录包时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependencePackages.record_package("pkg_name", "1.0.0", "/path", 1, None)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_package_path_found(self, mock_db_scope):
        """测试找到包路径"""
        mock_session = MagicMock()
        mock_pkg = MagicMock()
        mock_pkg.dependence_package_path = "/path/to/pkg"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_pkg
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.get_package_path(123)
        
        assert result == "/path/to/pkg"

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_package_path_not_found(self, mock_db_scope):
        """测试未找到包路径"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependencePackages.get_package_path(999)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_package_path_error(self, mock_db_scope):
        """测试获取包路径时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependencePackages.get_package_path(123)
        
        assert result is None


class TestFileDependence:
    """测试 FileDependence 模型"""

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_file_path_found(self, mock_db_scope):
        """测试找到文件路径"""
        mock_session = MagicMock()
        mock_file = MagicMock()
        mock_file.file_path = "/path/to/file.py"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_file
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependence.get_file_path(1)
        
        assert result == "/path/to/file.py"

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_file_path_not_found(self, mock_db_scope):
        """测试未找到文件路径"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependence.get_file_path(999)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_file_path_error(self, mock_db_scope):
        """测试获取文件路径时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = FileDependence.get_file_path(1)
        
        assert result is None


    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_task_name_and_file_path_found(self, mock_db_scope):
        """测试找到任务名称和文件路径"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.task_name = "Test Task"
        mock_result.file_path = "/path/to/file.py"
        mock_session.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = mock_result
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependence.get_task_name_and_file_path("user1", 1, 2, 3, 4)
        
        assert result == ("Test Task", "/path/to/file.py")

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_task_name_and_file_path_not_found(self, mock_db_scope):
        """测试未找到任务名称和文件路径"""
        mock_session = MagicMock()
        mock_session.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependence.get_task_name_and_file_path("user1", 999, 2, 3, 4)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_task_name_and_file_path_error(self, mock_db_scope):
        """测试获取任务名称和文件路径时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = FileDependence.get_task_name_and_file_path("user1", 1, 2, 3, 4)
        
        assert result is None


class TestFileDependenceSuggestion:
    """测试 FileDependenceSuggestion 模型"""

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_ai_suggestion_data_found(self, mock_db_scope):
        """测试找到 AI 建议数据"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.task_name = "Test Task"
        mock_result.file_path = "/path/to/file.py"
        mock_result.suggestion_type = 0
        mock_result.start_line_number = 10
        mock_result.end_line_number = 20
        mock_result.suggestion = "Fix this code"
        
        mock_session.query.return_value.select_from.return_value.join.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = mock_result
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependenceSuggestion.get_ai_suggestion_data("user1", 1, 2, 3, 4, 5)
        
        assert result == ("Test Task", "/path/to/file.py", 0, 10, 20, "Fix this code")

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_ai_suggestion_data_not_found(self, mock_db_scope):
        """测试未找到 AI 建议数据"""
        mock_session = MagicMock()
        mock_session.query.return_value.select_from.return_value.join.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependenceSuggestion.get_ai_suggestion_data("user1", 999, 2, 3, 4, 5)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_ai_suggestion_data_error(self, mock_db_scope):
        """测试获取 AI 建议数据时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = FileDependenceSuggestion.get_ai_suggestion_data("user1", 1, 2, 3, 4, 5)
        
        assert result is None

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_all_ai_suggestion_data_found(self, mock_db_scope):
        """测试找到所有 AI 建议数据"""
        mock_session = MagicMock()
        
        mock_result1 = MagicMock()
        mock_result1.task_name = "Test Task"
        mock_result1.file_path = "/path/to/file.py"
        mock_result1.suggestion_type = 0
        mock_result1.start_line_number = 10
        mock_result1.end_line_number = 20
        mock_result1.suggestion = "Fix this code"
        
        mock_session.query.return_value.select_from.return_value.join.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = [mock_result1]
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependenceSuggestion.get_all_ai_suggestion_data("user1", 1, 2, 3, 5)
        
        assert len(result) == 1
        assert result[0] == ("Test Task", "/path/to/file.py", 0, 10, 20, "Fix this code")

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_all_ai_suggestion_data_empty(self, mock_db_scope):
        """测试未找到 AI 建议数据（返回空列表）"""
        mock_session = MagicMock()
        mock_session.query.return_value.select_from.return_value.join.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = []
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = FileDependenceSuggestion.get_all_ai_suggestion_data("user1", 999, 2, 3, 5)
        
        assert result == []

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_all_ai_suggestion_data_error(self, mock_db_scope):
        """测试获取所有 AI 建议数据时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = FileDependenceSuggestion.get_all_ai_suggestion_data("user1", 1, 2, 3, 5)
        
        assert result == []


class TestDependenceTask:
    """测试 DependenceTask 模型"""

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_bulk_insert_tasks_python_deps(self, mock_db_scope):
        """测试批量插入 Python 依赖"""
        mock_session = MagicMock()
        
        task_data_list = [
            (1, 2, "pkg1", "1.0.0"),
            (1, 2, "pkg2", "2.0.0"),
        ]
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.bulk_insert_tasks(task_data_list)
        
        assert result == (True, 2)
        assert mock_session.bulk_save_objects.called

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_bulk_insert_tasks_go_deps(self, mock_db_scope):
        """测试批量插入 Go 依赖"""
        mock_session = MagicMock()
        
        task_data_list = [
            (1, 2, "pkg1", "1.0.0", "/path/to/pkg1"),
            (1, 2, "pkg2", "2.0.0", "/path/to/pkg2"),
        ]
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.bulk_insert_tasks(task_data_list)
        
        assert result == (True, 2)

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_bulk_insert_tasks_mixed(self, mock_db_scope):
        """测试批量插入混合依赖"""
        mock_session = MagicMock()
        
        task_data_list = [
            (1, 2, "pkg1", "1.0.0"),  # Python
            (1, 2, "pkg2", "2.0.0", "/path"),  # Go
        ]
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.bulk_insert_tasks(task_data_list)
        
        assert result == (True, 2)

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_bulk_insert_tasks_error(self, mock_db_scope):
        """测试批量插入时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependenceTask.bulk_insert_tasks([(1, 2, "pkg1", "1.0.0")])
        
        assert result == (False, 0)

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_update_task_status_success(self, mock_db_scope):
        """测试更新任务状态成功"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 1
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.update_task_status(1, 2, "pkg1", "1.0.0", 2, 100)
        
        assert result is True

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_update_task_status_with_enum(self, mock_db_scope):
        """测试使用枚举更新任务状态"""
        from plugin.codemig.dependence_process.dependence_info import DepStatus
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 1
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.update_task_status(1, 2, "pkg1", "1.0.0", DepStatus.finished, 100)
        
        assert result is True

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_update_task_status_no_rows(self, mock_db_scope):
        """测试更新任务状态但没有匹配行"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 0
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.update_task_status(999, 999, "pkg1", "1.0.0", 2, 100)
        
        assert result is False

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_update_task_status_error(self, mock_db_scope):
        """测试更新任务状态时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependenceTask.update_task_status(1, 2, "pkg1", "1.0.0", 2, 100)
        
        assert result is False

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_delete_by_task_id_success(self, mock_db_scope):
        """测试删除任务依赖成功"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.delete.return_value = 5
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.delete_by_task_id(1)
        
        assert result is True

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_delete_by_task_id_error(self, mock_db_scope):
        """测试删除任务依赖时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependenceTask.delete_by_task_id(1)
        
        assert result is False

    def test_get_packages_by_task_ids_empty(self):
        """测试空任务 ID 列表"""
        result = DependenceTask.get_packages_by_task_ids([])
        
        assert result == []

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_packages_by_task_ids_success(self, mock_db_scope):
        """测试成功获取任务包"""
        mock_session = MagicMock()
        
        mock_result1 = MagicMock()
        mock_result1.task_id = 1
        mock_result1.dir_id = 2
        mock_result1.pkg = "pkg1"
        mock_result1.version = "1.0.0"
        mock_result1.local_path = None
        mock_result1.status = 0
        mock_result1.dependence_id = 100
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_result1]
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = DependenceTask.get_packages_by_task_ids([1, 2])
        
        assert len(result) == 1
        assert result[0] == (1, 2, "pkg1", "1.0.0", None, 0, 100)

    @patch('plugin.codemig.dependence_process.models.db_session_scope')
    def test_get_packages_by_task_ids_error(self, mock_db_scope):
        """测试获取任务包时出错"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = DependenceTask.get_packages_by_task_ids([1, 2])
        
        assert result is None

