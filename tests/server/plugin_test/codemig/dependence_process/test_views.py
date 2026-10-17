import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.dependence_process.views import (
    query_dependence_sql,
    query_dependence_sql_summary,
    create_dependence_data,
    query_dependence,
    query_dependence_summary
)
from common.db.SQLOperation import DatabaseException


class TestQueryDependenceSql:
    """测试 query_dependence_sql 函数"""

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_success(self, mock_db_scope):
        """测试成功查询依赖信息"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 1
        mock_task.python_interpreter = "/usr/bin/python3"
        mock_task.python_image_source = "source1"
        mock_task.go_install_path = "/usr/bin/go"
        mock_task.go_environment = "env1"
        mock_task.dependence_status = 2
        mock_task.fail_reason = None
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql("user1", 1, "user_id_1")
        
        assert result[0] is True
        assert result[1][0] == 1  # is_scan_dependence
        assert result[1][1] == "/usr/bin/python3"  # python_interpreter
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_task_not_found(self, mock_db_scope):
        """测试任务不存在"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql("user1", 999, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "task not found"

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_no_dependence_scan(self, mock_db_scope):
        """测试未扫描依赖"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 0
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql("user1", 1, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "task didn't scan dependence"

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_processing_status(self, mock_db_scope):
        """测试处理中的状态（dependence_status < 2）"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 1
        mock_task.python_interpreter = "/usr/bin/python3"
        mock_task.python_image_source = "source1"
        mock_task.go_install_path = "/usr/bin/go"
        mock_task.go_environment = "env1"
        mock_task.dependence_status = 1  # 处理中
        mock_task.fail_reason = None
        
        mock_count_result = MagicMock()
        mock_count_result.total_count = 10
        mock_count_result.unfinished_count = 3
        
        # 第一次调用返回 task，第二次调用返回 count_result
        mock_query_instance = MagicMock()
        mock_query_instance.filter.return_value.first.return_value = mock_task
        mock_query_instance_2 = MagicMock()
        mock_query_instance_2.filter.return_value.first.return_value = mock_count_result
        
        call_counter = {'count': 0}
        
        def query_side_effect(*args, **kwargs):
            call_counter['count'] += 1
            if call_counter['count'] == 1:
                return mock_query_instance
            else:
                return mock_query_instance_2
        
        mock_session.query.side_effect = query_side_effect
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql("user1", 1, "user_id_1")
        
        assert result[0] is True
        assert result[2] == {'total': 10, 'processing': 3}

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_database_error(self, mock_db_scope):
        """测试数据库错误"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = query_dependence_sql("user1", 1, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "Database Error"


class TestQueryDependenceSqlSummary:
    """测试 query_dependence_sql_summary 函数"""

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_summary_success(self, mock_db_scope):
        """测试成功获取摘要"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 1
        
        mock_count_result = MagicMock()
        mock_count_result.total_count = 15
        mock_count_result.unfinished_count = 2
        
        # 第一次调用返回 task，第二次调用返回 count_result
        mock_query_instance = MagicMock()
        mock_query_instance.filter.return_value.first.return_value = mock_task
        mock_query_instance_2 = MagicMock()
        mock_query_instance_2.filter.return_value.first.return_value = mock_count_result
        
        call_counter = {'count': 0}
        
        def query_side_effect(*args, **kwargs):
            call_counter['count'] += 1
            if call_counter['count'] == 1:
                return mock_query_instance
            else:
                return mock_query_instance_2
        
        mock_session.query.side_effect = query_side_effect
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql_summary("user1", 1, "user_id_1")
        
        assert result[0] is True
        assert result[1] == 15
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_summary_task_not_found(self, mock_db_scope):
        """测试任务不存在"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql_summary("user1", 999, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "task not found"

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_summary_zero_counts(self, mock_db_scope):
        """测试零计数"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 1
        
        mock_count_result = MagicMock()
        mock_count_result.total_count = 0
        mock_count_result.unfinished_count = 0
        
        # 第一次调用返回 task，第二次调用返回 count_result
        mock_query_instance = MagicMock()
        mock_query_instance.filter.return_value.first.return_value = mock_task
        mock_query_instance_2 = MagicMock()
        mock_query_instance_2.filter.return_value.first.return_value = mock_count_result
        
        call_counter = {'count': 0}
        
        def query_side_effect(*args, **kwargs):
            call_counter['count'] += 1
            if call_counter['count'] == 1:
                return mock_query_instance
            else:
                return mock_query_instance_2
        
        mock_session.query.side_effect = query_side_effect
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql_summary("user1", 1, "user_id_1")
        
        assert result[0] is True
        assert result[1] == 0

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_summary_database_error(self, mock_db_scope):
        """测试数据库错误"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = query_dependence_sql_summary("user1", 1, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "Database Error"


class TestCreateDependenceData:
    """测试 create_dependence_data 函数"""

    def test_create_dependence_data_status_3(self):
        """测试状态为 3 的情况"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 3, None)
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert result["task_info"] == task_info[1:]
        assert result["success_dependence_data"] == []
        assert result["fail_dependence_data"] == []

    @patch('plugin.codemig.dependence_process.views.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_create_dependence_data_empty_dependence(self, mock_db_scope, mock_codemig_task_dep):
        """测试空依赖列表"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 2, None)
        
        mock_session = MagicMock()
        
        mock_codemig_task_dep.get_dependencies_by_task_id.return_value = []
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert result["task_info"] == task_info[1:]
        assert result["success_dependence_data"] == []
        assert result["fail_dependence_data"] == []

    @patch('plugin.codemig.dependence_process.views.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.views.FileDependence')
    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_create_dependence_data_with_success_and_fail(
            self, mock_db_scope, mock_file_dep, mock_codemig_task_dep):
        """测试有成功和失败的依赖"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 2, None)
        
        mock_session = MagicMock()
        
        # Mock 依赖行：(index, pkg, version, status, reason)
        dependence_rows = [
            (100, "pkg1", "1.0.0", 1, None),  # 成功
            (101, "pkg2", "2.0.0", 0, "Failed"),  # 失败
            (102, "pkg3", "3.0.0", 1, None),  # 成功
        ]
        
        mock_codemig_task_dep.get_dependencies_by_task_id.return_value = dependence_rows
        
        # Mock 汇总行：(dependence_id, num_changes, num_files)
        summary_rows = [
            (100, 2, 3),  # 5 个问题
            (102, 1, 0),  # 1 个问题
        ]
        
        mock_file_dep.get_summary_by_dependence_ids.return_value = summary_rows
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert len(result["success_dependence_data"]) == 2
        assert len(result["fail_dependence_data"]) == 1
        # 按问题数量降序排序，pkg1 (5 个) 应该在 pkg3 (1 个) 前面
        assert result["success_dependence_data"][0][2] == "pkg1"
        assert result["success_dependence_data"][1][2] == "pkg3"

    @patch('plugin.codemig.dependence_process.views.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_create_dependence_data_database_error(self, mock_db_scope, mock_codemig_task_dep):
        """测试数据库错误"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 2, None)
        
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert result["task_info"] == task_info[1:]
        assert result["success_dependence_data"] == []
        assert result["fail_dependence_data"] == []

    @patch('plugin.codemig.dependence_process.views.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.views.FileDependence')
    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_create_dependence_data_none_summary_rows(
            self, mock_db_scope, mock_file_dep, mock_codemig_task_dep):
        """测试汇总行为 None 的情况"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 2, None)
        
        mock_session = MagicMock()
        
        dependence_rows = [
            (100, "pkg1", "1.0.0", 1, None),
        ]
        
        mock_codemig_task_dep.get_dependencies_by_task_id.return_value = dependence_rows
        mock_file_dep.get_summary_by_dependence_ids.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert len(result["success_dependence_data"]) == 1
        # 没有匹配汇总行时，问题数为 0
        assert result["success_dependence_data"][0][9] == 0


class TestQueryDependence:
    """测试 query_dependence 函数"""

    @patch('plugin.codemig.dependence_process.views.query_dependence_sql')
    def test_query_dependence_error(self, mock_query_sql):
        """测试查询错误"""
        mock_query_sql.return_value = (False, None, "Error message")
        
        result = query_dependence("user1", 1, "user_id_1")
        
        assert result["code"] == -1
        assert result["msg"] == "Error message"

    @patch('plugin.codemig.dependence_process.views.query_dependence_sql')
    def test_query_dependence_with_count(self, mock_query_sql):
        """测试带计数的查询"""
        mock_query_sql.return_value = (True, (1, "/usr/bin/python3", "s1", "/usr/bin/go", "e1", 1, None), {'total': 10, 'processing': 3})
        
        result = query_dependence("user1", 1, "user_id_1")
        
        assert result["code"] == 0
        assert result["data"]["count"] == {'total': 10, 'processing': 3}

    @patch('plugin.codemig.dependence_process.views.query_dependence_sql')
    @patch('plugin.codemig.dependence_process.views.create_dependence_data')
    def test_query_dependence_with_data(self, mock_create_data, mock_query_sql):
        """测试带数据的查询"""
        task_info = (1, "/usr/bin/python3", "s1", "/usr/bin/go", "e1", 2, None)
        mock_query_sql.return_value = (True, task_info, None)
        
        mock_create_data.return_value = {
            "task_info": task_info[1:],
            "success_dependence_data": [(1, 100, "pkg1", "1.0.0", "", 1, None, 1, "", 5)],
            "fail_dependence_data": []
        }
        
        result = query_dependence("user1", 1, "user_id_1")
        
        assert result["code"] == 0
        assert "task_info" in result["data"]
        assert "success_dependence_data" in result["data"]


class TestQueryDependenceSummary:
    """测试 query_dependence_summary 函数"""

    @patch('plugin.codemig.dependence_process.views.query_dependence_sql_summary')
    def test_query_dependence_summary_error(self, mock_query_sql):
        """测试查询错误"""
        mock_query_sql.return_value = (False, None, "Error message")
        
        result = query_dependence_summary("user1", 1, "user_id_1")
        
        assert result["code"] == -1
        assert result["msg"] == "Error message"

    @patch('plugin.codemig.dependence_process.views.query_dependence_sql_summary')
    def test_query_dependence_summary_success(self, mock_query_sql):
        """测试成功查询摘要"""
        mock_query_sql.return_value = (True, 15, None)
        
        result = query_dependence_summary("user1", 1, "user_id_1")
        
        assert result["code"] == 0
        assert result["data"]["count"] == 15


class TestQueryDependenceSqlSummaryAdditional:
    """Additional tests for query_dependence_sql_summary"""

    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_query_dependence_sql_summary_no_dependence_scan(self, mock_db_scope):
        """测试未扫描依赖的情况"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.is_scan_dependence = 0
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = query_dependence_sql_summary("user1", 1, "user_id_1")
        
        assert result[0] is False
        assert result[2] == "task didn't scan dependence"


class TestCreateDependenceDataAdditional:
    """Additional tests for create_dependence_data"""

    @patch('plugin.codemig.dependence_process.views.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.views.db_session_scope')
    def test_create_dependence_data_none_dependence_rows(self, mock_db_scope, mock_codemig_task_dep):
        """测试依赖行为 None 的情况"""
        task_info = (1, "/usr/bin/python3", "source1", "/usr/bin/go", "env1", 2, None)
        
        mock_session = MagicMock()
        
        mock_codemig_task_dep.get_dependencies_by_task_id.return_value = None
        
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False
        
        result = create_dependence_data("user1", task_info, 1, "user_id_1")
        
        assert result["task_info"] == task_info[1:]
        assert result["success_dependence_data"] == []
        assert result["fail_dependence_data"] == []
