import logging
import logging.config
import logging.handlers
import json
import os
import stat
import zipfile
from logging.handlers import RotatingFileHandler, WatchedFileHandler

from .public import get_root_path

# Started by AICoder, pid:fb2d2ubcd4707541467108f840e433019186e5c7


BASE_LOG_DIR = os.path.join(get_root_path(), 'logs')
# Ended by AICoder, pid:fb2d2ubcd4707541467108f840e433019186e5c7

LOG_FORMAT = ('%(asctime)s|%(process)d:%(thread)d|%(filename)s:%(lineno)d|%(funcName)s|'
              '%(levelname)s|%(message)s')
DATE_FORMAT = '%Y-%m-%d  %H:%M:%S %a'


def _load_log_level_from_config():
    """从 server/config.json 读取 LOG_LEVEL，缺失或非法值回落 WARNING。"""
    config_path = os.path.join(get_root_path(), 'server', 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            level_name = json.load(config_file).get('LOG_LEVEL', 'WARNING')
        return getattr(logging, str(level_name).upper(), logging.WARNING)
    except (OSError, ValueError):
        return logging.WARNING


LOG_LEVEL = _load_log_level_from_config()
MAX_BYTES = 10485760  # 10 MB
BACKUP_COUNT = 2
logger_name_to_logger_dict = {}


class LogHandler(RotatingFileHandler, WatchedFileHandler):
    def __init__(self, *args, comp_method='ZIP', **kwargs):
        super().__init__(*args, **kwargs)
        self.namer, self.rotator = self._get_namer_and_rotator(comp_method)
        self.dev, self.ino = (-1, -1)
        self._statstream()

    @staticmethod
    def namer_zip(default_name):
        return default_name + '.zip'

    @staticmethod
    def rotator_zip(src, dst):
        """
        压缩日志文件。
        :param src: 源文件路径
        :param dst: 目标文件路径
        """
        with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as file:
            _, file_name = os.path.split(src)
            file.write(src, arcname=file_name)

        if os.path.isfile(src) and os.path.isfile(dst):
            os.remove(src)
        os.chmod(dst, stat.S_IREAD + stat.S_IWRITE)

    def emit(self, record):
        self.reopenIfNeeded()
        RotatingFileHandler.emit(self, record)

    def doRollover(self):
        RotatingFileHandler.doRollover(self)
        os.chmod(self.baseFilename, stat.S_IREAD + stat.S_IWRITE)

    def _get_namer_and_rotator(self, comp_method):
        namer_str = f'namer_{comp_method.lower()}'
        rotator_str = f'rotator_{comp_method.lower()}'

        try:
            namer = getattr(self, namer_str)
            rotator = getattr(self, rotator_str)
        except (AttributeError, NameError, TypeError):
            namer = self.namer_zip
            rotator = self.rotator_zip
        return namer, rotator

# pylint: disable=too-few-public-methods
class AntiCRLFLogRecord(logging.LogRecord):
    """
        记录日志时，转义CRLF
    """
    password_name_tuple = ('password', 'check_password')

    def getMessage(self):
        """
        重写getMessage方法，以转义CRLF字符。
        """
        message = str(self.msg)
        for password_name in self.password_name_tuple:
            if password_name in message:
                return ''
        if self.args:
            message = message % self.args
        message = message.replace('\n', '\\n').replace('\r', '\\r')
        return message


def init_log(function_name='common', file_name='', log_flag=''):
    """
    初始化日志记录器。
    :param file_name: 日志文件名
    :param function_name: 功能名称
    :param log_flag: 日志标识
    :return: 配置好的日志记录器
    """
    if file_name == '':
        file_name = function_name + '.log'
    # Started by AICoder, pid:tb2d27bcd4d07541467108f840e433019182e5c7
    if not all(isinstance(arg, str) for arg in (file_name, function_name, log_flag)):
        return None
    # Ended by AICoder, pid:tb2d27bcd4d07541467108f840e433019182e5c7
    logger_name = file_name.split('.')[0]
    if log_flag:
        logger_name = f'{logger_name}-{log_flag}'
    if logger_name in logger_name_to_logger_dict:
        return logger_name_to_logger_dict[logger_name]
    logging.setLogRecordFactory(AntiCRLFLogRecord)

    base_log_dir = os.path.join(BASE_LOG_DIR, function_name)
    # Started by AICoder, pid:0b2d2bbcd4h07541467108f840e433019182e5c7
    # mode=0o700：新建目录属主独占 rwx（目录必须保留 x 位，否则 LogHandler
    # 创建/打开日志文件直接 PermissionError），组/其他用户零权限，比 0750 更紧；
    # 已存在目录不重复收紧，敏感性由日志文件本身 0600（下方及 doRollover）承接。
    os.makedirs(base_log_dir, mode=0o700, exist_ok=True)
    # Ended by AICoder, pid:0b2d2bbcd4h07541467108f840e433019182e5c7

    log_dir = os.path.join(base_log_dir, file_name)
    handler = LogHandler(log_dir, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    handler.setFormatter(formatter)

    # Started by AICoder, pid:v3e0cxf0cayc9e214cfe0a547078200d5773ab50
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    # Ended by AICoder, pid:v3e0cxf0cayc9e214cfe0a547078200d5773ab50

    logger = logging.getLogger(logger_name)
    logger.setLevel(LOG_LEVEL)
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)  # 添加控制台处理器到日志记录器
    os.chmod(log_dir, stat.S_IREAD + stat.S_IWRITE)
    logger_name_to_logger_dict[logger_name] = logger
    return logger


def init_collect_log(function_name='', file_name='', log_flag=''):
    if file_name == '':
        file_name = function_name + '.log'
    function_name = os.path.join('collect', function_name)
    return init_log(function_name, file_name, log_flag)


def init_analysis_log(function_name='', file_name='', log_flag=''):
    if file_name == '':
        file_name = function_name + '.log'
    function_name = os.path.join('analysis', function_name)
    return init_log(function_name, file_name, log_flag)


def reset_level(log_level):
    for _, v in logger_name_to_logger_dict.items():
        v.setLevel(log_level)
