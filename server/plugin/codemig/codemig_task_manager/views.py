import os
import sqlite3
import sys
import threading

import sqlcipher3
from flask import Blueprint
from flask import request
from flask import session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.db.SQLOperation import get_conn
from common.public import logger
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from framework.log_manager.operation_log import record_operation_log
from framework.user_manager.user_db import UserManager
from plugin.codemig.codemig_task_manager.codemig_task import start_task
from plugin.codemig.codemig_task_manager.request_processor import save_updated_file_with_content, \
    save_project_file_with_content, \
    mark_as_deleted, create_file_or_directory_handler, delete_file_or_directory_handler, \
    update_suggestion_ignored_handler, file_rollback_handler
from plugin.codemig.codemig_task_manager.query_processor import \
    query_dependence_file_tree_processor, query_software, query_missing_files, \
    query_existing_arch, query_user_task_dependence_files, query_dependence_software, \
    query_dependence_missing_files, query_dependence_existing_arch, query_file_tree_processor, \
    query_dependence_changes_for_file, query_changes_for_file, query_user_task_files, \
    query_user_tasks, query_generate_for_file, query_dependence_generate_for_file, \
    check_file_exists_handler, save_file_content_handler, query_original_file_processor, \
    query_ut_test_files_processor
from plugin.codemig.codemig_config.user_config import get_init_configuration
from plugin.codemig.ai_assistant.query_ai_handler import (
    query_project_migrate,
    rollback_project_migrate_handler,
    list_project_migrate_history_handler,
    generate_project_patch_handler,
    rescan_file,
)
from plugin.codemig.codemig_common.codemig_common_utils import (
    query_project_ai_suggestion,
    query_project_ai_history,
    get_database_path,
    is_ai_task_running,
    FileSource,
)

from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.dependence_process.views import query_dependence, query_dependence_summary
from plugin.codemig.codemig_common.common_lock import task_file_lock

LOGGER = logger.init_log('codemig')
codemig_task_bp = Blueprint('task', __name__, url_prefix='/task')

# ─── v5.0.0：重扫任务状态管理 ───
# 内存状态：{ (user_name, dir_id): {status, processed, total, fail_reason} }
# status: 0=空闲 1=运行中 2=成功 3=失败
_rescan_states = {}
_rescan_states_lock = threading.Lock()


def _is_rescan_running(user_name, dir_id):
    key = (user_name, dir_id)
    with _rescan_states_lock:
        st = _rescan_states.get(key, {})
        return st.get("status") == 1


def _try_mark_rescan_running(user_name, dir_id):
    """原子地"检查 + 标记运行中"，成功返回 True，已在运行返回 False。

    必须在请求线程内同步完成 check-and-set：若只检查（_is_rescan_running）
    而把 status=1 留给工作线程设置，线程启动到置位之间的窗口期内第二个
    请求也能通过守卫，导致两个 rescan 线程并发写同一份建议表。
    """
    key = (user_name, dir_id)
    with _rescan_states_lock:
        st = _rescan_states.get(key)
        if st and st.get("status") == 1:
            return False
        _rescan_states[key] = {
            "status": 1, "processed": 0, "total": 0, "fail_reason": "",
        }
        return True


def _get_rescan_state(user_name, dir_id):
    key = (user_name, dir_id)
    with _rescan_states_lock:
        st = _rescan_states.get(key, {
            "status": 0, "processed": 0, "total": 0, "fail_reason": "",
        })
        return dict(st)


def _set_rescan_state(user_name, dir_id, **kwargs):
    key = (user_name, dir_id)
    with _rescan_states_lock:
        if key not in _rescan_states:
            _rescan_states[key] = {
                "status": 0, "processed": 0, "total": 0, "fail_reason": "",
            }
        _rescan_states[key].update(kwargs)


def _count_changed_files(user_name, dir_id):
    """统计 file_source='changed' 的文件数（前端 total 用）"""
    try:
        db_path = get_database_path(user_name, dir_id)
        if not db_path.exists():
            return 0
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM codemig_task_directory_file "
            "WHERE file_source = ? AND has_removed = 0 AND type = 0",
            (FileSource.CHANGED.value,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    except (sqlite3.Error, sqlcipher3.dbapi2.Error, ValueError) as e:
        LOGGER.error(f"Count changed files failed: {e}")
        return 0


def _query_changed_files(user_name, dir_id):
    """查询所有 file_source='changed' 的文件列表（含 file_id + file_path）"""
    try:
        db_path = get_database_path(user_name, dir_id)
        if not db_path.exists():
            return []
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_id, file_path FROM codemig_task_directory_file "
            "WHERE file_source = ? AND has_removed = 0 AND type = 0",
            (FileSource.CHANGED.value,)
        )
        result = cursor.fetchall()
        conn.close()
        return [{"file_id": row[0], "file_path": row[1]} for row in result]
    except (sqlite3.Error, sqlcipher3.dbapi2.Error, ValueError) as e:
        LOGGER.error(f"Query changed files failed: {e}")
        return []


