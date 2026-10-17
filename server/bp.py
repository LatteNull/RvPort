import time

from flask import Blueprint, request, abort, session, jsonify, make_response

from common.public.public import SECONDS_PER_MINUTE
from framework.config_manager.config import SysConfig, ConfigKeys, SESSION_TIMEOUT_DEFAULT
from framework.config_manager.views import config_bp
from framework.dashboard.views import dashboard_bp
from framework.log_manager.views import log_bp
from framework.plugin_manager.views import pluginmanager_bp
from framework.user_manager.user_update_cache import refresh_last_logout
from framework.user_manager.views import auth_bp, user_bp
from session_cache import UserSessionCache
from version import get_master_version

auto_refesh_url = ['/action/plugin/codemig/task/list',
                   'action/plugin/codemig/task/dependence']

action_bp = Blueprint('action', __name__, url_prefix='/action')
print("action_bp init ok")

action_bp.register_blueprint(auth_bp)
action_bp.register_blueprint(user_bp)
action_bp.register_blueprint(config_bp)
action_bp.register_blueprint(dashboard_bp)
action_bp.register_blueprint(log_bp)
action_bp.register_blueprint(pluginmanager_bp)
print("framework register_blueprint ok")


@action_bp.route('/version', methods=['GET'])
def get_version():
    return {"code": 0, "msg": "ok", "data": {"version": get_master_version()}}


# Started by AICoder, pid:zc6c3bcad9w9b4c141a9097600ac884a76751705
def validate_csrf():
    """
    校验 CSRF Token
    """
    if "X-Csrftoken" not in session:
        return False
    csrf_token = request.headers.get('X-Csrftoken')
    return csrf_token == UserSessionCache.get_user_token(session.get("user_id")) and session.get(
        "X-Csrftoken") == csrf_token


def validate_session_exp_time():
    if "X-Csrftoken" in session:
        user_id = session.get("user_id")
        last_time = UserSessionCache.get_user_last_time(user_id)
        # last_time = get_user_last_time(user_id)

        status, timeout, _ = SysConfig.query_system_configuration(
            ConfigKeys.SESSION_TIMEOUT)
        if not status:
            timeout = SESSION_TIMEOUT_DEFAULT
        if last_time and int(time.time()) > int(last_time) + int(timeout) * SECONDS_PER_MINUTE:
            session.pop("X-Csrftoken")
            session.pop("user_id")
            session.pop("user_name")
            UserSessionCache.delete_user_session(user_id)
            return False
        return True
    return False


def validate_session():
    flag = validate_csrf()
    if not flag:
        return False
    return validate_session_exp_time()
    # return True


def set_user_info():
    """
    设置用户信息 (user_id, user_name)
    """
    request.user_id = session.get("user_id")
    request.user_name = session.get("user_name")


# Ended by AICoder, pid:zc6c3bcad9w9b4c141a9097600ac884a76751705

def update_session_exp_time(response):
    if response.status_code != 401 and 'user_id' in session and not (
            request.path in auto_refesh_url):
        now = time.time()
        UserSessionCache.update_user_last_time(session.get("user_id"), now)
        refresh_last_logout(session.get("user_id"), now)


@action_bp.before_request
def before():
    """
    针对app实例定义全局拦截器
    """
    url = request.path  # 读取到当前接口的地址
    # url中不能出现的字符
    if any(char in url for char in [".bash_history", "./", ".."]):
        abort(400)
    # Started by AICoder, pid:xd2b5n2e9ene6f4144ba086a8047a11d77454585
    if url in ('/action/auth/login', '/action/auth/admin'):
        return None

    # 检查URL和会话中的CSRF token
    if "/action/" not in url:
        return None

    if not validate_session():
        if url == '/action/auth/logout':
            response = make_response(jsonify({
                "status": "error",
                "code": "AUTH_REQUIRED",
                "message": "Not logined in."
            }), 200)
            return response
        abort(401)
    set_user_info()
    if ("logged_in" not in session or not session['logged_in']) and '/action/auth' not in url:
        abort(401)
    return None

    # Ended by AICoder, pid:xd2b5n2e9ene6f4144ba086a8047a11d77454585


@action_bp.after_request
def modify_response(response):
    # 在每个请求完成后，修改响应的状态码
    if "/action/" in request.path:
        response.headers["Content-Type"] = response.content_type.split(";")[0] + "; charset=UTF-8"
        if not response.is_streamed:
            resp = response.get_json()
            if resp and resp.get('code', 0) == 1:
                response.status_code = 400
            update_session_exp_time(response)
    return response
