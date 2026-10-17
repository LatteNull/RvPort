import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig import (
    get_func_map, get_blueprint, init_data_directory,
    start_cron_permanent_delete, backend_process,
    func_map
)


class TestPluginVersion:
    def test_version(self):
        # 版本号重构后运行时版本统一走 server.version 的 getter（数据库 plugin 表），
        # codemig 模块不再导出 PLUGIN_VERSION 常量
        import version
        assert version.get_codemig_version() is not None


class TestFuncMap:
    """测试 func_map 和 get_func_map"""

    def test_get_func_map_returns_dict(self):
        result = get_func_map()
        assert isinstance(result, dict)

    def test_func_map_contains_codemig_task(self):
        assert 'codemig_task' in func_map
        assert 'remove_for_user' in func_map['codemig_task']

    def test_func_map_remove_for_user_is_callable(self):
        assert callable(func_map['codemig_task']['remove_for_user'])


class TestGetBlueprint:
    """测试 get_blueprint 函数"""

    def test_returns_blueprint(self):
        bp = get_blueprint()
        assert bp is not None
        assert bp.name == 'codemig'


class TestInitDataDirectory:
    """测试 init_data_directory 函数"""

    def test_creates_directory_if_not_exists(self, tmp_path):
        with patch('plugin.codemig.codemig.get_codemig_data_path',
                   return_value=str(tmp_path / "new_dir")):
            init_data_directory()
            assert os.path.isdir(str(tmp_path / "new_dir"))

    def test_does_not_fail_if_exists(self, tmp_path):
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        with patch('plugin.codemig.codemig.get_codemig_data_path',
                   return_value=str(existing_dir)):
            init_data_directory()
            assert os.path.isdir(str(existing_dir))


class TestStartCronPermanentDelete:
    """测试 start_cron_permanent_delete 函数"""

    def test_starts_scheduler(self):
        with patch('plugin.codemig.codemig.BackgroundScheduler') as mock_scheduler_cls:
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler

            start_cron_permanent_delete()
            mock_scheduler.add_job.assert_called_once()
            mock_scheduler.start.assert_called_once()


class TestBackendProcess:
    """测试 backend_process 函数"""

    def test_calls_init_codemig_task(self):
        with patch('plugin.codemig.codemig.init_codemig_task') as mock_init, \
             patch('plugin.codemig.codemig.ConfigManager.get_enable_dependence',
                   return_value=False), \
             patch('plugin.codemig.codemig.ENABLE_CRON_PERMANENT_DELETE', False):
            backend_process()
            mock_init.assert_called_once()

    def test_calls_dep_process_when_enabled(self):
        with patch('plugin.codemig.codemig.init_codemig_task'), \
             patch('plugin.codemig.codemig.dep_process') as mock_dep, \
             patch('plugin.codemig.codemig.ConfigManager.get_enable_dependence',
                   return_value=True), \
             patch('plugin.codemig.codemig.ENABLE_CRON_PERMANENT_DELETE', False):
            backend_process()
            mock_dep.assert_called_once()

    def test_starts_process_when_cron_enabled(self):
        with patch('plugin.codemig.codemig.init_codemig_task'), \
             patch('plugin.codemig.codemig.ConfigManager.get_enable_dependence',
                   return_value=False), \
             patch('plugin.codemig.codemig.ENABLE_CRON_PERMANENT_DELETE', True), \
             patch('plugin.codemig.codemig.multiprocessing.Process') as mock_proc:
            mock_process = MagicMock()
            mock_proc.return_value = mock_process

            backend_process()
            mock_proc.assert_called_once()
            assert mock_process.daemon is True
            mock_process.start.assert_called_once()


class TestBackendProcessRunTasks:
    """测试 backend_process 内的 run_tasks 子函数（行57-67）"""

    def test_run_tasks_captures_target(self):
        """通过捕获 Process target 来测试 run_tasks"""
        captured_target = {}

        def capture_process_target(target, name):
            captured_target['func'] = target
            mock_proc = MagicMock()
            mock_proc.daemon = None
            return mock_proc

        with patch('plugin.codemig.codemig.init_codemig_task'), \
             patch('plugin.codemig.codemig.ConfigManager.get_enable_dependence',
                   return_value=False), \
             patch('plugin.codemig.codemig.ENABLE_CRON_PERMANENT_DELETE', True), \
             patch('plugin.codemig.codemig.multiprocessing.Process',
                   side_effect=capture_process_target):

            backend_process()
            assert 'func' in captured_target

            # Now test the captured run_tasks function
            with patch('plugin.codemig.codemig.start_cron_permanent_delete'), \
                 patch('plugin.codemig.codemig.time.sleep', side_effect=KeyboardInterrupt):
                captured_target['func']()  # Should handle KeyboardInterrupt gracefully

    def test_run_tasks_no_cron(self):
        """测试 run_tasks 在 ENABLE_CRON_PERMANENT_DELETE=False 时"""
        with patch('plugin.codemig.codemig.init_codemig_task'), \
             patch('plugin.codemig.codemig.ConfigManager.get_enable_dependence',
                   return_value=False), \
             patch('plugin.codemig.codemig.ENABLE_CRON_PERMANENT_DELETE', False):
            backend_process()


class TestModulePathBranch:
    """测试 MODULE_PATH 分支（行18）"""

    def test_sys_path_already_contains_module(self):
        """测试 MODULE_PATH 已在 sys.path 中时不重复添加"""
        import plugin.codemig.codemig as cm
        module_path = os.path.realpath(
            os.path.join(os.path.dirname(cm.__file__), '..', '..'))
        assert module_path in sys.path