def _do_rescan_all_files(user_name, dir_id):
    """后台执行 rescan：对所有 file_source='changed' 文件复用 query_ai_handler.rescan_file。

    与 AI Agent finally 块调用的 _rescan_all_files（query_ai_handler.py:2959）差异：
    - 用户主动触发，不插入新增文件、不 git commit
    - 仅遍历 changed 文件并复用 rescan_file = process_updated_file + update_file_suggestion_to_database
    - is_manual=1 行由 REMOVE_SUGGESTION_OF_FILE_SQL 豁免；ignored 行由 _match_ignored_suggestion 跟随
    """
    try:
        file_list = _query_changed_files(user_name, dir_id)
        total = len(file_list)
        # status=1 已由请求线程的 _try_mark_rescan_running 同步置位（防重入），
        # 这里只补 total；processed 从 0 重新计数
        _set_rescan_state(user_name, dir_id, processed=0, total=total)

        for idx, file_info in enumerate(file_list, 1):
            file_id = file_info["file_id"]
            try:
                rescan_file(user_name, dir_id, file_id)
            except (sqlite3.Error, sqlcipher3.dbapi2.Error,
                    OSError, ValueError, TypeError) as e:
                LOGGER.error(f"Rescan file failed: file_id={file_id}, error={e}")
            _set_rescan_state(user_name, dir_id, processed=idx)

        _set_rescan_state(user_name, dir_id, status=2)
        LOGGER.info(f"Rescan all files done: {user_name}/{dir_id}, total={total}")

    except (sqlite3.Error, sqlcipher3.dbapi2.Error,
            OSError, ValueError, TypeError) as e:
        LOGGER.error(f"Rescan all files failed: {e}")
        _set_rescan_state(user_name, dir_id, status=3, fail_reason=str(e))

def check_user(user_name):
    user_id = request.user_id
    user = UserManager.query_by_id(user_id)
    if not user:
        return  -1, "Unkown user."
    if user_name != user.user_name:
        return  -1, 'no privilege'
    return 0, None

@codemig_task_bp.route('/create', methods=['POST'])
def create_and_process():
    LOGGER.info(f"Creating the task for the given directories.")
    json_body = request.get_json()
    user_name = json_body.get("user_name")

    task_name = json_body.get("task_name")
    code, msg = check_user(user_name)
    if "Unkown user." == msg:
        return {"code": code, "msg": "Unkown user."}
    if code != 0 :
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Create Code Migration Task', OpLogResult.FAILED,
                             f'create code migration task failed:{task_name}, error:{msg}.')
        return {"code": code, "msg": msg}

    upload_file_info_lists = json_body.get("upload_file_info_lists")
    is_scan = json_body.get("scan_dependencies")
    dep_info = DependenceInfo(1 if is_scan == "yes" else 0)  # 存储所有依赖相关数据
    if upload_file_info_lists is None or len(upload_file_info_lists) == 0:
        return {"code": -1, "msg": "No file uploaded."}
    if len(upload_file_info_lists) > 1:
        return {"code": -1, "msg": "Only single file can be uploaded."}
    dir_id, zip_name = upload_file_info_lists[0]
    if is_scan == "yes":
        dependencies = json_body.get("dependencies")
        if dependencies == "python":
            dep_info.lang = dependencies
            dep_info.python = json_body.get("python_interpreter")
            dep_info.python_config = json_body.get("python_image_source")
        elif dependencies == "go":
            dep_info.lang = dependencies
            dep_info.go = json_body.get("go_install_path")
            dep_info.go_config = json_body.get("go_environment")
        else:
            return {"code": -1, "msg": "Unsupported language."}
    return start_task(user_name, task_name, dir_id, zip_name, dep_info, request)


@codemig_task_bp.route('/list', methods=['POST'])
def query_task():
    user_id = request.user_id
    return query_user_tasks(user_id)


