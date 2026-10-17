import sys
import importlib
import os

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from bp import action_bp
from framework.plugin_manager.plugin_manager import get_installed_plugins
from framework.plugin_manager.views import plugin_bp
from framework.plugin_manager.plugin_cache import remove_for_user

LOGGER = logger.init_log('plugin_manager')


def load_py_module(plugin):
    module_path = os.path.join(MODULE_PATH, 'plugin', plugin, f'{plugin}')
    if not os.path.exists(f'{module_path}.py'):
        return
    try:
        module = load_module(module_path)
        process_blueprint(module)
        register_fuction(module)
    except (ImportError, ValueError, AttributeError, TypeError) as e:
        LOGGER.error(f'init plugin error: str{e}', exc_info=True)


def load_module(module_path):
    spec = importlib.util.spec_from_file_location(module_path, f'{module_path}.py')
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


def register_fuction(module):
    # codemig 插件注册用户删除时的清理回调（user_manager 删除用户时调用）
    if hasattr(module, 'get_func_map'):
        for k, v in module.get_func_map().items():
            if k == 'codemig_task':
                remove_for_user.append(v['remove_for_user'])


def process_blueprint(module):
    if hasattr(module, 'get_blueprint'):
        plugin_bp.register_blueprint(module.get_blueprint())


def load_so_module(plugin):
    if not os.path.exists(os.path.join(MODULE_PATH, 'plugin', plugin, f'{plugin}.so')):
        return
    try:
        spec = importlib.util.spec_from_file_location(plugin,
                                                      os.path.join(MODULE_PATH, 'plugin', plugin,
                                                                   f'{plugin}.so'))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            process_blueprint(module)
            register_fuction(module)
    except Exception as e:
        LOGGER.error(f'init plugin {plugin} error: {str(e)}', exc_info=True)


def init_plugin():
    plugins = get_installed_plugins()
    if plugins and len(plugins) > 0:
        action_bp.register_blueprint(plugin_bp)
    for plugin in plugins:
        load_py_module(plugin)
        load_so_module(plugin)
