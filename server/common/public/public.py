import os
import platform

COMMUNICATE_TIMEOUT = 60
SUCCESS = 0
FAILED = 1
SECONDS_PER_MINUTE = 60
DEBUG_MODE = True
ERROR_CODE = 1
OK = 0
SYS_ERROR = -1
TASK_INTERVAL = 'interval'
TASK_DURATION = 'duration'
TASK_ID = 'task_id'
TASK_PARAMS = 'taskparam'

# Node status constants
NODE_STATUS_OFFLINE = 'offline'
NODE_STATUS_AUTH_FAILED = 'authentication failed'
NODE_STATUS_INSTALLING = 'installing'
NODE_STATUS_UPGRADING = 'upgrading'
NODE_STATUS_INSTALL_FAILED = 'installing failed'
NODE_STATUS_NORMAL = 'normal'
NODE_STATUS_UNMATCH = 'unmatch'

ROOT_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SERVER_ROOT = os.path.realpath(os.path.join(ROOT_PATH, "server"))
CODEMIG_DATA_PATH = os.path.realpath(os.path.join(ROOT_PATH, "data", "codemig"))
AGENT_DATA_PATH = os.path.realpath(os.path.join(ROOT_PATH, "data", "agent"))
# 分片上传临时目录：统一放在 server/temp_file 下
AGENT_TEMP_PATH = os.path.realpath(os.path.join(SERVER_ROOT, "temp_file"))


def get_root_path():
    """     获取根目录的路径   """
    # Started by AICoder, pid:343ccs4830vcfac1428f08c8302873090871becb
    return ROOT_PATH


def get_codemig_data_path():
    return CODEMIG_DATA_PATH


def get_agent_data_path():
    return AGENT_DATA_PATH


def get_agent_temp_path():
    return AGENT_TEMP_PATH


DB_DIR = os.path.realpath(os.path.join(get_root_path(), 'data'))
PLUGIN_PACKAGE_STORAGE_PATH = 'plugin_packages'
DATABASE = os.path.join(DB_DIR, 'codemig.db')
TASK_INFO_FILE = 'taskinfo.json'

def get_free_space():
    disk_stat = os.statvfs(ROOT_PATH)
    free = float(disk_stat.f_bavail * disk_stat.f_frsize)
    return free


def get_platform():
    return platform.machine()


if __name__ == "__main__":
    root = get_root_path()

    print(root)
