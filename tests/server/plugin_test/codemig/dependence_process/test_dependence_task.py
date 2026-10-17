import pytest
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager
from plugin.codemig.dependence_process.dependence_task import (
    submit_dependence_task, insert_dep_task, init_dep_task, dep_process
)
from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.codemig_task_manager.task_common import TaskDependenceStatus


class TestSubmitDependenceTask:
    """测试 submit_dependence_task 函数"""

    def test_submit_dependence_task_scan_disabled(self):
        """测试扫描被禁用的情况"""
        dep = DependenceInfo(scan=0, lang="python")
        with patch(
                'plugin.codemig.dependence_process.dependence_task.parse_python_req') as mock_parse:
            submit_dependence_task("/path/to/source", dep, 1, 1, 1)
            mock_parse.assert_not_called()

    @patch('plugin.codemig.dependence_process.dependence_task.insert_dep_task')
    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_task.parse_python_req')
    def test_submit_dependence_task_python_success(self, mock_parse, mock_update, mock_insert):
        """测试 Python 依赖解析成功"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        mock_parse.return_value = (True, 5, [(1, 1, "package1", "1.0.0")])

        submit_dependence_task("/path/to/source", dep, 1, 1, 1)

        mock_parse.assert_called_once_with("/path/to/source", 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.PROCESSING.value, None)
        mock_insert.assert_called_once_with(1, dep, [(1, 1, "package1", "1.0.0")])

    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_task.parse_python_req')
    def test_submit_dependence_task_python_parse_failed(self, mock_parse, mock_update):
        """测试 Python 依赖解析失败"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        mock_parse.return_value = (False, "Parse error", None)

        submit_dependence_task("/path/to/source", dep, 1, 1, 1)

        mock_parse.assert_called_once_with("/path/to/source", 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.FAILED.value,
                                            "Parse go mod file failed")

    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_task.parse_python_req')
    def test_submit_dependence_task_python_no_packages(self, mock_parse, mock_update):
        """测试 Python 依赖解析成功但无包"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        mock_parse.return_value = (True, 0, [])

        submit_dependence_task("/path/to/source", dep, 1, 1, 1)

        mock_parse.assert_called_once_with("/path/to/source", 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.SUCCESS.value, None)

    @patch('plugin.codemig.dependence_process.dependence_task.insert_dep_task')
    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_task.parse_go_dep')
    def test_submit_dependence_task_go_success(self, mock_parse, mock_update, mock_insert):
        """测试 Go 依赖解析成功"""
        dep = DependenceInfo(scan=1, lang="go", go="/usr/bin/go", go_config="GOPATH=/path/to/go")
        mock_parse.return_value = (True, 3, [(1, 1, "github.com/user/pkg", "v1.0.0")])

        submit_dependence_task("/path/to/source", dep, 1, 1, 1)

        mock_parse.assert_called_once_with("/path/to/source", 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.PROCESSING.value, None)
        mock_insert.assert_called_once_with(1, dep, [(1, 1, "github.com/user/pkg", "v1.0.0")])

    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_task.parse_go_dep')
    def test_submit_dependence_task_go_parse_failed(self, mock_parse, mock_update):
        """测试 Go 依赖解析失败"""
        dep = DependenceInfo(scan=1, lang="go", go="/usr/bin/go", go_config="")
        mock_parse.return_value = (False, "Parse error", None)

        submit_dependence_task("/path/to/source", dep, 1, 1, 1)

        mock_parse.assert_called_once_with("/path/to/source", 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.FAILED.value,
                                            "Parse go mod file failed")

    @patch(
        'plugin.codemig.dependence_process.dependence_task.CodemigTasks.update_dependence_status')
    def test_submit_dependence_task_unsupported_lang(self, mock_update):
        """测试不支持的语言"""
        dep = DependenceInfo(scan=1, lang="rust")
        submit_dependence_task("/path/to/source", dep, 1, 1, 1)
        mock_update.assert_called_once_with(1, TaskDependenceStatus.FAILED.value,
                                            "只支持python和go依赖包")


class TestInsertDepTask:
    """测试 insert_dep_task 函数"""

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.PythonDependenceProcessor')
    def test_insert_dep_task_python(self, mock_processor_class, mock_executor):
        """测试插入 Python 依赖任务"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        packages = [
            (1, 1, "package1", "1.0.0"),
            (1, 1, "package2", "2.0.0")
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        insert_dep_task(1, dep, packages)

        mock_processor_class.assert_called_once_with(
            config=("/usr/bin/python3", ""),
            to_process=[(1, "package1", "1.0.0", "", 0, None),
                        (1, "package2", "2.0.0", "", 0, None)],
            task_id=1
        )
        mock_executor.submit.assert_called_once_with(mock_processor.process)

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.GoDependenceProcessor')
    def test_insert_dep_task_go(self, mock_processor_class, mock_executor):
        """测试插入 Go 依赖任务"""
        dep = DependenceInfo(scan=1, lang="go", go="/usr/bin/go", go_config="GOPATH=/path/to/go")
        packages = [
            (1, 1, "github.com/user/pkg1", "v1.0.0", "/local/path1"),
            (1, 1, "github.com/user/pkg2", "v1.0.0")
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        insert_dep_task(1, dep, packages)

        mock_processor_class.assert_called_once_with(
            config=("/usr/bin/go", "GOPATH=/path/to/go"),
            to_process=[
                (1, "github.com/user/pkg1", "v1.0.0", "/local/path1", 0, None),
                (1, "github.com/user/pkg2", "v1.0.0", "", 0, None)
            ],
            task_id=1
        )
        mock_executor.submit.assert_called_once_with(mock_processor.process)

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    def test_insert_dep_task_empty_packages(self, mock_executor):
        """测试空包列表"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        packages = []

        insert_dep_task(1, dep, packages)

        mock_executor.submit.assert_not_called()

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.PythonDependenceProcessor')
    def test_insert_dep_task_python_with_local_path(self, mock_processor_class, mock_executor):
        """测试 Python 依赖任务带本地路径（5个元素）"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="")
        packages = [
            (1, 1, "package1", "1.0.0", "/local/path1")
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        insert_dep_task(1, dep, packages)

        mock_processor_class.assert_called_once_with(
            config=("/usr/bin/python3", ""),
            to_process=[(1, "package1", "1.0.0", "/local/path1", 0, None)],
            task_id=1
        )


class TestInitDepTask:
    """测试 init_dep_task 函数"""

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.GoDependenceProcessor')
    @patch(
        'plugin.codemig.dependence_process.dependence_task.DependenceTask.get_packages_by_task_ids')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_success_go(self, mock_db_scope, mock_get_packages, mock_processor_class,
                                      mock_executor):
        """测试成功初始化 Go 依赖任务"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.task_id = 1
        mock_task.python_interpreter = None
        mock_task.python_image_source = None
        mock_task.go_install_path = "/usr/bin/go"
        mock_task.go_environment = "GOPATH=/path/to/go"
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task]

        @contextmanager
        def mock_db_scope_func():
            yield mock_session

        mock_db_scope.side_effect = mock_db_scope_func
        mock_get_packages.return_value = [
            (1, 1, "github.com/user/pkg", "v1.0.0", None, 0, None)
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        init_dep_task()

        mock_get_packages.assert_called_once_with([1])
        mock_processor_class.assert_called_once_with(
            config=("/usr/bin/go", "GOPATH=/path/to/go"),
            to_process=[(1, "github.com/user/pkg", "v1.0.0", None, 0, None)],
            task_id=1
        )
        mock_executor.submit.assert_called_once_with(mock_processor.process)

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.PythonDependenceProcessor')
    @patch(
        'plugin.codemig.dependence_process.dependence_task.DependenceTask.get_packages_by_task_ids')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_success_python(self, mock_db_scope, mock_get_packages,
                                          mock_processor_class, mock_executor):
        """测试成功初始化 Python 依赖任务"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.task_id = 1
        mock_task.python_interpreter = "/usr/bin/python3"
        mock_task.python_image_source = ""
        mock_task.go_install_path = None
        mock_task.go_environment = None
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task]

        @contextmanager
        def mock_db_scope_func():
            yield mock_session

        mock_db_scope.side_effect = mock_db_scope_func
        mock_get_packages.return_value = [
            (1, 1, "package1", "1.0.0", None, 0, None)
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        init_dep_task()

        mock_get_packages.assert_called_once_with([1])
        mock_processor_class.assert_called_once_with(
            config=("/usr/bin/python3", ""),
            to_process=[(1, "package1", "1.0.0", None, 0, None)],
            task_id=1
        )
        mock_executor.submit.assert_called_once_with(mock_processor.process)

    @patch('plugin.codemig.dependence_process.dependence_task.LOGGER')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_database_exception(self, mock_db_scope, mock_logger):
        """测试数据库异常"""
        from common.db.SQLOperation import DatabaseException
        mock_db_scope.side_effect = DatabaseException("Database error")

        # 当 tasks 为 None 时，for 循环会失败，但这是代码的实际行为
        init_dep_task()

        mock_logger.error.assert_called_once()

    @patch(
        'plugin.codemig.dependence_process.dependence_task.DependenceTask.get_packages_by_task_ids')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_no_packages(self, mock_db_scope, mock_get_packages):
        """测试无包信息"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.task_id = 1
        mock_task.python_interpreter = "/usr/bin/python3"
        mock_task.python_image_source = ""
        mock_task.go_install_path = None
        mock_task.go_environment = None
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task]

        @contextmanager
        def mock_db_scope_func():
            yield mock_session

        mock_db_scope.side_effect = mock_db_scope_func
        mock_get_packages.return_value = None

        init_dep_task()

        mock_get_packages.assert_called_once_with([1])

    @patch('plugin.codemig.dependence_process.dependence_task.background_executor')
    @patch('plugin.codemig.dependence_process.dependence_task.PythonDependenceProcessor')
    @patch(
        'plugin.codemig.dependence_process.dependence_task.DependenceTask.get_packages_by_task_ids')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_multiple_tasks(self, mock_db_scope, mock_get_packages,
                                          mock_processor_class, mock_executor):
        """测试多个任务"""
        mock_session = MagicMock()
        mock_task1 = MagicMock()
        mock_task1.task_id = 1
        mock_task1.python_interpreter = "/usr/bin/python3"
        mock_task1.python_image_source = ""
        mock_task1.go_install_path = None
        mock_task1.go_environment = None

        mock_task2 = MagicMock()
        mock_task2.task_id = 2
        mock_task2.python_interpreter = None
        mock_task2.python_image_source = None
        mock_task2.go_install_path = "/usr/bin/go"
        mock_task2.go_environment = "GOPATH=/path/to/go"

        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task1, mock_task2
        ]

        @contextmanager
        def mock_db_scope_func():
            yield mock_session

        mock_db_scope.side_effect = mock_db_scope_func
        mock_get_packages.side_effect = [
            [(1, 1, "package1", "1.0.0", None, 0, None)],
            [(2, 1, "github.com/user/pkg", "v1.0.0", None, 0, None)]
        ]
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        init_dep_task()

        assert mock_get_packages.call_count == 2
        assert mock_executor.submit.call_count == 2

    @patch(
        'plugin.codemig.dependence_process.dependence_task.DependenceTask.get_packages_by_task_ids')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_empty_tasks(self, mock_db_scope, mock_get_packages):
        """测试空任务列表"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        @contextmanager
        def mock_db_scope_func():
            yield mock_session

        mock_db_scope.side_effect = mock_db_scope_func

        init_dep_task()

        mock_get_packages.assert_not_called()

    @patch('plugin.codemig.dependence_process.dependence_task.LOGGER')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_os_error(self, mock_db_scope, mock_logger):
        """测试 OSError 异常"""
        mock_db_scope.side_effect = OSError("OS error")

        # 当 tasks 为 None 时，for 循环会失败，但这是代码的实际行为
        init_dep_task()

        mock_logger.error.assert_called_once()

    @patch('plugin.codemig.dependence_process.dependence_task.LOGGER')
    @patch('plugin.codemig.dependence_process.dependence_task.db_session_scope')
    def test_init_dep_task_io_error(self, mock_db_scope, mock_logger):
        """测试 IOError 异常"""
        mock_db_scope.side_effect = IOError("IO error")

        # 当 tasks 为 None 时，for 循环会失败，但这是代码的实际行为
        init_dep_task()

        mock_logger.error.assert_called_once()
