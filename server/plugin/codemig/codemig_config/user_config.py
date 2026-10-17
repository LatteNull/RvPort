import os
import subprocess
import sys

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger

from plugin.codemig.codemig_config.config import ConfigManager
from plugin.codemig.codemig_config.models import UserConfiguration

LOGGER = logger.init_log('codemig')


def get_init_configuration(user_id):
    dep_enable = ConfigManager.get_enable_dependence()
    if not dep_enable:
        return {
            'code': 0,
            'msg': 'query success',
            'data': {
                'python_interpreter': '',
                'python_image_source': '',
                'go_install_path': '',
                'go_environment': '',
                'enable': False
            }
        }
    status, configuration = UserConfiguration.query_user_configuration(user_id)
    if not status:
        return {'code': -1, 'msg': 'query user configuration failure'}
    if not configuration:
        python_path = find_executable_path('python')
        go_path = find_executable_path('go')
        return {
            'code': 0,
            'msg': 'query success',
            'data': {
                'python_interpreter': python_path,
                'python_image_source': '',
                'go_install_path': go_path,
                'go_environment': '',
                'enable': dep_enable
            }
        }
    _, _, python_interpreter, python_image_source, go_install_path, go_environment = configuration
    return {
        'code': 0,
        'msg': 'query success',
        'data': {
            'python_interpreter': python_interpreter or find_executable_path('python'),
            'python_image_source': python_image_source or '',
            'go_install_path': go_install_path or find_executable_path('go'),
            'go_environment': go_environment or '',
            'enable': dep_enable
        }
    }


def find_executable_path(executable_name):
    """统一查找可执行文件路径"""
    try:
        command = ['which', executable_name]
        result = subprocess.run(command, capture_output=True, text=True,
                                shell=(os.name == 'nt'))  # Windows需要shell=True

        if result.returncode == 0:
            path = result.stdout.split('\n')[0].strip()
            return path

    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as e:
        print(f"查找{executable_name}路径时出错: {e}")

    return None
