import os
import re
import sys
import time
import threading
from flask import session

from dataclasses import dataclass

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.response.response_code import ResponseCode
from common.response.code2string import getI18n
from common.public import logger
from session_cache import UserSessionCache
from framework.log_manager import operation_log
from framework.log_manager.operation_constant import OpLogModule, OpLogResult, OpLogEvent
from framework.user_manager.user_db import Role, UserStatus, UserLoginFailedTime, UserFailedLogin, \
    IPFailedLogin, UserManager, UserPasswordHistory
from framework.user_manager.weak_pwd import WeakPwd
from framework.user_manager import user_db as user_service
from framework.plugin_manager.plugin_cache import remove_for_user

LOGGER = logger.init_log('usermanager')
MAX_USERNAME_LENGTH = 32


def _check_before_create(op_usr, username, password, role):
    error_list = []
    if op_usr is None or op_usr.role != Role.ADMIN:
        error_list.append(ResponseCode.NON_PRIVILEGED)

    status, code = _check_username_legal(username)
    if not status:
        error_list.append(code)

    status, code = _check_password_legal(password, username)
    if not status:
        error_list.append(code)

    if role not in Role.__dict__.values():
        error_list.append(ResponseCode.USER_ROLE_ILLEGAL)
    return error_list


@dataclass
class OperationContext:
    """操作上下文数据类"""
    user_id: str
    remote_ip: str
    user_name: str = ""


class OperationLogger:
    """操作日志记录器"""

    @staticmethod
    def record_auth_failure(context: OperationContext, operation: str, target_user: str,
                            lock_type: int, module: OpLogModule = OpLogModule.USER):
        """记录认证失败日志"""
        lock_messages = {
            2: f"due to IP locked",
            1: f"due to excessive failed attempts",
            0: f"because the password is incorrect"
        }

        message = (f"Failed to {operation} for {target_user} "
                   f"{lock_messages.get(lock_type, 'due to authentication failure')}.")

        operation_log.record_operation_log(
            context.user_id, context.remote_ip, module, operation,
            OpLogResult.FAILED, message
        )

    @staticmethod
    def record_operation(context: OperationContext, operation: str, result: OpLogResult,
                         message: str, module: OpLogModule = OpLogModule.USER):
        """记录操作日志"""
        operation_log.record_operation_log(
            context.user_id, context.remote_ip, module, operation, result, message
        )


def create(params, request):
    context = OperationContext(
        user_id=getattr(request, 'user_id', ''),
        remote_ip=getattr(request, 'remote_addr', '')
    )
    op_usr = UserManager.query_by_id(context.user_id, nopw=False)
    username = params.get('user_name', '')
    password = str(params.get('password', ''))
    role = params.get('role', Role.NORMAL).lower()
    error_list = _check_before_create(op_usr, username, password, role)
    if len(error_list) > 0:
        OperationLogger.record_operation(
            context, OpLogEvent.CREATE_USER, OpLogResult.FAILED,
            f"Failed to create {username} due to: {';'.join(getI18n(e) for e in error_list)}"
        )
        return False, error_list, None
    admin_password = params.get('admin_password', '')
    valid, locked = validate_pw(admin_password, op_usr, context.remote_ip)
    if not valid:
        OperationLogger.record_auth_failure(context, OpLogEvent.CREATE_USER, username, locked)
        return False, [ResponseCode.USER_AUTH_FAILED], None

    status, user_id = UserManager.save(username, role, password)
    if not status:
        OperationLogger.record_operation(context, OpLogEvent.CREATE_USER, OpLogResult.FAILED,
                                         f"Failed to create {username} due to database error")
        error_list.append(ResponseCode.USER_SAVEDB_ERROR)
        return False, [ResponseCode.USER_SAVEDB_ERROR], None
    # Ended by AICoder, pid:eb8147f56fme0cb14460088740dc8709ada29a8f

    created_user = UserManager.query_by_id(user_id)
    UserFailedLogin.clean_failed_record(username)
    login_user = {'user_id': user_id, 'user_name': username, 'role': role}
    OperationLogger.record_operation(context, OpLogEvent.CREATE_USER, OpLogResult.SUCCESS,
                                     f"Successfully created user: {username}")
    return status, error_list, login_user


