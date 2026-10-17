import pytest
from unittest.mock import patch, MagicMock, Mock
from contextlib import contextmanager

from plugin.codemig.dependence_process.dependence_base import (
    update_task_dependence_status, DependenceProcessor
)
from plugin.codemig.dependence_process.dependence_sql import insert_task_dependence_update_status
from plugin.codemig.dependence_process.dependence_info import DepStatus
from plugin.codemig.dependence_process.models import DependencePackages, DependenceTask
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.codemig_task_manager.task_common import TaskDependenceStatus
from common.db.SQLOperation import db_session_scope, DatabaseException


class TestUpdateTaskDependenceStatus:
    """测试 update_task_dependence_status 函数"""

    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.update_task_status')
    def test_update_task_dependence_status(self, mock_update):
        """测试更新任务依赖状态"""
        update_task_dependence_status(1, 2, "test_pkg", "1.0.0", DepStatus.finished, 123)
        
        mock_update.assert_called_once_with(1, 2, "test_pkg", "1.0.0", DepStatus.finished, 123)

    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.update_task_status')
    def test_update_task_dependence_status_failed(self, mock_update):
        """测试更新失败状态"""
        update_task_dependence_status(1, 2, "test_pkg", "1.0.0", DepStatus.failed, None)
        
        mock_update.assert_called_once_with(1, 2, "test_pkg", "1.0.0", DepStatus.failed, None)


class ConcreteDependenceProcessor(DependenceProcessor):
    """具体实现类，用于测试抽象基类"""

    def validate_config(self, config):
        return True, config

    def _get_base_dir(self):
        return "/test/base/dir"

    def _should_check_installed(self, local_path):
        return local_path == ""

    def _extract_version_for_check(self, package, version):
        return version if version else None

    @staticmethod
    def install_single_package(dir_id, pkg, version, local_path, validated_config):
        return True, "success", 123


