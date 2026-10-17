import os
import subprocess
import sys

from flask import Blueprint, request, jsonify, session
from functools import wraps

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.response.response_code import ResponseCode
from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_for_change, \
    cancel_ai_suggestion_by_id, query_reopen_ai_suggestion, set_ai_score, \
    get_ai_score, \
    insert_manual_suggestion_handler, \
    delete_manual_suggestion_handler, \
    list_manual_suggestions_by_dir_handler, \
    run_ut_test, \
    query_project_migrate, \
    _resumable_status_all_stages, \
    force_commit_marker
from plugin.codemig.ai_assistant.api_key_manager import store_api_key_to_db, \
    get_api_key_from_db, del_api_key_from_db, set_default_api_key_to_db, \
    set_model_default_api_key_to_db, test_api_key_by_post
from framework.user_manager.user_db import UserManager
from plugin.codemig.codemig_common.common_lock import task_file_lock
from plugin.codemig.codemig_task_manager.views import check_user


LOGGER = logger.init_log('codemig')
codemig_ai_bp = Blueprint('advise', __name__, url_prefix='/advise')

def require_admin_role(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 注意：确保 request.user_id 已被中间件/登录逻辑设置
        user_id = getattr(request, 'user_id', None)
        if user_id is None:
            return jsonify({
                "code": -1,
                "msg": "未登录或用户信息缺失",
                "data": ""
            }), 401

        user = UserManager.query_by_id(user_id)
        if not user or user.role != 'admin':
            return jsonify({
                "code": -1,
                "msg": "该用户无操作权限",
                "data": ""
            }), 403  # 403 表示权限不足

        return f(*args, **kwargs)
    return decorated_function


def _get_user_role_info():
    """获取当前请求用户的 (user_id, is_admin) 信息"""
    user_id = getattr(request, 'user_id', None)
    is_admin = False
    if user_id is not None:
        user = UserManager.query_by_id(user_id)
        if user and user.role == 'admin':
            is_admin = True
    return user_id, is_admin

@codemig_ai_bp.route('/ai_suggestion', methods=['POST'])
def query_ai_suggestion():
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unkown user."}
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json()
    dir_id = parameters.get("dir_id")
    task_id = parameters.get("task_id")
    request_uuid = parameters.get("request_uuid")
    if request_uuid is None or len(request_uuid) < 1:
        return {"code":-2, "msg": "There is no request uuid in parameters"} 

    # 执行 AI 建议查询
    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=3600):
            return query_ai_suggestion_for_change(parameters, request)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}

@codemig_ai_bp.route('/ai_suggestion_cancel', methods=['POST'])
def cancel_ai_suggestion():
    LOGGER.info(f"Cancel the AI suggestion for the given suggestion.")
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json()
    request_uuid = parameters.get('request_uuid')
    if not request_uuid:
        return {"code": -1, "msg": "Missing 'request_uuid' in parameters"}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}

    return cancel_ai_suggestion_by_id(user_name, dir_id, request_uuid)

@codemig_ai_bp.route('/api_key_store', methods=['POST'])
def store_api_key():
    data = request.get_json()
    user_id = getattr(request, 'user_id', None)
    return store_api_key_to_db(user_id, data, getattr(request, 'remote_addr', None))

@codemig_ai_bp.route('/api_key_set_default', methods=['POST'])
def set_default_api_key():
    data = request.get_json()
    user_id, is_admin = _get_user_role_info()
    return set_default_api_key_to_db(
        data, user_id=user_id, login_ip=getattr(request, 'remote_addr', None), is_admin=is_admin)

@codemig_ai_bp.route('/api_key_set_model_default', methods=['POST'])
def set_model_default_api_key():
    data = request.get_json()
    user_id, is_admin = _get_user_role_info()
    return set_model_default_api_key_to_db(
        data, user_id=user_id, login_ip=getattr(request, 'remote_addr', None), is_admin=is_admin)

