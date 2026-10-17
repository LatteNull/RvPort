import os
import sys

from flask import Blueprint
from flask import request
from flask import session

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from plugin.codemig.codemig_report_manager.report_processor import create_report_response, create_patch_response

LOGGER = logger.init_log('codemig')
codemig_report_bp = Blueprint('report', __name__, url_prefix='/report')


@codemig_report_bp.route('/download', methods=['POST'])
def download_report():
    LOGGER.info("Downloading the report for the given task.")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    return create_report_response(user_name, task_id, request)


@codemig_report_bp.route('/download_patch', methods=['POST'])
def download_patch():
    LOGGER.info("Downloading the patch file for the given task.")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    return create_patch_response(user_name, task_id, request)
