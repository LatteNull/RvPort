import os
import sys

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.response.response_code import ResponseCode
from framework.plugin_manager import plugin_db
from framework.plugin_manager.plugin_db import PluginStatus, Plugin


LOGGER = logger.init_log('plugin_manager')


def get_plugins(request):
    status, plugins, error = Plugin.query_all()
    if not status:
        return {
            "code": -1,
            "msg": error
        }
    # Started by AICoder, pid:xae9bq6863a6de214a40085fc0ce640abde5d048
    if not plugins:
        return {
            "code": -1,
            "msg": "No plugins installed"
        }

    formatted_plugins = [
        {
            'type': plugin['plugin_type'],
            'current_version': plugin['current_version'],
            'status': plugin['status'],
            'isOK': 'OK' if plugin['status'] == PluginStatus.INSTALLED else 'notOK'
        }
        for plugin in plugins
    ]
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "data": formatted_plugins
    }
    # Ended by AICoder, pid:xae9bq6863a6de214a40085fc0ce640abde5d048


def get_installed_plugins():
    status, plugins, _ = Plugin.query_all()
    if not status:
        return []
    plugins = [i['plugin_type'] for i in plugins if i['status'] == PluginStatus.INSTALLED]
    return plugins


def install_plugin(request):
    # free_space = public.get_free_space()
    # platform = public.get_platform()
    plugin_type = request.data.get('type')
    if plugin_type not in plugin_db.PluginType.get_supported_types():
        return False, 'plugin type not support'
    return True, None
