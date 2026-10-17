import copy
import json
import os
import re
import sys

from .public import ROOT_PATH
from .logger import init_log
from common import crypto

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

key_path = os.path.join(ROOT_PATH, "data", "himalayan")
nonce_path = os.path.join(ROOT_PATH, "data", "qomolangma")
TASK_STATUS_JSON = {'error_info_list': [], 'success_info': ''}
LOGGER = init_log('common')


def validate_ip(ip):
    '\n    校验ip\n    '
    if not isinstance(ip, str):
        return False
    pattern = re.compile(
        '((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})(\\.((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})){3}')
    if pattern.match(ip):
        return True
    return False


def write_json(data, target_file, log=None):
    """
    write data to txt
    :param data:dict
    :param target_file:str
    :param log
    """

    try:
        with open(target_file, 'w') as fo:
            json.dump(data, fo)
        return True
    except (json.JSONDecodeError, OSError, PermissionError, IOError, FileNotFoundError) as err:
        if log:
            log.error(err, exc_info=True)
        return False


def encrypt_passphrase(pw):
    """AES-256-GCM 加密，返回 ciphertext || tag(16B)；空值返回 None，失败抛异常。"""
    if pw is None or pw == '':
        return None
    key = crypto.read_key_file(key_path)
    nonce = crypto.read_nonce_file(nonce_path)
    return crypto.aes_gcm_encrypt(key, nonce, pw)


def decrypt_passphrase(cipher):
    """解密 encrypt_passphrase 的输出（ciphertext || tag）；空值返回 ''，失败返回 None。"""
    if not cipher:
        return ''
    try:
        key = crypto.read_key_file(key_path)
        nonce = crypto.read_nonce_file(nonce_path)
        plaintext = crypto.aes_gcm_decrypt(key, nonce, cipher)
    except (OSError, ValueError):
        LOGGER.error("decryption failed: key/nonce file error", exc_info=True)
        return None
    except Exception:
        LOGGER.error("decryption failed")
        return None
    return plaintext.decode()


def decrypt_passphrase(cipher):
    """解密 encrypt_passphrase 的输出（ciphertext || tag）；空值返回 ''，失败返回 None。"""
    if not cipher:
        return ''
    try:
        key = crypto.read_key_file(key_path)
        nonce = crypto.read_nonce_file(nonce_path)
        plaintext = crypto.aes_gcm_decrypt(key, nonce, cipher)
    except (OSError, ValueError):
        LOGGER.error("decryption failed: key/nonce file error", exc_info=True)
        return None
    except Exception:
        LOGGER.error("decryption failed")
        return None
    return plaintext.decode()


def set_error_info_list(error_info_list, error_code, cmd=''):
    """
    异常提示信息更新
    """
    if not error_info_list:
        error_info_list.append({
            error_code: [[str(cmd)]] if cmd else []})
        return None
    for _index, error_info in enumerate(error_info_list):
        LOGGER.debug('error_code: %s; cmd: %s; index: %s; error_info: %s', error_code, cmd, _index, error_info)
        if error_code in error_info:
            if cmd and [str(cmd)] not in error_info[error_code]:
                error_info[error_code].append([str(cmd)])

        else:
            if cmd:
                error_info_list.append({error_code: [[str(cmd)]]})

            else:
                error_info_list.append({error_code: []})


def get_task_status_from_file(data_path):
    """
    从task_status.json文件获取异常提示信息
    """
    task_status = copy.deepcopy(TASK_STATUS_JSON)
    task_status_file = os.path.realpath(os.path.join(data_path, 'task_status.json'))
    if os.path.isfile(task_status_file):

        try:
            with open(task_status_file, 'r', encoding='utf-8') as file:
                task_status = json.load(file)
        except Exception as error:
            LOGGER.error(error, exc_info=True)

    return task_status


def get_task_status(task_status=None, code='SysPerf.Success.TimeOut', args_list=None):
    if task_status is None:
        task_status = copy.deepcopy(TASK_STATUS_JSON)
    if code in ('SysPerf.Success.ReachFileSize', 'SysPerf.Success.TimeOut', 'SysPerf.Success.AppFinish'):
        task_status['success_info'] = code
    else:
        code_list = args_list if args_list else []
        err_info = {code: code_list}
        task_status['error_info_list'].append(err_info)
    return task_status


def get_module_task_status(module, task_status, error_code, args_list=None):
    module_status = get_task_status(task_status, error_code, args_list)
    module_task_status = {
        module: module_status}
    return module_task_status


def write_task_status(task_status, data_path, error_code='', args_list=None, module=None):
    task_file = os.path.realpath(os.path.join(data_path, 'task_status.json'))
    if module and error_code:
        task_status = get_module_task_status(module, task_status, error_code, args_list)
    elif error_code:
        get_task_status(task_status, error_code, args_list)
    elif not task_status.get('error_info_list'):
        get_task_status(task_status)
    write_json(task_status, task_file)
