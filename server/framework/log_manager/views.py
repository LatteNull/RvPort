import sys
import os
from flask import Blueprint, request, send_file
from contextlib import suppress

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from framework.log_manager.operation_constant import OpLogModule, OpLogResult, OpLogEvent
from framework.log_manager.operation_log import OperationLog, record_operation_log, write_csv
from framework.user_manager.user_db import UserManager
from common.public.public import DB_DIR

log_bp = Blueprint('logmanager', __name__, url_prefix='/logmanager')


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/logmanager/list \
# -H 'Content-Type: application/json' \
# -d '{
# "page":1,
# "per_page": 20,
# "filter":{"user_name": "Admin","result":"success,failed"}
# }'


@log_bp.route('/list', methods=['POST'])
def list_log():
    op_user_id = request.user_id
    user = UserManager.query_by_id(op_user_id)
    if user is None:
        return {"code": 1, "msg": "user not found"}
    data = request.get_json()
    page = data.get('page', 1)
    per_page = data.get('per_page', 20)
    filters = data.get('filter', None)

    user_id = None if user.role == 'admin' else op_user_id
    status, msg, log_list = OperationLog.list_operation_log(
        user_id, per_page, (page - 1) * per_page, filters)
    if not status:
        return {"code": 1, "msg": msg}
    return {"code": 0, "msg": log_list}


# curl -i -X GET --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/logmanager/csv \
# -H 'Content-Type: application/json'


@log_bp.route('/csv', methods=['GET'])
def csv():
    op_user_id = request.user_id
    user = UserManager.query_by_id(op_user_id)
    if user is None:
        return {"code": 1, "msg": "user not found"}
    if user.role != 'admin':
        status, msg, log_list = OperationLog.list_operation_log(op_user_id)
    else:
        status, msg, log_list = OperationLog.list_operation_log(None)
    if not status:
        return {"code": 1, "msg": msg}
    if log_list and log_list.get('total_log_count') > 0:
        file = write_csv(op_user_id, log_list.get('operation_log_list'))
        return {"code": 0, "msg": "ok", "data": file}
    return {"code": 0, "msg": "no log"}


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/logmanager/download \
# -H 'Content-Type: application/json' \
# -d '{
# "csvfile":"bBEbHfpZNO.csv"
# }'


@log_bp.route('/download', methods=['POST'])
def download():
    op_user_id = request.user_id
    csvfile = request.get_json().get("csvfile", None)
    path = os.path.join(DB_DIR, "logmanager", f'{op_user_id}_{csvfile}')
    download_file = "log.csv"
    if not os.path.exists(path):
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.LOG,
                             OpLogEvent.LOG_DOWNLOAD, OpLogResult.FAILED,
                             f'File:{csvfile} not exist')

        return {"code": -1, "msg": "file not exist"}
    try:
        response = send_file(path, as_attachment=True, download_name=download_file)

        record_operation_log(request.user_id, request.remote_addr, OpLogModule.LOG,
                             OpLogEvent.LOG_DOWNLOAD, OpLogResult.SUCCESS, '')
        return response
    finally:
        # 无论成功与否都会执行清理
        with suppress(OSError, PermissionError, FileNotFoundError):
            if os.path.exists(path):
                os.remove(path)
                print(f"Successfully deleted {path}")


# curl -i -X GET --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/logmanager/filter \
# -H 'Content-Type: application/json'


@log_bp.route('/filter', methods=['GET'])
def filter_list():
    modules = [value for name, value in vars(OpLogModule).items() if
               not name.startswith('__') and not callable(value)]
    result = [value for name, value in vars(OpLogResult).items() if
              not name.startswith('__') and not callable(value)]
    return {"code": 0, "msg": "ok", "data": {"modules": modules, "result": result}}
