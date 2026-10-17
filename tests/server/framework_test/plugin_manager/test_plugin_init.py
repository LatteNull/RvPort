"""
Tests for framework/plugin_manager/plugin_init.py
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from framework.plugin_manager import plugin_init


@pytest.fixture
def fresh_module():
    """提供一个临时构造的模块对象用于 register/process 测试"""
    module = MagicMock()
    return module


def test_load_module_success(tmp_path):
    """load_module 能从 .py 文件加载模块（注意 load_module 会自动补 .py 后缀）"""
    py_file = tmp_path / "demo.py"
    py_file.write_text("VALUE = 42\n")
    module = plugin_init.load_module(str(py_file.with_suffix('')))
    assert module is not None
    assert module.VALUE == 42


def test_load_module_returns_none_when_loader_missing():
    """spec.loader 为 None 时返回 None"""
    fake_spec = MagicMock()
    fake_spec.loader = None
    with patch('importlib.util.spec_from_file_location', return_value=fake_spec):
        assert plugin_init.load_module('/some/path.py') is None


def test_load_module_returns_none_when_spec_none():
    """spec 为 None 时返回 None"""
    with patch('importlib.util.spec_from_file_location', return_value=None):
        assert plugin_init.load_module('/some/path.py') is None


def test_load_py_module_file_not_exist():
    """目标文件不存在时应早返回，不执行后续逻辑"""
    with patch('os.path.exists', return_value=False):
        with patch.object(plugin_init, 'load_module') as mock_load:
            result = plugin_init.load_py_module('not_existing_plugin')
            assert result is None
            mock_load.assert_not_called()


def test_load_py_module_success():
    """文件存在时正常加载并处理 blueprint/register"""
    fake_module = MagicMock()
    with patch('os.path.exists', return_value=True), \
            patch.object(plugin_init, 'load_module', return_value=fake_module) as mock_load, \
            patch.object(plugin_init, 'process_blueprint') as mock_bp, \
            patch.object(plugin_init, 'register_fuction') as mock_reg:
        plugin_init.load_py_module('demo_plugin')
        mock_load.assert_called_once()
        mock_bp.assert_called_once_with(fake_module)
        mock_reg.assert_called_once_with(fake_module)


def test_load_py_module_handles_import_error():
    """load_module 抛 ImportError 时被捕获并记录日志"""
    with patch('os.path.exists', return_value=True), \
            patch.object(plugin_init, 'load_module', side_effect=ImportError("boom")), \
            patch.object(plugin_init.LOGGER, 'error') as mock_err:
        plugin_init.load_py_module('demo_plugin')
        assert mock_err.called


def test_load_py_module_handles_value_error():
    """load_module 抛 ValueError 时被捕获并记录日志"""
    with patch('os.path.exists', return_value=True), \
            patch.object(plugin_init, 'load_module', side_effect=ValueError("boom")), \
            patch.object(plugin_init.LOGGER, 'error') as mock_err:
        plugin_init.load_py_module('demo_plugin')
        assert mock_err.called


def test_load_py_module_handles_attribute_error():
    """load_module 抛 AttributeError 时被捕获并记录日志"""
    with patch('os.path.exists', return_value=True), \
            patch.object(plugin_init, 'load_module', side_effect=AttributeError("boom")), \
            patch.object(plugin_init.LOGGER, 'error') as mock_err:
        plugin_init.load_py_module('demo_plugin')
        assert mock_err.called


def test_load_py_module_handles_type_error():
    """load_module 抛 TypeError 时被捕获并记录日志"""
    with patch('os.path.exists', return_value=True), \
            patch.object(plugin_init, 'load_module', side_effect=TypeError("boom")), \
            patch.object(plugin_init.LOGGER, 'error') as mock_err:
        plugin_init.load_py_module('demo_plugin')
        assert mock_err.called


def test_register_fuction_no_get_func_map(fresh_module):
    """没有 get_func_map 属性时直接返回"""
    del fresh_module.get_func_map
    plugin_init.register_fuction(fresh_module)


def test_register_fuction_codemig_task_branch(fresh_module):
    """对 codemig_task 类型的函数，加入 remove_for_user 列表"""
    remove_fn = MagicMock()
    fresh_module.get_func_map.return_value = {
        'codemig_task': {'remove_for_user': remove_fn}
    }
    with patch.object(plugin_init, 'remove_for_user', []) as remove_list:
        plugin_init.register_fuction(fresh_module)
        assert remove_fn in remove_list


def test_process_blueprint_with_attr():
    """get_blueprint 存在时调用 register_blueprint"""
    bp = MagicMock()
    fake_module = MagicMock()
    fake_module.get_blueprint.return_value = bp
    with patch.object(plugin_init, 'plugin_bp') as mock_plugin_bp:
        plugin_init.process_blueprint(fake_module)
        mock_plugin_bp.register_blueprint.assert_called_once_with(bp)


def test_process_blueprint_without_attr():
    """没有 get_blueprint 时直接返回"""
    fake_module = MagicMock()
    del fake_module.get_blueprint
    plugin_init.process_blueprint(fake_module)


def test_load_so_module_not_exist():
    """so 文件不存在时直接返回"""
    with patch('os.path.exists', return_value=False):
        with patch.object(plugin_init.LOGGER, 'error') as mock_err:
            result = plugin_init.load_so_module('demo_plugin')
            assert result is None
            mock_err.assert_not_called()


def test_load_so_module_loads_and_processes():
    """so 文件存在时执行加载和处理"""
    fake_module = MagicMock()
    fake_spec = MagicMock()
    fake_spec.loader = MagicMock()

    with patch('os.path.exists', return_value=True), \
            patch('importlib.util.spec_from_file_location', return_value=fake_spec), \
            patch('importlib.util.module_from_spec', return_value=fake_module), \
            patch.object(plugin_init, 'process_blueprint') as mock_bp, \
            patch.object(plugin_init, 'register_fuction') as mock_reg:
        plugin_init.load_so_module('demo_plugin')
        fake_spec.loader.exec_module.assert_called_once_with(fake_module)
        mock_bp.assert_called_once_with(fake_module)
        mock_reg.assert_called_once_with(fake_module)


def test_load_so_module_spec_without_loader():
    """spec.loader 为 None 时跳过执行"""
    fake_spec = MagicMock()
    fake_spec.loader = None
    with patch('os.path.exists', return_value=True), \
            patch('importlib.util.spec_from_file_location', return_value=fake_spec), \
            patch('importlib.util.module_from_spec') as mock_from_spec, \
            patch.object(plugin_init, 'process_blueprint') as mock_bp:
        plugin_init.load_so_module('demo_plugin')
        mock_from_spec.assert_not_called()
        mock_bp.assert_not_called()


def test_load_so_module_handles_exception():
    """so 加载抛异常时被捕获并记录"""
    with patch('os.path.exists', return_value=True), \
            patch('importlib.util.spec_from_file_location',
                  side_effect=Exception("so boom")), \
            patch.object(plugin_init.LOGGER, 'error') as mock_err:
        plugin_init.load_so_module('demo_plugin')
        assert mock_err.called


def test_init_plugin_no_plugins():
    """没有任何插件时不注册 blueprint"""
    with patch.object(plugin_init, 'get_installed_plugins', return_value=[]), \
            patch.object(plugin_init, 'action_bp') as mock_action_bp, \
            patch.object(plugin_init, 'load_py_module') as mock_py, \
            patch.object(plugin_init, 'load_so_module') as mock_so:
        plugin_init.init_plugin()
        mock_action_bp.register_blueprint.assert_not_called()
        mock_py.assert_not_called()
        mock_so.assert_not_called()


def test_init_plugin_with_plugins():
    """有插件时注册 blueprint 并对每个插件加载 .py 与 .so"""
    with patch.object(plugin_init, 'get_installed_plugins', return_value=['p1', 'p2']), \
            patch.object(plugin_init, 'action_bp') as mock_action_bp, \
            patch.object(plugin_init, 'plugin_bp') as mock_plugin_bp, \
            patch.object(plugin_init, 'load_py_module') as mock_py, \
            patch.object(plugin_init, 'load_so_module') as mock_so:
        plugin_init.init_plugin()
        mock_action_bp.register_blueprint.assert_called_once_with(mock_plugin_bp)
        assert mock_py.call_count == 2
        assert mock_so.call_count == 2