def _check_modify_privileged(op_usr_id, user):
    if op_usr_id is None:
        return False, ResponseCode.NON_PRIVILEGED

    op_usr = UserManager.query_by_id(op_usr_id)
    if op_usr is None:
        return False, ResponseCode.NON_PRIVILEGED

    if user is None:
        return False, ResponseCode.USER_NOT_EXIST
    user_id = user.user_id

    if user_id != op_usr_id:
        return False, ResponseCode.NON_PRIVILEGED
    return True, None


def _deal_pw_failed(user, ip, valid_time=None):
    """ 记录失败的登录尝试 """
    ip_locked = IPFailedLogin.record_and_check(ip, valid_time)
    UserLoginFailedTime.record_user_failed(user.user_id, ip)
    locked = UserFailedLogin.record_and_check(user.user_name, valid_time)
    if user.status == UserStatus.NORMAL and locked:
        UserManager.update(user.user_id, status=UserStatus.LOCKED)
    if not locked and user.status == UserStatus.LOCKED:
        UserManager.update(user.user_id, status=UserStatus.NORMAL)
    if ip_locked or locked:
        try:
            if ip_locked:
                UserSessionCache.kick_ip(ip)
            if session and 'logged_in' in session:
                session.pop("logged_in")
        except (TypeError, KeyError, ValueError, AttributeError, IndexError) as e:
            pass
    return 2 if ip_locked else (1 if locked else 0)


def validate_pw(pw_to_check, user, ip="127.0.0.1", valid_time=None):
    # 返回值：密码是否正确，是否被新锁定
    pw_in_cb = user.pw
    salt = int(pw_in_cb[0:24], 16).to_bytes(12, byteorder='big')
    dk = user_service.encrypt_password(pw_to_check, salt)
    # pw 是只读属性，不能删除，只清零即可
    # user.pw = '0' * len(user.pw)  # 不能设置只读属性
    # del user.pw  # 不能删除只读属性
    # 直接使用 password 字段清零（如果存在且非空）
    if hasattr(user, 'password') and user.password:
        user.password = '0' * len(user.password)
    if dk != pw_in_cb:
        return False, _deal_pw_failed(user, ip, valid_time)
    locked = UserFailedLogin.check_lock_status(user.user_name, valid_time)
    if locked:
        return False, 1
    UserFailedLogin.clean_failed_record(user.user_name)
    return True, 0


def _modify_pw(new_password, user, context, event, action, check_history=True):
    status, code = _check_password_legal(new_password, user.user_name)
    if not status:
        OperationLogger.record_operation(
            context, event, OpLogResult.FAILED,
            f"Failed to {action} password for {user.user_name},due to: {getI18n(code)}"
        )
        return status, code

    password = user_service.encrypt_password(new_password)
    is_first_login = 1 if context.user_id != user.user_id else 0
    if check_history:
        history = UserPasswordHistory.is_password_in_history(user.user_id, new_password)
        if history:
            OperationLogger.record_operation(
                context, event, OpLogResult.FAILED,
                f"Password cannot be the same as previous passwords for {user.user_name}"
            )
            return False, ResponseCode.USER_HISTORY_PW
    status = UserManager.update(user.user_id, password=password, time_pw_reset=int(time.time()),
                                is_first_login=is_first_login)
    if not status:
        OperationLogger.record_operation(
            context, event, OpLogResult.FAILED,
            f"Database error while {action}ing password for {user.user_name}"
        )
        return False, ResponseCode.USER_MODIFY_FAILED
    if check_history:
        UserPasswordHistory.save_password_history(user.user_id, new_password)
    OperationLogger.record_operation(
        context, event, OpLogResult.SUCCESS,
        f"Successfully {action}ed password for {user.user_name}"
    )
    return True, ResponseCode.OK


def modify(params, request):
    context = OperationContext(
        user_id=getattr(request, 'user_id', ''),
        remote_ip=getattr(request, 'remote_addr', '')
    )
    user_name = params.get('user_name', '')
    user = UserManager.query(nopw=False, user_name=user_name, provider_id=-1)
    status, error_code = _check_modify_privileged(context.user_id, user)
    if not status:
        OperationLogger.record_operation(
            context, OpLogEvent.MOD_PWD, OpLogResult.FAILED,
            f"Cannot modify password for {user_name} due to no privilege"
        )
        return False, error_code

    old_password = params.get('old_password')
    new_password = params.get('new_password')
    if old_password == new_password:
        OperationLogger.record_operation(
            context, OpLogEvent.MOD_PWD, OpLogResult.FAILED,
            f"New password cannot be the same as old password for {user_name}"
        )
        return False, ResponseCode.USER_PASSWORD_NOCHANGE
    valid, locked = validate_pw(old_password, user, context.remote_ip)
    if not valid:
        OperationLogger.record_auth_failure(context, OpLogEvent.MOD_PWD, user_name, locked)
        return False, ResponseCode.USER_AUTH_FAILED
    status, code = _modify_pw(new_password, user, context, OpLogEvent.MOD_PWD, 'modify')
    if status:
        _clean_user_lock_status(user, context, 'Modify')
    return status, code


