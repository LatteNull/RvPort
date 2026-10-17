import sys

import fcntl

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.response.response_code import ResponseCode
from common.public import logger
from common.public.public import get_codemig_data_path
from framework.log_manager.operation_log import record_operation_log
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage

MY_DATA_PATH = Path(get_codemig_data_path())

LOGGER = logger.init_log('codemig')


def process_upload(user_name, file, request):
    user_id = request.user_id
    dir_id = CodemigDirectoryStorage.insert_directory(user_id)
    if dir_id:
        dir_path = save_file_to_dir(user_name, dir_id, file)
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Upload Directory', OpLogResult.SUCCESS,
                             f'Upload directory to {os.path.relpath(dir_path, get_codemig_data_path())}.',
                             user_name=user_name)
        return {"code": 0, "msg": ResponseCode.OK, "dir_id": dir_id}
    record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                         'Upload Directory', OpLogResult.FAILED, f'Database Error!',
                         user_name=user_name)
    return {"code": -1, "msg": "Database Error!"}


def process_upload_zip(user_name, file_name, uploaded_chunks, chunk_dir, user_id):
    LOGGER.info(f"Uploading the zip to the backend.")
    dir_id = CodemigDirectoryStorage.insert_directory(user_id)
    if dir_id:
        folder_path = MY_DATA_PATH / user_name / str(dir_id)
        return merge_file(dir_id, file_name, uploaded_chunks, chunk_dir, folder_path)
    return {"code": -1, "msg": "Database Error!"}


def process_upload_single_zip(user_name, file_name, file, user_id):
    LOGGER.info(f"Uploading the zip to the backend.")
    dir_id = CodemigDirectoryStorage.insert_directory(user_id)
    if dir_id:
        folder_path = MY_DATA_PATH / user_name / str(dir_id)
        folder_path.mkdir(parents=True, exist_ok=True)
        final_path = os.path.join(folder_path, file_name)
        file.save(final_path)
        return {
            'code': 0,
            'msg': 'File uploaded successfully',
            'dir_id': dir_id
        }
    return {"code": -1, "msg": "Database Error!"}


def save_file_to_dir(user_name, dir_id, file):
    LOGGER.info(f"Saving the folder to the target directory.")
    file_path = MY_DATA_PATH / user_name / str(dir_id)
    file_path.mkdir(parents=True, exist_ok=True)
    file.save(file_path / file.filename)
    return file_path / file.filename


def process_chunk(user_name, file, current_chunk_idx, total_chunk_size, file_name, relative_path,
                  request):
    file_md5 = hashlib.sha256(f"{user_name}+{file_name}".encode()).hexdigest()
    directory_path = os.path.split(relative_path)[0] if relative_path else ''
    # 如果是分块上传
    if int(total_chunk_size) != 1:
        result = chunk_upload(user_name, file, file_name, current_chunk_idx, total_chunk_size,
                              directory_path, file_md5, request.user_id)
    else:
        result = process_upload_single_zip(user_name, file_name, file, request.user_id)
    if result['code'] == -1:
        fail_msg = result['msg']
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Upload Zip', OpLogResult.FAILED,
                             f'Upload {file_name} failed: {fail_msg}', user_name=user_name)
    else:
        if result['msg'] == 'File merged successfully' or result[
            'msg'] == 'File uploaded successfully':
            record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                                 'Upload Zip', OpLogResult.SUCCESS,
                                 f'Upload {file_name} successfully.', user_name=user_name)
    return result


def chunk_upload(user_name, file, file_name, current_chunk_idx, total_chunk_size, directory_path,
                 file_md5, user_id):
    # 创建临时文件夹存放分块
    chunk_dir = os.path.join('temp_file', directory_path, file_md5)
    try:
        os.makedirs(chunk_dir, exist_ok=True)
        if not os.path.exists(chunk_dir):
            return {"code": -1, 'msg': 'Failed to create temp directory'}
    except (OSError, FileNotFoundError, PermissionError, IOError) as e:
        return {"code": -1, 'msg': f'Directory creation failed: {str(e)}'}

    # 保存分块
    chunk_path = os.path.join(chunk_dir, current_chunk_idx)
    file.save(chunk_path)

    # 检查是否所有分块都已上传
    uploaded_chunks = set(os.listdir(chunk_dir))
    all_chunks = set(str(i) for i in range(int(total_chunk_size)))

    if uploaded_chunks == all_chunks:
        # 检查合并锁
        lock_file = os.path.join(chunk_dir, '.lock')
        with open(lock_file, 'w') as lf:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return process_upload_zip(user_name, file_name, uploaded_chunks, chunk_dir, user_id)
            except BlockingIOError:
                return {'code': -1, 'msg': 'Merge in progress'}
    else:
        return {
            'code': 0,
            'msg': f'Chunk {current_chunk_idx} uploaded successfully',
            'uploaded_chunks_length': len(uploaded_chunks),
            'total': int(total_chunk_size),
            'dir_id': -1
        }


def merge_file(dir_id, file_name, uploaded_chunks, chunk_dir, folder_path):
    LOGGER.info(f"merge file.")
    folder_path.mkdir(parents=True, exist_ok=True)
    final_path = os.path.join(folder_path, file_name)
    # 执行合并
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    with open(final_path, 'wb') as target_file:
        for chunk_num in sorted(int(c) for c in uploaded_chunks):
            with open(os.path.join(chunk_dir, str(chunk_num)), 'rb') as cf:
                target_file.write(cf.read())
    # 删除分块
    shutil.rmtree(chunk_dir)
    return {
        'code': '0',
        'msg': 'File merged successfully',
        'dir_id': dir_id
    }


def _remove_migrate_volumes(user_name, dir_id):
    """删除工程时清理一键迁移的 docker 命名卷（best-effort，失败不阻塞删工程）。

    卷名规则与 query_ai_handler._migrate_named_volume_name 保持一致：
    codemig_migrate_{pm|ut|mca}_{safe_user}_{dir_id}，改名需同步两处。
    """
    safe_user = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(user_name))[:32] or 'u'
    for prefix in ('codemig_migrate_pm', 'codemig_migrate_ut', 'codemig_migrate_mca'):
        volume_name = f"{prefix}_{safe_user}_{dir_id}"
        try:
            subprocess.run(
                ["docker", "volume", "rm", volume_name],
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as e:
            # 卷不存在 / docker 不可用 —— 均不阻塞删除工程
            LOGGER.warning(f"[cleanup] 删除命名卷 {volume_name} 失败（忽略）: {e}")


def delete_folder_by_dir_id(user_name, dir_id, request):
    folder_path = Path(get_codemig_data_path()) / user_name / str(dir_id)
    status = CodemigDirectoryStorage.mark_as_removed(dir_id)
    if not status:
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Delete File', OpLogResult.FAILED,
                             f'Delete {folder_path} failed: Database Error!', user_name=user_name)
        return {'code': -1, 'msg': 'remove failure'}
    if folder_path.exists():
        shutil.rmtree(folder_path)
    record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                         'Delete File', OpLogResult.SUCCESS, f'Delete {folder_path}',
                         user_name=user_name)
    _remove_migrate_volumes(user_name, dir_id)
    return {'code': 0, 'msg': 'remove success'}