@codemig_task_bp.route('/project_migrate_missing_files', methods=['POST'])
def project_migrate_missing_files():
    """获取一键迁移 ①代码生成 节点的缺失文件 + 迁移新增文件清单

    ★ code 统一返回 0（历史版本返回 200，前端判断 code == 0 导致
      缺失文件永远不渲染——本次连同新增文件一并修复）。
    """
    json_body = request.get_json()
    task_id = json_body.get('task_id')
    user_name = json_body.get('user_name')

    if not task_id or not user_name:
        return {'code': 400, 'msg': '缺少必要参数'}, 400

    code, msg = check_user(user_name)
    if code != 0:
        return {'code': code, 'msg': msg}

    from plugin.codemig.codemig_task_manager.query_processor import (
        query_project_migrate_extra_files, query_dir_id_by_task_id)

    # 先查询dir_id
    status, dir_id = query_dir_id_by_task_id(task_id)
    if not status:
        LOGGER.error(f"查询目录ID失败，task_id={task_id}")
        return {'code': -1, 'msg': '查询目录ID失败'}

    return query_project_migrate_extra_files(user_name, dir_id)


@codemig_task_bp.route('/files', methods=['POST'])
def query_task_files():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    user_id = request.user_id
    return query_user_task_files(user_name, task_id, user_id)


@codemig_task_bp.route('/ut_test_files', methods=['POST'])
def query_ut_test_files():
    """② 功能验证：列出 <repo>/test/ 下生成的测试产物清单（供前端节点 items 渲染）"""
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_ut_test_files_processor(user_name, dir_id)



@codemig_task_bp.route('/changes', methods=['POST'])
def query_changes():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}

    return query_changes_for_file(user_name, task_id, dir_id, file_id)


@codemig_task_bp.route('/dependence_changes', methods=['POST'])
def query_dependence_changes():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence_changes_for_file(user_name, task_id, dir_id, file_id, dependence_id)

@codemig_task_bp.route('/generate', methods=['POST'])
def query_generate():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    model = body_data.get("model")
    reference_arch_paths = body_data.get("reference_arch_paths")
    request_uuid = body_data.get("request_uuid")
    if request_uuid is None or len(request_uuid) < 1:
        return {"code":-2, "msg": "There is no request uuid in parameters"} 
    api_format = body_data.get("api_format")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}

    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=3600):
            return query_generate_for_file(user_name, task_id, dir_id, file_id, model,
                                           reference_arch_paths, request_uuid, api_format)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}

@codemig_task_bp.route('/dependence_generate', methods=['POST'])
def query_dependence_generate():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    user_id = request.user_id
    return query_dependence_generate_for_file(user_name, task_id, dir_id, file_id, dependence_id, user_id)

@codemig_task_bp.route('/filetree', methods=['POST'])
def query_file_tree():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_file_tree_processor(user_name, request.user_id, task_id, dir_id)


@codemig_task_bp.route('/original_file', methods=['POST'])
def query_original_file():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_path = body_data.get("file_path")
    return query_original_file_processor(user_name, task_id, dir_id, file_path)

