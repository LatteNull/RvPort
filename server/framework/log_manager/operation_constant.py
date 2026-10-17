from enum import Enum


# pylint: disable=too-few-public-methods
class OpLogResult:
    SUCCESS = 'Successful'
    FAILED = 'Failed'
    TIMEOUT = 'Time out'


# pylint: disable=too-few-public-methods
class OpLogModule:
    SYSTEM = 'System'
    NODE = 'Node Manager'
    TASK = 'Task Manager'
    USER = 'User Manager'
    CONFIG = 'Config Manager'
    LOG = 'Log Manager'
    CODEMIG = 'Code Migration'


# pylint: disable=too-few-public-methods
class OpLogEvent:
    LOGIN = 'Login'
    CREATE_USER = 'Create User'
    DEL_USER = 'Delete User'
    MOD_PWD = 'Modify Password'
    RST_PWD = 'Reset Password'
    LOG_DMP = 'Operation Log Dump'
    LOG_DOWNLOAD = 'Download Log'
    API_KEY_TEST = 'Test API Key'
    API_KEY_STORE = 'Store API Key'
    API_KEY_DELETE = 'Delete API Key'
    API_KEY_SET_DEFAULT = 'Set Default API Key'
    API_KEY_SET_MODEL_DEFAULT = 'Set Model Default API Key'
