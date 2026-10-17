import sys
import os
from flask import Blueprint

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from plugin.codemig.codemig_dir_manager.views import directory_storage_bp
from plugin.codemig.codemig_task_manager.views import codemig_task_bp
from plugin.codemig.codemig_report_manager.views import codemig_report_bp
from plugin.codemig.ai_assistant.views import codemig_ai_bp
from version import get_codemig_version as _get_codemig_version

codemig_bp = Blueprint("codemig", __name__, url_prefix="/codemig")

codemig_bp.register_blueprint(directory_storage_bp)
codemig_bp.register_blueprint(codemig_task_bp)
codemig_bp.register_blueprint(codemig_report_bp)
codemig_bp.register_blueprint(codemig_ai_bp)


@codemig_bp.route('/version', methods=['GET'])
def get_codemig_version():
    return {"code": 0, "msg": "ok", "data": {"version": _get_codemig_version()}}