class TestDependenceProcessor:
    """测试 DependenceProcessor 基类"""

    def test_init(self):
        """测试初始化"""
        processor = ConcreteDependenceProcessor(
            config_name="Test",
            config=("test", "config"),
            to_process=[],
            task_id=1
        )
        assert processor.config_name == "Test"
        assert processor.config == ("test", "config")
        assert processor.to_process == []
        assert processor.task_id == 1
        assert processor.validated_config == ()

    def test_cannot_instantiate_abstract_class(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            DependenceProcessor("Test", ("test",), [], 1)

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_exists(self, mock_db_scope):
        """测试检查任务状态 - 任务存在"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.status = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        
        @contextmanager
        def mock_context():
            yield mock_session
        
        mock_db_scope.return_value = mock_context()
        
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()
        
        assert exists is True
        assert should_stop is False

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_deleted(self, mock_db_scope):
        """测试检查任务状态 - 任务已删除"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.status = 4  # deleted
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        
        @contextmanager
        def mock_context():
            yield mock_session
        
        mock_db_scope.return_value = mock_context()
        
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()
        
        assert exists is True
        assert should_stop is True

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_not_exists(self, mock_db_scope):
        """测试检查任务状态 - 任务不存在"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        @contextmanager
        def mock_context():
            yield mock_session
        
        mock_db_scope.return_value = mock_context()
        
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()
        
        assert exists is False
        assert should_stop is True

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_database_error(self, mock_db_scope):
        """测试检查任务状态 - 数据库错误"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()
        
        assert exists is False
        assert should_stop is True

    def test_install_package_worker_success(self):
        """测试安装包工作函数 - 成功"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            return True, "success", 123
        
        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }
        
        DependenceProcessor._install_package_worker(args_dict)
        
        assert result_dict['success'] is True
        assert result_dict['msg'] == "success"
        assert result_dict['dep_id'] == 123

    def test_install_package_worker_failure(self):
        """测试安装包工作函数 - 失败"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            return False, "failed", None
        
        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }
        
        DependenceProcessor._install_package_worker(args_dict)
        
        assert result_dict['success'] is False
        assert result_dict['msg'] == "failed"
        assert result_dict['dep_id'] is None

    def test_install_package_worker_exception(self):
        """测试安装包工作函数 - 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise RuntimeError("Installation error")
        
        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }
        
        DependenceProcessor._install_package_worker(args_dict)
        
        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_empty(self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试处理包列表 - 空列表"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(status=1)
        
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        result = processor._process_packages()
        
        assert result == []
        mock_makedirs.assert_called_once()

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_already_processed(self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试处理包列表 - 已处理的包"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(status=1)
        
        processor = ConcreteDependenceProcessor(
            "Test", ("test",), [(1, "pkg1", "1.0.0", "", DepStatus.finished.value, 100)], 1
        )
        result = processor._process_packages()
        
        assert len(result) == 1
        assert (1, 100) in result

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_already_installed(self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试处理包列表 - 包已安装"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(status=1)
        mock_is_installed.return_value = 200
        
        processor = ConcreteDependenceProcessor(
            "Test", ("test",), [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)], 1
        )
        result = processor._process_packages()
        
        assert len(result) == 1
        assert (1, 200) in result
        mock_is_installed.assert_called_once()

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_install_success(self, mock_db_scope, mock_process_class, mock_update, mock_is_installed, mock_makedirs):
        """测试处理包列表 - 安装成功"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(status=1)
        mock_is_installed.return_value = None
        
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process_class.return_value = mock_process
        
        processor = ConcreteDependenceProcessor(
            "Test", ("test",), [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)], 1
        )
        # Mock multiprocessing.Manager
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 300
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict
            
            result = processor._process_packages()
        
        assert len(result) == 1
        assert (1, 300) in result

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_success(self, mock_delete, mock_update_status):
        """测试process方法 - 成功"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        
        with patch.object(processor, '_process_packages', return_value=[(1, 100)]):
            with patch('plugin.codemig.dependence_process.dependence_base.insert_task_dependence_update_status') as mock_insert:
                processor.process()
                
                mock_insert.assert_called_once_with(1, [(1, 100)])

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_no_dependencies(self, mock_delete, mock_update_status):
        """测试process方法 - 没有依赖"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        
        with patch.object(processor, '_process_packages', return_value=[]):
            processor.process()
            
            mock_update_status.assert_called_with(1, TaskDependenceStatus.SUCCESS.value, None)

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_config_invalid(self, mock_delete, mock_update_status):
        """测试process方法 - 配置无效"""
        class InvalidProcessor(ConcreteDependenceProcessor):
            def validate_config(self, config):
                return False, "Invalid config"
        
        processor = InvalidProcessor("Test", ("test",), [], 1)
        processor.process()
        
        mock_update_status.assert_called_with(1, TaskDependenceStatus.FAILED.value, "Invalid config")

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_exception(self, mock_delete, mock_update_status):
        """测试process方法 - 异常处理"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        
        with patch.object(processor, '_process_packages', side_effect=RuntimeError("Test error")):
            processor.process()
            
            mock_update_status.assert_called()
            assert TaskDependenceStatus.FAILED.value in [call[0][1] for call in mock_update_status.call_args_list]
            mock_delete.assert_called_once_with(1)


class TestDependenceProcessorEdgeCases:
    """测试 DependenceProcessor 的边界情况和异常场景"""

    def test_validate_config_not_implemented(self):
        """测试抽象方法未实现时类无法实例化"""
        class IncompleteProcessor(DependenceProcessor):
            def _get_base_dir(self):
                return "/test"

            def _should_check_installed(self, local_path):
                return False

            def _extract_version_for_check(self, package, version):
                return version

            @staticmethod
            def install_single_package(dir_id, pkg, version, local_path, validated_config):
                return True, "success", 123

        # 抽象方法未实现，类无法实例化
        with pytest.raises(TypeError):
            IncompleteProcessor("Test", ("test",), [], 1)

    def test_get_base_dir_not_implemented(self):
        """测试_get_base_dir 未实现时类无法实例化"""
        class IncompleteProcessor(DependenceProcessor):
            def validate_config(self, config):
                return True, config

            def _should_check_installed(self, local_path):
                return False

            def _extract_version_for_check(self, package, version):
                return version

            @staticmethod
            def install_single_package(dir_id, pkg, version, local_path, validated_config):
                return True, "success", 123

        # 抽象方法未实现，类无法实例化
        with pytest.raises(TypeError):
            IncompleteProcessor("Test", ("test",), [], 1)

    def test_should_check_installed_not_implemented(self):
        """测试_should_check_installed 未实现时类无法实例化"""
        class IncompleteProcessor(DependenceProcessor):
            def validate_config(self, config):
                return True, config

            def _get_base_dir(self):
                return "/test"

            def _extract_version_for_check(self, package, version):
                return version

            @staticmethod
            def install_single_package(dir_id, pkg, version, local_path, validated_config):
                return True, "success", 123

        # 抽象方法未实现，类无法实例化
        with pytest.raises(TypeError):
            IncompleteProcessor("Test", ("test",), [], 1)

    def test_extract_version_not_implemented(self):
        """测试_extract_version_for_check 未实现时类无法实例化"""
        class IncompleteProcessor(DependenceProcessor):
            def validate_config(self, config):
                return True, config

            def _get_base_dir(self):
                return "/test"

            def _should_check_installed(self, local_path):
                return False

            @staticmethod
            def install_single_package(dir_id, pkg, version, local_path, validated_config):
                return True, "success", 123

        # 抽象方法未实现，类无法实例化
        with pytest.raises(TypeError):
            IncompleteProcessor("Test", ("test",), [], 1)

    def test_install_single_package_not_implemented(self):
        """测试 install_single_package 未实现时类无法实例化"""
        class IncompleteProcessor(DependenceProcessor):
            def validate_config(self, config):
                return True, config

            def _get_base_dir(self):
                return "/test"

            def _should_check_installed(self, local_path):
                return False

            def _extract_version_for_check(self, package, version):
                return version

        # 抽象方法未实现，类无法实例化
        with pytest.raises(TypeError):
            IncompleteProcessor("Test", ("test",), [], 1)

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_os_error(self, mock_db_scope):
        """测试检查任务状态 - OSError 异常"""
        mock_db_scope.side_effect = OSError("OS error")

        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()

        assert exists is False
        assert should_stop is True

    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_check_task_status_io_error(self, mock_db_scope):
        """测试检查任务状态 - IOError 异常"""
        mock_db_scope.side_effect = IOError("IO error")

        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)
        exists, should_stop = processor._check_task_status()

        assert exists is False
        assert should_stop is True

    def test_install_package_worker_value_error(self):
        """测试安装包工作函数 - ValueError 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise ValueError("Value error")

        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }

        DependenceProcessor._install_package_worker(args_dict)

        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None

    def test_install_package_worker_attribute_error(self):
        """测试安装包工作函数 - AttributeError 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise AttributeError("Attribute error")

        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }

        DependenceProcessor._install_package_worker(args_dict)

        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None

    def test_install_package_worker_runtime_error(self):
        """测试安装包工作函数 - RuntimeError 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise RuntimeError("Runtime error")

        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }

        DependenceProcessor._install_package_worker(args_dict)

        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None

    def test_install_package_worker_os_error(self):
        """测试安装包工作函数 - OSError 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise OSError("OS error")

        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }

        DependenceProcessor._install_package_worker(args_dict)

        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None

    def test_install_package_worker_io_error(self):
        """测试安装包工作函数 - IOError 异常"""
        def mock_install_func(dir_id, pkg, spec, local_path, validated_config):
            raise IOError("IO error")

        result_dict = {'success': None, 'msg': None, 'dep_id': None}
        args_dict = {
            'dir_id': 1,
            'pkg': 'test_pkg',
            'spec': '1.0.0',
            'local_path': '',
            'validated_config': ('test',),
            'install_func': mock_install_func,
            'result_dict': result_dict
        }

        DependenceProcessor._install_package_worker(args_dict)

        assert result_dict['success'] is False
        assert "安装包时发生异常" in result_dict['msg']
        assert result_dict['dep_id'] is None


class TestProcessPackagesEdgeCases:
    """测试_process_packages 方法的边界情况"""

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_multiple_packages(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试处理多个包"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        processor = ConcreteDependenceProcessor(
            "Test", ("test",),
            [
                (1, "pkg1", "1.0.0", "", DepStatus.created.value, None),
                (2, "pkg2", "2.0.0", "", DepStatus.created.value, None),
                (3, "pkg3", "3.0.0", "", DepStatus.created.value, None),
            ],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 100
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        assert len(result) == 3
        assert mock_process.call_count == 3

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_mixed_status(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试处理混合状态的包"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        processor = ConcreteDependenceProcessor(
            "Test", ("test",),
            [
                (1, "pkg1", "1.0.0", "", DepStatus.finished.value, 100),  # 已完成
                (2, "pkg2", "2.0.0", "", DepStatus.created.value, None),  # 待处理
                (3, "pkg3", "3.0.0", "", DepStatus.failed.value, 200),   # 已失败
            ],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 300
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        # 只有 pkg2 需要安装，其他两个应该直接添加
        assert len(result) == 3
        assert (1, 100) in result  # 已完成的
        assert (2, 300) in result  # 新安装的
        assert (3, 200) in result  # 已失败的

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_version_none(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试版本号为 None 的情况"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        processor = ConcreteDependenceProcessor(
            "Test", ("test",),
            [(1, "pkg1", None, "", DepStatus.created.value, None)],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 100
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        assert len(result) == 1

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_local_path_not_empty(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试 local_path 不为空的情况"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        processor = ConcreteDependenceProcessor(
            "Test", ("test",),
            [(1, "pkg1", "1.0.0", "/some/path", DepStatus.created.value, None)],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 100
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        # local_path 不为空，_should_check_installed 返回 False，不检查已安装
        assert len(result) == 1


class TestProcessMethodEdgeCases:
    """测试 process 方法的边界情况"""

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_attribute_error(self, mock_delete, mock_update_status):
        """测试 process 方法 - AttributeError 异常"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        with patch.object(processor, '_process_packages', side_effect=AttributeError("Attr error")):
            processor.process()

            mock_update_status.assert_called()
            assert TaskDependenceStatus.FAILED.value in [call[0][1] for call in mock_update_status.call_args_list]

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_value_error(self, mock_delete, mock_update_status):
        """测试 process 方法 - ValueError 异常"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        with patch.object(processor, '_process_packages', side_effect=ValueError("Value error")):
            processor.process()

            mock_update_status.assert_called()
            assert TaskDependenceStatus.FAILED.value in [call[0][1] for call in mock_update_status.call_args_list]

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_type_error(self, mock_delete, mock_update_status):
        """测试 process 方法 - TypeError 异常"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        with patch.object(processor, '_process_packages', side_effect=TypeError("Type error")):
            processor.process()

            mock_update_status.assert_called()
            assert TaskDependenceStatus.FAILED.value in [call[0][1] for call in mock_update_status.call_args_list]

    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_os_error(self, mock_delete, mock_update_status):
        """测试 process 方法 - OSError 异常"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        with patch.object(processor, '_process_packages', side_effect=OSError("OS error")):
            processor.process()

            mock_update_status.assert_called()
            assert TaskDependenceStatus.FAILED.value in [call[0][1] for call in mock_update_status.call_args_list]

    @patch('plugin.codemig.dependence_process.dependence_base.insert_task_dependence_update_status')
    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_finally_block_always_executes(self, mock_delete, mock_update_status, mock_insert):
        """测试 process 方法的 finally 块总是执行"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        # RuntimeError 在 process 方法的 except 捕获范围内
        with patch.object(processor, '_process_packages', side_effect=RuntimeError("Unexpected error")):
            processor.process()

        # 即使发生异常，finally 块中的 delete_by_task_id 也应该被调用
        mock_delete.assert_called_once_with(1)

    @patch('plugin.codemig.dependence_process.dependence_base.insert_task_dependence_update_status')
    @patch('plugin.codemig.dependence_process.dependence_base.CodemigTasks.update_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.DependenceTask.delete_by_task_id')
    def test_process_success_no_dependence_ids(self, mock_delete, mock_update_status, mock_insert):
        """测试 process 方法 - 成功但没有 dependence_ids"""
        processor = ConcreteDependenceProcessor("Test", ("test",), [], 1)

        with patch.object(processor, '_process_packages', return_value=[]):
            processor.process()

        # 当 dependence_ids 为空时，应该更新为 SUCCESS 状态
        mock_update_status.assert_called_with(1, TaskDependenceStatus.SUCCESS.value, None)
        mock_delete.assert_called_once_with(1)