@codemig_ai_bp.route('/api_key_get', methods=['GET'])
def get_api_key():
    user_id, is_admin = _get_user_role_info()
    return get_api_key_from_db(user_id=user_id, is_admin=is_admin)

@codemig_ai_bp.route('/api_key_del', methods=['POST'])
def del_api_key():
    data = request.get_json()
    user_id, is_admin = _get_user_role_info()
    return del_api_key_from_db(user_id, data, getattr(request, 'remote_addr', None), is_admin=is_admin)

@codemig_ai_bp.route('/api_key_test', methods=['POST'])
def test_api_key():
    data = request.get_json()
    user_id = getattr(request, 'user_id', None)
    return test_api_key_by_post(
        data, user_id=user_id, login_ip=getattr(request, 'remote_addr', None))


@codemig_ai_bp.route('/ai_score_set', methods=['POST'])
@require_admin_role
def ai_score_set():
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json()
    file_id = parameters.get('file_id')
    if file_id is None:
        return {"code": -1, "msg": "Missing 'file_id' in parameters"}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    score = parameters.get('score')
    if score is None:
        return {"code": -1, "msg": "Missing 'score' in parameters"}
    ai_id = parameters.get('ai_id')

    result, msg = set_ai_score(user_name, dir_id, file_id, ai_id, score)
    if not result:
        return {"code": -1, "msg": msg}
    return {"code": 0, "msg": ResponseCode.OK}

@codemig_ai_bp.route('/ai_score_get', methods=['POST'])
def ai_score_get():
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json()
    file_id = parameters.get('file_id')
    if file_id is None:
        return {"code": -1, "msg": "Missing 'file_id' in parameters"}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    uuid = parameters.get('uuid')
    score = 5
    status = False
    status, score = get_ai_score(user_name, dir_id, file_id, uuid)
    if not status:
        return {"code": -1, "msg": "Failed to get ai score"}
    return {"code": 0, "msg": ResponseCode.OK, "data": score}

@codemig_ai_bp.route('/reopen_ai_suggestion', methods=['POST'])
def reopen_ai_suggestion():
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json()
    file_id = parameters.get('file_id')
    if file_id is None:
        return {"code": -1, "msg": "Missing 'file_id' in parameters"}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    ai_id = parameters.get('ai_id')
    status, new_id, content = query_reopen_ai_suggestion(user_name, dir_id, file_id, ai_id)
    if not status:
        return {"code": -1, "msg": "Failed to reopen ai suggestion"}
    return {"code": 0, "msg": ResponseCode.OK, "id": new_id, "data": content}


# ─────────────────────────────────────────────────────────────────────
#  项目级一键迁移 · 阶段技能路由（v4.x.0-RUN-FLOW）
#   - ② POST /action/plugin/codemig/advise/skill/ut_test      → run_ut_test（②功能验证）
#  路由挂在 codemig_ai_bp（url_prefix='/advise'）下，所以实际路径前缀是
#  /action/plugin/codemig/advise/skill/...
#  参数体与 /task/migrate_project 保持同一形态：user_name、task_id、dir_id、
#  agent_model、api_format、request_uuid。流式 SSE 响应。
# ─────────────────────────────────────────────────────────────────────

@codemig_ai_bp.route('/skill/ut_test', methods=['POST'])
def run_ut_test_view():
    """
    ② 功能验证：注入 ut_test skill，对现有 RISC-V 迁移产物生成可对比输出的单元测试
    并交叉编译 + qemu 回归。
    """
    if 'user_name' not in session:
        return {"code": -1, "msg": "Unknown user."}
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    # 防御：用户名由 session 拿，不信任请求体里的 user_name
    parameters["user_name"] = user_name

    task_id = parameters.get("task_id")
    dir_id = parameters.get("dir_id")
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}

    try:
        with task_file_lock(user_name, dir_id, task_id, blocking=True, timeout=7200):
            return run_ut_test(parameters, request)
    except RuntimeError as e:
        return {"code": -1, "msg": str(e)}