def _clean_user_lock_status(user, context, action):
    UserFailedLogin.clean_failed_record(user.user_name)
    UserLoginFailedTime.clean_failed_record(user.user_id)
    UserSessionCache.delete_user_session(user.user_id)
    if user.status == UserStatus.LOCKED:
        UserManager.update(user.user_id, status=UserStatus.NORMAL)
        operation_log.record_operation_log(context.user_id, context.remote_ip, OpLogModule.USER,
                                           f'{action} Password', OpLogResult.SUCCESS,
                                           f'User {user.user_name} is unlocked by {action.lower()} password.')


def reset_pw(params, request):
    context = OperationContext(
        user_id=getattr(request, 'user_id', ''),
        remote_ip=getattr(request, 'remote_addr', '')
    )
    user_name = params.get('user_name', '')
    admin_password = params.get('admin_password')
    new_password = params.get('new_password')
    admin = UserManager.query_by_id(context.user_id, nopw=False)
    if admin is None:
        return False, ResponseCode.NON_PRIVILEGED
    if admin.role != Role.ADMIN:
        OperationLogger.record_operation(
            context, OpLogEvent.RST_PWD, OpLogResult.FAILED,
            f"Insufficient privileges to reset password for {user_name}"
        )
        return False, ResponseCode.NON_PRIVILEGED
    user = UserManager.query(nopw=False, user_name=user_name, provider_id=-1)
    if user is None:
        OperationLogger.record_operation(
            context, OpLogEvent.RST_PWD, OpLogResult.FAILED,
            f"User {user_name} does not exist"
        )
        return False, ResponseCode.USER_NOT_EXIST
    valid, locked = validate_pw(admin_password, admin, context.remote_ip)
    if not valid:
        OperationLogger.record_auth_failure(context, OpLogEvent.RST_PWD, user_name, locked)
        return False, ResponseCode.USER_AUTH_FAILED
    status, code = _modify_pw(new_password, user, context, OpLogEvent.RST_PWD, 'reset',
                              check_history=False)
    if status:
        _clean_user_lock_status(user, context, 'Reset')
    return status, code


def _delete_user_related(user):
    # 删除用户关联信息
    UserFailedLogin.clean_failed_record(user.user_name)
    UserLoginFailedTime.clean_failed_record(user.user_id)
    UserSessionCache.delete_user_session(user.user_id)

    # # 删除用户关联任务
    # if go_delete_task:
    #     task_thread = threading.Thread(target=delete_user_tasks_in_thread, args=(user.user_id,))
    #     task_thread.start()  # 启动子线程
    for list_func in remove_for_user:
        try:
            list_func(user.user_id)
        except (TimeoutError, TypeError, IOError, AttributeError, ValueError, RuntimeError) as e:
            LOGGER.error(f"delete_user_related of {user.user_id} error: {e}")


def delete_user(user_id, data, request):
    context = OperationContext(
        user_id=getattr(request, 'user_id', ''),
        remote_ip=getattr(request, 'remote_addr', '')
    )
    password = data.get('admin_password')
    if context.user_id is None:
        return False, ResponseCode.NON_PRIVILEGED

    op_usr = UserManager.query_by_id(context.user_id, nopw=False)
    if op_usr is None:
        return False, ResponseCode.NON_PRIVILEGED
    if op_usr.role != Role.ADMIN:
        OperationLogger.record_operation(context, OpLogEvent.DEL_USER, OpLogResult.FAILED,
                                         f"Insufficient privileges to delete user")
        return False, ResponseCode.NON_PRIVILEGED
    user = UserManager.query_by_id(user_id)
    if user is None:
        OperationLogger.record_operation(context, OpLogEvent.DEL_USER, OpLogResult.FAILED,
                                         f"Failed to delete user due to user not exist.")
        return False, ResponseCode.USER_NOT_EXIST

    valid, locked = validate_pw(password, op_usr, context.remote_ip)
    if not valid:
        OperationLogger.record_auth_failure(context, OpLogEvent.DEL_USER, user.user_name, locked)
        return False, ResponseCode.USER_AUTH_FAILED
    if user.user_name == 'Admin':
        OperationLogger.record_operation(context, OpLogEvent.DEL_USER, OpLogResult.FAILED,
                                         getI18n(ResponseCode.CANNOT_DEL_ADMIN))
        return False, ResponseCode.CANNOT_DEL_ADMIN
    # 删除用户关联信息
    _delete_user_related(user)

    status = UserManager.delete_user(user_id)

    if status:
        OperationLogger.record_operation(context, OpLogEvent.DEL_USER, OpLogResult.SUCCESS,
                                         f"Delete {user.user_name}")

        return True, ResponseCode.OK
    OperationLogger.record_operation(context, OpLogEvent.DEL_USER, OpLogResult.FAILED,
                                     f'Failed to delete {user.username} due to database error')

    return False, ResponseCode.DB_EXCEPTION


