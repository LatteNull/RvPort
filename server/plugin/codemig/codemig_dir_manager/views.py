import os
import sys
import re
from pathlib import Path
from flask import Blueprint
from flask import request
from flask import session
from werkzeug.utils import secure_filename

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from framework.log_manager.operation_log import record_operation_log
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from plugin.codemig.codemig_dir_manager.codemig_dir_processor import (process_upload,
        process_chunk, delete_folder_by_dir_id)

LOGGER = logger.init_log('codemig')
directory_storage_bp = Blueprint('dir', __name__, url_prefix='/dir')


@directory_storage_bp.route('/upload', methods=['POST'])
def upload():
    LOGGER.info(f"Uploading the folder to the backend.")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    file = request.files['file']
    return process_upload(user_name, file, request)


def validate_chunk_parameters(current_chunk_idx, total_chunk_size):
    """
    验证分块上传参数的安全性
    """
    # 验证 current_chunk_idx
    if not current_chunk_idx or not isinstance(current_chunk_idx, str):
        return False, "current_chunk_idx", "分块索引不能为空"

    # 必须是纯数字
    if not current_chunk_idx.isdigit():
        return False, "current_chunk_idx", "分块索引必须是数字"

    chunk_idx = int(current_chunk_idx)
    if chunk_idx < 0 or chunk_idx > 40000:  # 合理范围限制
        return False, "current_chunk_idx", "分块索引超出有效范围"

    # 验证 total_chunk_size
    if total_chunk_size and isinstance(total_chunk_size, str):
        if not total_chunk_size.isdigit():
            return False, "total_chunk_size", "总分块大小必须是数字"

        total_size = int(total_chunk_size)
        if total_size < 0 or total_size > 4 * 1024 * 1024 * 1024:  # 限制1GB
            return False, "total_chunk_size", "文件大小超出限制"

    return True, '', "验证通过"


def validate_relative_path(relative_path):
    """
    验证相对路径是否安全
    """
    status = True
    safe_path = relative_path
    msg = "验证通过"

    if not relative_path:
        return True, "", ''

    if not isinstance(relative_path, str):
        status = False
        msg = '类型异常'
    else:
        # 基本清理
        relative_path = relative_path.strip()

        # 1. 拒绝绝对路径
        if Path(relative_path).is_absolute():
            status = False
            msg = "不允许使用绝对路径"
        # 2. 拒绝路径遍历攻击
        elif '..' in relative_path or '../' in relative_path or '\\..' in relative_path:
            status = False
            msg = "路径包含非法遍历序列"
        # 3. 限制字符集（白名单）
        elif not re.match(r'^[a-zA-Z0-9_\-./\\\s]+$', relative_path):
            status = False
            msg = "路径包含非法字符"
        # 4. 限制路径深度
        else:
            path_parts = [part for part in relative_path.replace('\\', '/').split('/') if
                          part and part != '.']
            if len(path_parts) > 10:  # 限制最大深度
                status = False
                msg = "路径深度超出限制"
            # 5. 额外安全检查：防止隐藏文件
            elif any(part.startswith('.') and part not in ['.', '..'] for part in path_parts):
                status = False
                msg = "路径包含隐藏文件模式"

    return status, safe_path, msg


def validate_file_upload(file, file_name):
    """
    验证上传文件的安全性
    """
    if not file:
        return False, "未上传文件"

    if not file_name:
        return False, "文件名不能为空"

    # 检查文件名是否安全（secure_filename 处理后应该没问题）
    safe_name = secure_filename(file_name)
    if safe_name != file_name:
        return False, "文件名包含不安全字符"

    return True, "文件验证通过"

def check_upload_zip(current_chunk_idx, total_chunk_size, file, file_name, relative_path):
    chunk_status, chunk_field, chunk_msg = validate_chunk_parameters(current_chunk_idx,
                                                                     total_chunk_size)
    if not chunk_status:
        return  -1,  f"{chunk_field}: {chunk_msg}", None

    file_status, file_msg = validate_file_upload(file, file_name)
    if not file_status:
        return  -1,  file_msg, None

    status, safe_path, msg = validate_relative_path(relative_path)
    if not status:
        return  -1,  msg, None
    return 0, '', safe_path
    
@directory_storage_bp.route('/upload_zip', methods=['POST'])
def upload_zip():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    # 获取上传的文件块

    current_chunk_idx = request.form.get('current_chunk_idx')
    total_chunk_size = request.form.get('total_chunk_size')
    file = request.files.get('file')
    file_name = secure_filename(request.form.get('file_name'))
    relative_path = request.form.get('relativePath')

    status, msg, safe_path  = check_upload_zip(current_chunk_idx, total_chunk_size, file, file_name, relative_path)
    if status != 0:
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Upload Zip', OpLogResult.FAILED,
                             f'Upload {file_name} failed: {msg}', user_name=user_name)
        return {"code": status, 'msg': msg}
    return process_chunk(user_name, file, current_chunk_idx, total_chunk_size, file_name, safe_path,
                         request)


@directory_storage_bp.route('/delete_folder', methods=['POST'])
def delete_folder():
    LOGGER.info(f"remove folder for dir_id")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    return delete_folder_by_dir_id(user_name, dir_id, request)