# ─────────────────────────────────────────────────────────────────────
#  一键迁移：用户手动选中的代码段持久化（v4.0）
#  数据源：codemig_task_directory_file_suggestion 表 is_manual=1 的行
#  与单文件迁移扫描器产出（is_manual=0）通过 is_manual 字段正交解耦
# ─────────────────────────────────────────────────────────────────────

@codemig_ai_bp.route('/suggestion/insert_manual', methods=['POST'])
def insert_manual_suggestion():
    """单条插入 manual 选中段（用户点击"添加到 AI 建议"时立即入库）

    请求体：{"user_name": str, "dir_id": int, "file_id": int,
             "start_line": int, "end_line": int,
             "suggestion": str, "append_or_replace": int}
    """
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    file_id = parameters.get('file_id')
    start_line = parameters.get('start_line')
    end_line = parameters.get('end_line')
    suggestion = parameters.get('suggestion') or ''
    append_or_replace = parameters.get('append_or_replace', 2)
    missing = [
        k for k, v in (
            ('dir_id', dir_id), ('file_id', file_id),
            ('start_line', start_line), ('end_line', end_line)
        ) if v is None
    ]
    if missing:
        return {"code": -1, "msg": f"Missing {missing} in parameters"}
    return insert_manual_suggestion_handler(
        user_name, dir_id, file_id,
        int(start_line), int(end_line), suggestion, int(append_or_replace))


@codemig_ai_bp.route('/suggestion/delete_manual', methods=['POST'])
def delete_manual_suggestion():
    """删除一条 manual 选中段（按 file_id + start_line + end_line 定位）

    请求体：{"user_name": str, "dir_id": int, "file_id": int,
             "start_line": int, "end_line": int}
    """
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    file_id = parameters.get('file_id')
    start_line = parameters.get('start_line')
    end_line = parameters.get('end_line')
    missing = [
        k for k, v in (
            ('dir_id', dir_id), ('file_id', file_id),
            ('start_line', start_line), ('end_line', end_line)
        ) if v is None
    ]
    if missing:
        return {"code": -1, "msg": f"Missing {missing} in parameters"}
    return delete_manual_suggestion_handler(
        user_name, dir_id, file_id, int(start_line), int(end_line))


@codemig_ai_bp.route('/suggestion/list_manual_by_dir', methods=['POST'])
def list_manual_suggestions_by_dir():
    """查询某 dir 下所有 manual 选中段

    请求体：{"user_name": str, "dir_id": int}
    返回：{"code": 0, "selections": [{"file_id", "file_path", "start_line", "end_line"}, ...]}
    """
    user_name = session['user_name']
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    return list_manual_suggestions_by_dir_handler(user_name, dir_id)


# =============================================================================
# v4.x.0-RESUME 一键迁移中断恢复路由
#   - /advise/skill/migrate_resume        POST  进入"继续"
#   - /advise/skill/migrate_resumable_status  POST  探测三阶段是否可恢复
# =============================================================================
RESUME_STAGE_TO_IMPL = {
    'project_migrate': query_project_migrate,
    'ut_test': run_ut_test,
}