def list_user(op_usr_id=None):
    if op_usr_id is None:
        return False, ResponseCode.NON_PRIVILEGED, []

    op_usr = UserManager.query_by_id(op_usr_id)
    if op_usr is None or op_usr.role != Role.ADMIN:
        return False, ResponseCode.NON_PRIVILEGED, []

    users = UserManager.list_all_local()
    return True, ResponseCode.OK, users


def _check_username_legal(username):
    old = UserManager.query(user_name=username, provider_id=-1)
    if old is not None:
        return False, ResponseCode.USER_NAME_DUPLICATE
    if len(username) > MAX_USERNAME_LENGTH:
        return False, ResponseCode.USER_NAME_LENGTH_OVER
    username = username.replace('#', '%23').replace('&', '%26').replace('<', '%3C').replace('>',
                                                                                            '%3E')
    regex = '^[a-zA-Z][a-zA-Z0-9_-]{4,31}$'
    # Started by AICoder, pid:wb814hf56fue0cb14460088740dc8709ada29a8f
    if not re.match(regex, username):
        return False, ResponseCode.USER_NAME_ILLEGAL
    return True, ResponseCode.OK
    # Ended by AICoder, pid:wb814hf56fue0cb14460088740dc8709ada29a8f


def _check_type_class(password):
    checks = [
        r'\d',  # 数字
        r'[a-z]',  # 小写字母
        r'[A-Z]',  # 大写字母
        r'[~!@#$%^&*()_\-=+\\|[{}\];:\'",<.>/?]'  # 特殊字符
    ]

    count = sum(1 for pattern in checks if re.search(pattern, password))
    if count < 3:
        return False
    return True


def _has_username_in_pw(password, username):
    password_lower = password.lower()
    username_lower = username.lower()

    patterns = [username_lower]
    if password_lower == username_lower * 2:
        return False, ResponseCode.USER_PASSWORD_USERNAME_2
    if password_lower == username_lower[::-1]:
        return False, ResponseCode.USER_PASSWORD_USERNAME_REVERSE
    if any(pattern in password_lower for pattern in patterns):
        return False, ResponseCode.USER_PASSWORD_HASUSERNAME
    return True, None


def _check_pwd_rule(password, username):
    if not isinstance(password, str):
        return False, ResponseCode.USER_PASSWORD_ILLEGAL
    regex = ('^(?![A-Z]+$)(?![a-z]+$)(?![0-9]+$)(?![`~!@#$%^&*()\\-_=+\\\\|[{}];:\'\\",<.>/?]+$)'
             '[A-Za-z0-9`~!@#$%^&*()\\-_=+\\\\|[{}\\];:\'\\",<.>/?]{8,64}$')
    if not re.match(regex, password):
        return False, ResponseCode.USER_PASSWORD_ILLEGAL

    if not _check_type_class(password):
        return False, ResponseCode.USER_PASSWORD_ILLEGAL
    code, msg = _has_username_in_pw(password, username)
    if not code:
        return False, msg
    # 校验是否含有超过2个连续的相同字符
    if re.search(r'(.)\1\1', password):
        return False, ResponseCode.CONSECUTIVE_CHAR_ERROR_CODE
    return True, None


def _check_password_legal(password, username):
    status, msg = _check_pwd_rule(password, username)
    if not status:
        return False, msg
    if WeakPwd.is_weak_passsword(password):
        return False, ResponseCode.USER_PASSWORD_WEAK
    return True, ResponseCode.OK