@codemig_task_bp.route('/dependence_filetree', methods=['POST'])
def query_dependence_file_tree():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dependence_id = body_data.get("dependence_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence_file_tree_processor(user_name, task_id, dependence_id, user_id)


@codemig_task_bp.route('/changesave', methods=['POST'])
def save_edited_file():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    content = body_data.get("content")
    dependence_id = body_data.get("dependence_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    if dependence_id:
        return {"code": -1, "msg": "依赖包不能修改源码"}
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=20):
            return save_updated_file_with_content(user_name, dir_id, file_id, content)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/software', methods=['POST'])
def query_software_data_route():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_software(user_name, task_id)


@codemig_task_bp.route('/missing_files', methods=['POST'])
def query_missing_files_data_route():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_missing_files(user_name, task_id)


@codemig_task_bp.route('/existing_arch', methods=['POST'])
def query_existing_arch_info():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    file_id = body_data.get("file_id")
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_existing_arch(user_name, file_id, task_id, dir_id)


@codemig_task_bp.route('/dependence', methods=['POST'])
def query_dependence_data_info():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence(user_name, task_id, user_id)


@codemig_task_bp.route('/depsum', methods=['POST'])
def query_dependence_summary_info():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence_summary(user_name, task_id, user_id)

@codemig_task_bp.route('/dependence_files', methods=['POST'])
def query_task_dependence_files():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dependence_id = body_data.get("dependence_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_user_task_dependence_files(user_name, task_id, dependence_id, user_id)


@codemig_task_bp.route('/dependence_software', methods=['POST'])
def query_task_dependence_software():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dependence_id = body_data.get("dependence_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence_software(user_name, task_id, dependence_id, user_id)


@codemig_task_bp.route('/dependence_missing_files', methods=['POST'])
def query_dependence_missing_files_info():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dependence_id = body_data.get("dependence_id")
    user_id = request.user_id
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return query_dependence_missing_files(user_name, task_id, dependence_id, user_id)


@codemig_task_bp.route('/dependence_existing_arch', methods=['POST'])
def query_dependence_existing_arch_info():
    body_data = request.get_json()
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    return query_dependence_existing_arch(file_id, dependence_id)


@codemig_task_bp.route('/query_init_configuration', methods=['POST'])
def query_init_configuration():
    # body_data = request.get_json()
    user_id = request.user_id
    return get_init_configuration(user_id)


@codemig_task_bp.route('/check_file_exists', methods=['POST'])
def check_file_exists():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    return check_file_exists_handler(user_name, task_id, dir_id, file_id, dependence_id)

@codemig_task_bp.route('/save_file_content', methods=['POST'])
def save_file_content():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    content = body_data.get("content")
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=20):
            return save_file_content_handler(user_name, task_id, dir_id, file_id, 
                                             dependence_id, content)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}

@codemig_task_bp.route('/delete', methods=['POST'])
def delete_task():
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    return mark_as_deleted(task_id, request)


@codemig_task_bp.route('/create_file_or_directory', methods=['POST'])
def create_file_or_directory():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    file_path = body_data.get("file_path")
    is_directory = body_data.get("is_directory", False)
    dependence_id = body_data.get("dependence_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    if not file_path:
        return {"code": -1, "msg": "文件路径不能为空"}
    if dependence_id:
        return {"code": -1, "msg": "依赖包不支持创建文件或目录"}
    try:
        with task_file_lock(user_name, dir_id, blocking=True, timeout=10):
            return create_file_or_directory_handler(user_name, request.user_id, 
                                                    dir_id, file_path, is_directory)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/delete_file_or_directory', methods=['POST'])
def delete_file_or_directory():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    dependence_id = body_data.get("dependence_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    if dependence_id:
        return {"code": -1, "msg": "依赖包不支持创建文件或目录"}
    try:
        with task_file_lock(user_name, dir_id, blocking=True, timeout=10):
            return delete_file_or_directory_handler(user_name, dir_id, file_id)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/update_suggestion_ignored', methods=['POST'])
def update_suggestion_ignored():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    change_id = body_data.get("change_id")
    ignored = body_data.get("ignored")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return update_suggestion_ignored_handler(user_name, dir_id, file_id, change_id, ignored)

@codemig_task_bp.route('/rollback_file', methods=['POST'])
def file_rollback():
    LOGGER.info(f"Rolling back the file for the given file.")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg, "content": ""}
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=20):
            return file_rollback_handler(user_name, dir_id, file_id)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/project_file_changesave', methods=['POST'])
def save_project_file_change():
    """一键迁移：用户手动编辑代码后保存。

    与 /changesave（单文件视图 saveChanges）的差异：
    - 不触发 CodemigProcessor.process_file 重新扫描，
    - 不调用 REMOVE_SUGGESTION_OF_FILE_SQL（AI 建议行不受影响），
    - commit message 走 project-manual + src=codemig-project-migrate-view + reason=user-edit-save。
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    file_id = body_data.get("file_id")
    content = body_data.get("content")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    # AI 任务（迁移/UT/MCA）运行期间禁止保存：Agent 容器 bind mount 同一仓库，
    # 保存会与 Agent 写入互相覆盖、并把半成品误收进 user-edit-save commit。
    if is_ai_task_running(user_name, dir_id):
        return {"code": -1, "msg": "AI 任务运行中，请先停止或等待完成后再保存"}
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=20):
            return save_project_file_with_content(user_name, dir_id, file_id, content)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/migrate_project', methods=['POST'])
def migrate_project():
    LOGGER.info(f"Migrating the whole project.")
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    task_id = body_data.get("task_id")
    dir_id = body_data.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=7200):
            return query_project_migrate(body_data, request)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}


@codemig_task_bp.route('/rollback_project_migrate', methods=['POST'])
def rollback_project_migrate():
    """项目级迁移手动回退
    body 中 target_hash 可选：
    - 不传：回退到最近一次迁移前的 git commit
    - 传值：回退到指定 commit（基于 reflog 历史点，可逆）
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    target_hash = body_data.get("target_hash") or None
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return rollback_project_migrate_handler(user_name, dir_id, target_hash)


@codemig_task_bp.route('/reopen_project_ai', methods=['POST'])
def reopen_project_ai():
    """刷新后恢复最近一次项目级迁移的 AI 建议。
    v4.x：可选 stage 参数（project_migrate/ut_test）按阶段恢复；
    缺省取全部阶段里最近的一次（兼容旧行为）。"""
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    stage = body_data.get("stage") or None
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    status, ai_id, content = query_project_ai_suggestion(user_name, dir_id, stage=stage)
    if not status:
        return {"code": -1, "msg": "Failed to query project ai"}
    return {"code": 0, "data": content}


@codemig_task_bp.route('/project_ai_history', methods=['POST'])
def project_ai_history():
    """v4.x：项目级阶段历史列表（file_id=0 的 codemig_task_ai 元信息），
    供前端 AI 面板切换器展示：哪个阶段、模型、结束状态、时间。"""
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    status, records = query_project_ai_history(user_name, dir_id)
    if not status:
        return {"code": -1, "msg": "Failed to query project ai history"}
    return {"code": 0, "data": records}


@codemig_task_bp.route('/list_project_history', methods=['POST'])
def list_project_history_route():
    """列出项目迁移的所有历史快照点（基于 reflog，仅供一键迁移使用）"""
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    return list_project_migrate_history_handler(user_name, dir_id)


@codemig_task_bp.route('/generate_project_patch', methods=['POST'])
def generate_project_patch():
    """生成两个 commit 之间的增量 patch 并以文件流方式下载
    body: dir_id, from_hash(必填), to_hash(可选, 默认 HEAD)
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json()
    dir_id = body_data.get("dir_id")
    from_hash = body_data.get("from_hash")
    to_hash = body_data.get("to_hash") or None
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}

    result = generate_project_patch_handler(user_name, dir_id, from_hash, to_hash)
    if result.get("code") != 0:
        return result

    patch_content = result.get("data") or ""
    try:
        from flask import Response
        from urllib.parse import quote
    except ImportError:
        return {"code": -1, "msg": "Failed to build download response."}

    # 空补丁仍可下载，方便用户确认"无变更"
    patch_bytes = patch_content.encode('utf-8', errors='replace')
    from_hash_short = (from_hash or '')[:8]
    to_hash_short = (to_hash[:8] if to_hash else 'HEAD')
    filename = quote(f"incremental_{from_hash_short}_to_{to_hash_short}.patch")
    response = Response(patch_bytes, mimetype="text/plain")
    response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{filename}"
    return response


# ─── v5.0.0：项目级重新扫描按钮 ───
@codemig_task_bp.route('/rescan', methods=['POST'])
def task_rescan_handler():
    """启动重新扫描任务（异步线程执行）。

    body 中可显式传 user_name / dir_id / task_id；缺省取 session。
    防重入：检查 _rescan_states 中当前任务是否 status=1（运行中）。
    返回：{code, msg, total} — total 是 changed 文件总数，供前端立即渲染 "扫描中 0/total"。
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json() or {}
    dir_id = body_data.get("dir_id") or session.get("dir_id")
    task_id = body_data.get("task_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    if not dir_id:
        return {"code": -1, "msg": "missing dir_id"}

    # ★ 防重入：在请求线程内原子地"检查 + 置 status=1"，堵住 check-then-start 竞态
    #   （若第二个请求在线程启动窗口内到达，_try_mark_rescan_running 会直接拒绝）
    if not _try_mark_rescan_running(user_name, dir_id):
        return {"code": -1, "msg": "已有重扫任务在进行中"}

    # ★ 启动后台线程（daemon=True：主进程退出时自动结束）
    #   status=1 已在上面同步置位，线程内的 _set_rescan_state 只更新 total/processed
    t = threading.Thread(
        target=_do_rescan_all_files,
        args=(user_name, dir_id),
        daemon=True,
    )
    t.start()

    # ★ 立即返回 total；前端拿到后启动轮询 /task/rescan_status
    total = _count_changed_files(user_name, dir_id)
    LOGGER.info(f"Rescan task started: user={user_name}, dir_id={dir_id}, task_id={task_id}, total={total}")
    return {"code": 0, "msg": "OK", "total": total}


@codemig_task_bp.route('/rescan_status', methods=['POST'])
def task_rescan_status_handler():
    """查询重扫状态：前端每 5s/10s 轮询一次。

    返回字段：
      - status: 0=空闲 / 1=运行中 / 2=成功 / 3=失败
      - processed: 已处理文件数
      - total: 总文件数
      - fail_reason: 失败原因（status=3 时非空）
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    body_data = request.get_json() or {}
    dir_id = body_data.get("dir_id") or session.get("dir_id")
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    if not dir_id:
        return {"code": -1, "msg": "missing dir_id"}

    state = _get_rescan_state(user_name, dir_id)
    return {
        "code": 0,
        "msg": "OK",
        "status": state["status"],
        "processed": state["processed"],
        "total": state["total"],
        "fail_reason": state.get("fail_reason", ""),
    }