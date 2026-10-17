# Started by AICoder, pid:14029n2c88h21fd14b83098040974103b5e133ff
import json
import secrets
from flask import Blueprint
from flask import request, session, make_response, jsonify, abort

from common.response.code2string import getI18n
from common.response.response_code import ResponseCode
from framework.user_manager import user_manager, login_manager
from framework.user_manager.user_db import Role
from session_cache import UserSessionCache

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
user_bp = Blueprint('user', __name__, url_prefix='/user')


# Ended by AICoder, pid:14029n2c88h21fd14b83098040974103b5e133ff
def insert_session(login_user, logged_in):
    session['logged_in'] = logged_in
    session['user_name'] = login_user.get('user_name')
    session['user_id'] = login_user.get('user_id')
    random_string = secrets.token_hex(32)
    session['X-Csrftoken'] = random_string
    UserSessionCache.set_user_session(login_user.get('user_id'), random_string, request.remote_addr,
                                      role=1 if login_user.get('user_name') == 'Admin'
                                                and login_user.get('role') == Role.ADMIN else 0)


def clear_session():
    UserSessionCache.delete_user_session(request.user_id)
    session.clear()


def generic_login(username, password, remote_ip, admin=False):
    status, login_user, code = login_manager.login(username, password, remote_ip, admin)
    resp = {'code': 0, 'msg': 'ok'}
    if status:
        resp['msg'] = json.dumps(login_user)
        insert_session(login_user, True)
        response = make_response(jsonify(resp))
        response.headers['X-Csrftoken'] = session['X-Csrftoken']
        return response
    if code in (ResponseCode.USER_FIRST_LOGIN, ResponseCode.PW_TIMEOUT):
        insert_session(login_user, False)
        response = make_response(jsonify({"code": 2, "msg": getI18n(code, 'zh')}))
        response.headers['X-Csrftoken'] = session['X-Csrftoken']
        return response
    return {"code": 1, "msg": getI18n(code, 'zh')}


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/auth/login \
# -H 'Content-Type: application/json' \
# -d '{
# "username":"--",
# "password": "--"
# }'
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data["username"]
    password = data["password"]

    remote_ip = request.remote_addr
    return generic_login(username, password, remote_ip)


@auth_bp.route('/admin', methods=['POST'])
def verify_admin():
    data = request.get_json()
    username = data["username"]
    password = data["password"]
    remote_ip = request.remote_addr
    return generic_login(username, password, remote_ip, admin=True)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    login_manager.logout(request)
    clear_session()
    return {
        "code": 0,
        "msg": "ok"
    }


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8080/action/auth/modify_password \
# -H 'Content-Type: application/json' \
# -H 'X-Csrftoken: 13b8947b959d71dfa44094528a64b63a52f3ec58fe351a49367a0d40ce21f507' \
# -d '{
# "username":"--",
# "old_password": "--",
# "new_password": "--"
# }'
@auth_bp.route('/modify-password', methods=['POST'])
def modify_password():
    data = request.get_json()
    params = {'user_name': data["username"],
              'old_password': data["old_password"], 'new_password': data["new_password"]}

    status, info = user_manager.modify(params, request)
    if not status:
        return {
            "code": -1,
            "msg": getI18n(info, 'zh')
        }
    clear_session()
    return {
        "code": 0,
        "msg": info
    }


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/auth/reset-password \
# -H 'Content-Type: application/json' \
# -H 'X-Csrftoken: 13b8947b959d71dfa44094528a64b63a52f3ec58fe351a49367a0d40ce21f507' \
# -d '{
# "username":"--",
# "admin_password": "--."，
# "new_password": "--"
# }'
@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    params = {'user_name': data["username"],
              'admin_password': data["admin_password"], 'new_password': data["new_password"]}

    status, info = user_manager.reset_pw(params, request)
    if not status:
        return {
            "code": -1,
            "msg": getI18n(info, 'zh')
        }
    return {
        "code": 0,
        "msg": info
    }


# curl -i -X GET --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/user/list \
# -H 'Content-Type: application/json' \
# -H 'X-Csrftoken: 13b8947b959d71dfa44094528a64b63a52f3ec58fe351a49367a0d40ce21f507'
@user_bp.route('/list', methods=['GET'])
def list_local():
    user_id = request.user_id
    status, code, users = user_manager.list_user(user_id)
    if not status:
        return {
            "code": -1,
            "msg": code
        }
    user_list = []
    for user in users:
        user_list.append({
            'user_id': user.user_id,
            'user_name': user.user_name,
            'role': user.role,
            'status': user.status,
        })
    return {
        "code": 0,
        "msg": code,
        "data": user_list
    }


# curl -i -X DELETE --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/user/rm/<id> \
# -H 'Content-Type: application/json' \
# -H 'X-Csrftoken: 13b8947b959d71dfa44094528a64b63a52f3ec58fe351a49367a0d40ce21f507' \
# -d '{
# "admin_password":"--",
# "delete_task":"False"
# }'
@user_bp.route('rm/<user_id>', methods=['POST'])
def delete(user_id):
    data = request.get_json()
    status, code = user_manager.delete_user(user_id, data, request)
    if status:
        UserSessionCache.delete_user_session(user_id)
    return {
        "code": 0 if status else -1,
        "msg": getI18n(code, 'zh')
    }


# curl -i -X POST --noproxy 127.0.0.1 \
# http://127.0.0.1:8094/action/user \
# -H 'Content-Type: application/json' \
# -H 'X-Csrftoken: 13b8947b959d71dfa44094528a64b63a52f3ec58fe351a49367a0d40ce21f507' \
# -d '{
# "admin_password":"--",
# "password":"--",
# "role":"normal",
# "user_name":"--"
# }'
@user_bp.route('', methods=['POST'])
def create():
    data = request.get_json()
    status, code, user = user_manager.create(data, request)
    if not status:
        return {
            "code": -1,
            "msg": '\n'.join([getI18n(c, 'zh') for c in code])
        }
    return {
        "code": 0,
        "msg": code,
        "data": user
    }