class TestProcessPackagesTaskStopped:
    """测试任务停止时的场景"""

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_task_stopped_during_install(
            self, mock_db_scope, mock_update, mock_is_installed, mock_makedirs):
        """测试安装包过程中任务被删除，强制终止进程"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        # 模拟进程在等待时仍然存活
        mock_process_instance = MagicMock()
        # 第一次检查 is_alive 返回 True，表示进程还在运行
        # 然后 check_task_status 会返回 should_stop=True
        mock_process_instance.is_alive.side_effect = [True, False]
        mock_process_instance.terminate = MagicMock()
        mock_process_instance.join = MagicMock()
        mock_process_instance.kill = MagicMock()

        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process', return_value=mock_process_instance):
            with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
                mock_manager_dict = MagicMock()
                # 模拟任务停止后的结果
                mock_manager_dict.get.side_effect = lambda key: {
                    'success': False,
                    'msg': '任务已删除或状态为 deleted，安装已停止',
                    'dep_id': None
                }.get(key)
                mock_manager.return_value.dict.return_value = mock_manager_dict

                # Mock _check_task_status 在第二次调用时返回 should_stop=True
                call_count = [0]

                def mock_check_status():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return True, True  # 应该停止
                    return True, False

                processor = ConcreteDependenceProcessor(
                    "Test", ("test",),
                    [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)],
                    1
                )
                with patch.object(processor, '_check_task_status', side_effect=mock_check_status):
                    result = processor._process_packages()

                # 任务停止后，dependence_ids 应该为空
                assert result == []
                mock_process_instance.terminate.assert_called_once()

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_install_failed(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试安装包失败的情况"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        processor = ConcreteDependenceProcessor(
            "Test", ("test",),
            [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': False,
                'msg': 'Installation failed',
                'dep_id': None
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        # 安装失败，dep_id 为 None，不应该添加到结果中
        assert result == []
        # 应该调用 update_task_dependence_status 设置为 failed 状态
        mock_update.assert_called_with(1, 1, "pkg1", "1.0.0", DepStatus.failed, None)

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_process_kill_when_not_terminating(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试进程无法及时终止时需要强制杀死"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        # terminate 后进程仍在运行，需要 kill
        mock_process_instance.is_alive.side_effect = [True, True, False]
        mock_process_instance.terminate = MagicMock()
        mock_process_instance.join = MagicMock()
        mock_process_instance.kill = MagicMock()

        mock_process.return_value = mock_process_instance

        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': False,
                'msg': '任务已删除或状态为 deleted，安装已停止',
                'dep_id': None
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            call_count = [0]

            def mock_check_status():
                call_count[0] += 1
                if call_count[0] == 1:
                    return True, True  # 应该停止
                return True, False

            processor = ConcreteDependenceProcessor(
                "Test", ("test",),
                [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)],
                1
            )
            with patch.object(processor, '_check_task_status', side_effect=mock_check_status):
                result = processor._process_packages()

            # 应该调用了 kill
            mock_process_instance.kill.assert_called_once()
            assert result == []


class TestExtractVersionAndCheckInstalled:
    """测试版本提取和已安装检查相关逻辑"""

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_extract_version_returns_none(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试_extract_version_for_check 返回 None 的情况"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        class CustomProcessor(ConcreteDependenceProcessor):
            def _extract_version_for_check(self, package, version):
                return None  # 无法提取版本号

        processor = CustomProcessor(
            "Test", ("test",),
            [(1, "pkg1", "1.0.0", "", DepStatus.created.value, None)],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 100
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        # 版本号提取为 None，不检查已安装，直接进行安装
        assert len(result) == 1
        # is_package_installed 不应该被调用，因为 version 是 None
        mock_is_installed.assert_not_called()

    @patch('plugin.codemig.dependence_process.dependence_base.os.makedirs')
    @patch('plugin.codemig.dependence_process.dependence_base.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.dependence_base.update_task_dependence_status')
    @patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Process')
    @patch('plugin.codemig.dependence_process.dependence_base.db_session_scope')
    def test_process_packages_should_check_installed_false(
            self, mock_db_scope, mock_process, mock_update, mock_is_installed, mock_makedirs):
        """测试_should_check_installed 返回 False 的情况"""
        mock_db_scope.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = MagicMock(
            status=1)
        mock_is_installed.return_value = None

        mock_process_instance = MagicMock()
        mock_process_instance.is_alive.return_value = False
        mock_process.return_value = mock_process_instance

        class CustomProcessor(ConcreteDependenceProcessor):
            def _should_check_installed(self, local_path):
                return False  # 不检查已安装

        processor = CustomProcessor(
            "Test", ("test",),
            [(1, "pkg1", "1.0.0", "/some/path", DepStatus.created.value, None)],
            1
        )
        with patch('plugin.codemig.dependence_process.dependence_base.multiprocessing.Manager') as mock_manager:
            mock_manager_dict = MagicMock()
            mock_manager_dict.get.side_effect = lambda key: {
                'success': True,
                'msg': 'success',
                'dep_id': 100
            }.get(key)
            mock_manager.return_value.dict.return_value = mock_manager_dict

            result = processor._process_packages()

        # 不检查已安装，直接进行安装
        assert len(result) == 1
        mock_is_installed.assert_not_called()