@codemig_ai_bp.route('/skill/migrate_resume', methods=['POST'])
def migrate_resume_view():
    """
    一键迁移"继续"按钮路由。

    请求体：{"dir_id": int, "stage": "project_migrate"|"ut_test",
             "model"?: str, "request_uuid"?: str (后端自动生成)}
    行为：注入 parameters['_resume']=True 后透传给对应阶段的 impl。
    """
    user_name = session.get('user_name')
    if not user_name:
        return {"code": -1, "msg": "Unknown user."}
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    stage = parameters.get('stage') or 'project_migrate'
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    if stage not in RESUME_STAGE_TO_IMPL:
        return {"code": -1, "msg": f"Unknown stage: {stage}"}
    # 后端不强制传 request_uuid（impl 会自己生成），但若前端传了就用前端的
    if not parameters.get('request_uuid'):
        import uuid as _uuid
        parameters['request_uuid'] = str(_uuid.uuid4())
    parameters['_resume'] = True
    # 一键迁移 / ut_test impl 签名都是 (parameters, request)，
    # 与 query_project_migrate 一致。
    impl = RESUME_STAGE_TO_IMPL[stage]
    try:
        return impl(parameters, request)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        LOGGER.error(f"[migrate_resume] {stage} error: {e}", exc_info=True)
        return {"code": -1, "msg": str(e)}


@codemig_ai_bp.route('/skill/migrate_resumable_status', methods=['POST'])
def migrate_resumable_status_view():
    """
    探测一键迁移各阶段是否各自存在可恢复的 qwen 会话。

    请求体：{"dir_id": int}
    返回：{"code": 0,
            "stages": {"project_migrate": {...}, "ut_test": {...}}}
    """
    user_name = session.get('user_name')
    if not user_name:
        return {"code": -1, "msg": "Unknown user."}
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    if dir_id is None:
        return {"code": -1, "msg": "Missing 'dir_id' in parameters"}
    try:
        stages = _resumable_status_all_stages(user_name, dir_id)
        return {"code": 0, "msg": "ok", "stages": stages}
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        LOGGER.error(f"[migrate_resumable_status] error: {e}", exc_info=True)
        return {"code": -1, "msg": str(e)}


@codemig_ai_bp.route('/skill/boundary_commit', methods=['POST'])
def migrate_boundary_commit_view():
    """
    前端硬边界 commit 入口（v3.2 改造产物）。

    请求体：{
        "user_name": str,
        "dir_id": int,
        "reason": str,   # 必须在 COMMIT_REASON_WHITELIST 内
        "src"?: str,     # 默认 'codemig-boundary'
        "stage"?: str,   # 默认 'marker'
        "type"?: str,    # 默认 'marker'
    }

    行为：调 force_commit_marker 产生硬边界 commit（allow-empty=True），
    返回 commit hash。

    调用方（前端）：
      - _preBoundaryCommit（点击"运行"/"继续"瞬间）
      - _postBoundaryCommit（阶段 success/error/cancel 收尾）
      - _preResumeBoundaryCommit（点击"继续"瞬间）

    设计动机：
      - 把 commit 的"何时产生"决策权完全交给前端（用户动作触发）
      - 后端只在 finally 块做兜底（agent-finish / interrupted）→ 改造 5/6
    """
    user_name = session.get('user_name')
    if not user_name:
        return {"code": -1, "msg": "Unknown user."}
    code, msg = check_user(user_name)
    if code != 0:
        return {"code": code, "msg": msg}
    parameters = request.get_json() or {}
    dir_id = parameters.get('dir_id')
    reason = parameters.get('reason')
    if dir_id is None or not reason:
        return {"code": -1, "msg": "Missing 'dir_id' or 'reason'"}
    # 白名单校验（双重保险：路由层 + force_commit_marker 内部）
    # 注意：项目导入约定省略 'server.' 前缀（MODULE_PATH 已把 server/ 注入 sys.path）
    from plugin.codemig.codemig_common.common_git import COMMIT_REASON_WHITELIST
    if reason not in COMMIT_REASON_WHITELIST:
        return {"code": -1, "msg": f"Invalid reason: {reason}"}
    sha = force_commit_marker(
        user_name=user_name,
        dir_id=dir_id,
        reason=reason,
        src=parameters.get('src', 'codemig-boundary'),
        stage=parameters.get('stage', 'marker'),
        type=parameters.get('type', 'marker'),
    )
    if sha:
        return {"code": 0, "msg": "Boundary commit created", "sha": sha}
    return {"code": 1, "msg": "Force commit failed"}