import sys

import os

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.response.response_code import ResponseCode
from framework.user_manager.user_db import Role, UserManager
from framework.config_manager.config import SysConfig, ConfigKeys


# 普通用户可以查看/修改的配置项（网络代理相关）
ALLOWED_NORMAL_USER_KEYS = {
    ConfigKeys.DOCKER_HTTP_PROXY,
    ConfigKeys.DOCKER_HTTPS_PROXY,
    ConfigKeys.DOCKER_NO_PROXY,
}


def check_usr_admin_role(op_usr_id=None):
    if op_usr_id is None:
        return False, ResponseCode.NON_PRIVILEGED

    op_usr = UserManager.query_by_id(op_usr_id)
    if op_usr is None or op_usr.role != Role.ADMIN:
        return False, ResponseCode.NON_PRIVILEGED
    return True, None


def list_user_config(op_usr_id=None, ip=None):
    status, msg = check_usr_admin_role(op_usr_id)
    success, code, config_set = SysConfig.list_all()
    if not success:
        return success, code, []

    # 普通用户只能看到网络代理相关配置
    if status is False:
        config_set = {k: v for k, v in config_set.items() if k in ALLOWED_NORMAL_USER_KEYS}

    return True, None, config_set


def check_and_update(key, value, op_usr_id=None):
    status, msg = check_usr_admin_role(op_usr_id)
    if status is False:
        # 普通用户只能修改网络代理相关配置
        if key not in ALLOWED_NORMAL_USER_KEYS:
            return False, ResponseCode.NON_PRIVILEGED
    return SysConfig.update(key, value)
