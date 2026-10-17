import os
import sys
import time

from datetime import datetime, timedelta

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from session_cache import UserSessionCache
from common.public.public import SECONDS_PER_MINUTE
from common.public import logger
from common.response.code2string import getI18n
from common.response.response_code import ResponseCode
from framework.user_manager.user_db import UserStatus, Role, UserLoginFailedTime, UserFailedLogin, \
    IPFailedLogin, UserManager
from framework.log_manager import operation_log
from framework.log_manager.operation_constant import OpLogResult, OpLogModule, OpLogEvent
from framework.config_manager.config import SysConfig, ConfigKeys
from framework.user_manager.user_manager import validate_pw

LOGGER = logger.init_log('usermanager')


def _clean_failed_record(login_user, ip):
    UserLoginFailedTime.clean_failed_record(login_user.user_id)
    if login_user.status == UserStatus.LOCKED:
        UserManager.update(login_user.user_id, status=UserStatus.NORMAL)
        operation_log.record_operation_log(login_user.user_id, ip, OpLogModule.SYSTEM,
                                           OpLogEvent.LOGIN, OpLogResult.SUCCESS,
                                           f'User {login_user.user_name} is unlocked.')


def _check_max_online_user(login_user):
    if login_user.role == Role.ADMIN and login_user.user_name == 'Admin':
        return False
    current_time = int(time.time())
    last_login = UserSessionCache.get_user_last_time(login_user.user_id)
    session_timeout = (int(SysConfig.query_system_configuration(ConfigKeys.SESSION_TIMEOUT)[1])
                       * SECONDS_PER_MINUTE)
    if last_login and int(last_login) > current_time - session_timeout:
        return False
    max_online = int(SysConfig.query_system_configuration(ConfigKeys.MAX_ONLINE_USERS)[1])
    users = UserSessionCache.get_online_users(current_time - session_timeout)
    online_num = len(users)
    if online_num >= max_online:
        return True
    return False


def _check_pw_expired(login_user):
    time_pw_reset = login_user.time_pw_reset
    config_pw_timeout = int(SysConfig.query_system_configuration(ConfigKeys.PW_TIMEOUT)[1])  # 单位：天
    now = int(time.time())
    if (time_pw_reset and config_pw_timeout != 0
            and time_pw_reset + config_pw_timeout * 24 * 60 * 60 < now):
        return True
    return False


def _calculate_duration(login_time, logout_time):
    duration = logout_time - login_time if logout_time and login_time else 0 if login_time else "--"
    if duration != "--":
        duration = int(duration) if duration > 0 else 0
    return duration


def _login_result(login_user, failed_count, expired):
    result = not login_user.is_first_login and not expired
    rcode = ResponseCode.PW_TIMEOUT if expired else ResponseCode.USER_FIRST_LOGIN \
        if login_user.is_first_login else ResponseCode.OK
    login_time = login_user.last_login
    logout_time = login_user.last_logout
    duration = _calculate_duration(login_time, logout_time)
    login_user = {'user_id': login_user.user_id, 'user_name': login_user.user_name,
                  'role': login_user.role,
                  'last_login': datetime.fromtimestamp(login_time).strftime(
                      "%Y-%m-%d %H:%M:%S") if login_time else None,
                  'last_login_ip': login_user.last_login_ip, 'last_login_duration': duration,
                  'auth_failed': failed_count}
    return result, login_user, rcode


def _login(user_name, password, ip="127.0.0.1", admin=False):
    login_time = time.time()
    ip_locked = IPFailedLogin.get_lock_status(ip, login_time)
    if ip_locked:
        return False, None, ResponseCode.IP_LOCKED
    login_user = UserManager.query(nopw=False, user_name=user_name, provider_id=-1)
    if not login_user:
        ip_locked = IPFailedLogin.record_and_check(ip, login_time)
        locked = UserFailedLogin.record_and_check(user_name)
        if ip_locked:
            UserSessionCache.kick_ip(ip)
            return False, None, ResponseCode.IP_LOCKED
        if locked:
            return False, None, ResponseCode.USER_LOCKED
        return False, None, ResponseCode.USER_AUTH_FAILED
    if admin and login_user.role != Role.ADMIN:
        return False, {'user_id': login_user.user_id}, ResponseCode.NON_PRIVILEGED
    valid, locked = validate_pw(password, login_user, ip, login_time)
    if not valid:
        if locked == 2:
            return False, {'user_id': login_user.user_id}, ResponseCode.IP_LOCKED
        if locked == 1:
            return False, {'user_id': login_user.user_id}, ResponseCode.USER_LOCKED
        else:
            return False, {'user_id': login_user.user_id}, ResponseCode.USER_AUTH_FAILED
    failed_count = UserLoginFailedTime.get_count(login_user.user_id)
    _clean_failed_record(login_user, ip)

    limit = _check_max_online_user(login_user)
    if limit:
        return False, {'user_id': login_user.user_id}, ResponseCode.USER_OVER_MAX_ONLINE
    expired = _check_pw_expired(login_user)
    last_login = int(datetime.now().timestamp())
    UserManager.update(login_user.user_id, last_login=last_login, last_login_ip=ip)
    return _login_result(login_user, failed_count, expired)


def login(user_name, password, ip="127.0.0.1", admin=False):
    status, login_user, code = _login(user_name, password, ip, admin)
    if status:
        operation_log.record_operation_log(login_user.get('user_id'), ip, OpLogModule.SYSTEM,
                                           OpLogEvent.LOGIN, OpLogResult.SUCCESS,
                                           'Login successfully.')
    else:
        op_result = OpLogResult.SUCCESS \
            if code in [ResponseCode.USER_FIRST_LOGIN, ResponseCode.PW_TIMEOUT] \
            else OpLogResult.FAILED
        user_id = login_user.get('user_id') if login_user else ''
        operation_log.record_operation_log(user_id, ip, OpLogModule.SYSTEM, OpLogEvent.LOGIN,
                                           op_result, getI18n(code), user_name=user_name)
    return status, login_user, code


def logout(request):
    user_id = request.user_id
    login_user = UserManager.query(user_id=user_id)
    if login_user:
        operation_log.record_operation_log(login_user.user_id, request.remote_addr,
                                           OpLogModule.SYSTEM, 'Logout', OpLogResult.SUCCESS,
                                           'Logout successfully.')
        UserManager.update(user_id, last_logout=time.time())
