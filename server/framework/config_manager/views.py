from flask import Blueprint, request

from common.response.response_code import ResponseCode
from framework.config_manager.config_manager import list_user_config, check_and_update
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from framework.log_manager.operation_log import record_operation_log

config_bp = Blueprint('config', __name__, url_prefix='/config')


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/config \
# -H 'Content-Type: application/json' \
# -d '{
# "key":"max_online_users",
# "value": "10"
# }'
@config_bp.route('', methods=['POST'])
def set_config():
    user_id = request.user_id
    # 修改为批量导入，需要列表传入
    data_list = request.get_json()
    if not isinstance(data_list, list):
        return {"code": -1, "msg": "数据格式错误，应为列表"}

    results = []
    overall_status = True
    for item in data_list:
        k = item.get("key")
        v = item.get("value")
        status, code = check_and_update(k, v, user_id)
        # 记录日志
        detail = f"Modify {k.replace('_', ' ')} to {v}"
        detail += ' successfully.' if status else f' failed: {code}.'
        record_operation_log(
            user_id, request.remote_addr, OpLogModule.CONFIG,
            'Batch Modify ' + k.replace('_', ' '),
            OpLogResult.SUCCESS if status else OpLogResult.FAILED,
            detail,
            user_name=request.user_name
        )
        if not status:
            overall_status = False
            results.append({"key": k, "msg": code})
    if overall_status:
        return {"code": 0, "msg": "全部更新成功"}
    else:
        return {"code": -1, "msg": "部分或全部更新失败", "errors": results}


# curl -i -X GET --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/config \
# -H 'Content-Type: application/json'
@config_bp.route('', methods=['GET'])
def list_config():
    user_id = request.user_id
    ip = request.remote_addr
    status, msg, config = list_user_config(user_id, ip)
    if msg == ResponseCode.NON_PRIVILEGED:
        record_operation_log(user_id, ip, OpLogModule.CONFIG, 'Query Config',
                             OpLogResult.FAILED, msg)
    return {"code": 0 if status else -1, "msg": msg, "data": config}
