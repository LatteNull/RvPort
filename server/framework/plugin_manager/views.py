from flask import Blueprint, request

from framework.plugin_manager.plugin_manager import get_plugins

plugin_bp = Blueprint('plugin', __name__, url_prefix='/plugin')
pluginmanager_bp = Blueprint('pluginmanager', __name__, url_prefix='/pluginmanager')


# curl -i -X GET --noproxy 127.0.0.1 http://127.0.0.1:8080/action/pluginmanager/list \
# -H 'Content-Type: application/json'


# Started by AICoder, pid:obdd6n44654f77914ea309aa801cd80609b7a7d4
@pluginmanager_bp.route('/list', methods=['GET'])
def list_plugins():
    """
    Handles GET requests to /pluginmanager/list.
    Returns a list of all available plugins.
    """
    return get_plugins(request)
# Ended by AICoder, pid:obdd6n44654f77914ea309aa801cd80609b7a7d4
