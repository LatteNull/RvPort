import os
import sys
import subprocess
import re
from urllib.parse import urlparse
from flask import jsonify
import requests

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.public.common import encrypt_passphrase
from common.public.public import ROOT_PATH
from common.ai_key.ai_key_utils import DEFAULT_AI_HTTP_UA
from plugin.codemig.ai_assistant.models import UserApiKey
from framework.config_manager.config import ConfigKeys, SysConfig
from framework.log_manager import operation_log
from framework.log_manager.operation_constant import OpLogResult, OpLogModule, OpLogEvent
from common.db.SQLOperation import DatabaseException
key_path = os.path.join(ROOT_PATH, "data", "himalayan")
nonce_path = os.path.join(ROOT_PATH, "data", "qomolangma")
LOGGER = logger.init_log('api_keyManager')

_WS_OR_CTRL_RE = re.compile(r"[\s\x00-\x1F\x7F]")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._\/-]+$")

# 需要脱敏的环境变量名（docker run -e KEY=VALUE 显式传值场景）
_SENSITIVE_ENV_KEYS = ("OPENAI_API_KEY", "CURSOR_API_KEY", "PI_BASE_API_KEY")


def _mask_env_value(value: str) -> str:
    """敏感值脱敏：保留前 3 个字符，其余替换为 ******（与 _key_prefix=api_key[:3] 规范一致）。"""
    return (value[:3] + "******") if len(value) > 3 else "******"


def sanitize_cmd_for_log(cmd_list) -> list:
    """docker 命令日志脱敏：把 -e KEY=VALUE 中的敏感 KEY 的 VALUE 替换为前3字符+******。

    仅处理敏感环境变量名（_SENSITIVE_ENV_KEYS），其余参数（挂载、镜像、
    shell_cmd、proxy 等）原样保留，保证日志可读性。
    """
    sanitized, i = [], 0
    while i < len(cmd_list):
        item = str(cmd_list[i])
        if item == "-e" and i + 1 < len(cmd_list):
            env = str(cmd_list[i + 1])
            key, sep, value = env.partition("=")
            if sep and key in _SENSITIVE_ENV_KEYS and value:
                sanitized.append(item)
                sanitized.append(f"{key}={_mask_env_value(value)}")
            else:
                sanitized.append(item)
                sanitized.append(cmd_list[i + 1])
            i += 2
            continue
        sanitized.append(cmd_list[i])
        i += 1
    return sanitized


def sanitize_cmd_text(cmd: str) -> str:
    """docker 命令字符串脱敏（入库版）：与 sanitize_cmd_for_log 同规则，处理 join 后的整条命令字符串。

    用于 codemig_task_ai.cmd 等落库字段，避免完整 API key 写入数据库。
    """
    if not cmd:
        return cmd
    out = cmd
    for key in _SENSITIVE_ENV_KEYS:
        # 匹配 "KEY=VALUE"，VALUE 取到空白为止（shell 词边界），保留前3字符脱敏
        out = re.sub(
            rf"{key}=(\S+)",
            lambda m, k=key: f"{k}={_mask_env_value(m.group(1))}",
            out,
        )
    return out


def _has_whitespace_or_control_chars(value: str) -> bool:
    return bool(_WS_OR_CTRL_RE.search(value))


def _is_valid_http_url(value: str) -> bool:
    """
    与前端 validateHttpUrl 一致：
    - 禁止空白/控制字符
    - 必须可解析为 URL，且协议为 http/https
    """
    if _has_whitespace_or_control_chars(value):
        return False
    try:
        u = urlparse(value)
    except (TypeError, ValueError):
        return False
    if u.scheme not in ("http", "https"):
        return False
    # urlparse 对 "http://a" 的 netloc="a"，对 "http:/a" 等异常会不完整
    if not u.netloc:
        return False
    return True


def _validate_api_config_params(api_key: str, base_url: str, model: str):
    """
    返回 (ok: bool, msg: str)
    约束与前端一致，确保前后端“效果一致”。
    """
    if not str(api_key):
        return False, "API Key不能为空"
    if not str(base_url):
        return False, "Base URL不能为空"
    if not str(model):
        return False, "模型名称不能为空"

    if _has_whitespace_or_control_chars(str(api_key)):
        return False, "API Key包含非法字符（禁止空格/换行/控制字符）"
    if _has_whitespace_or_control_chars(str(base_url)):
        # 前端 validateInfos 对应 invalidBaseUrl；这里复用同语义提示
        return False, "Base URL格式不正确（必须是 http/https 且禁止空白/控制字符）"
    if not _is_valid_http_url(str(base_url)):
        return False, "Base URL格式不正确（必须是 http/https 且禁止空白/控制字符）"

    if _has_whitespace_or_control_chars(str(model)) or not _MODEL_RE.match(str(model)):
        return False, "模型名称包含非法字符"

    return True, ""


def _record_op_log(user_id, login_ip, event, result, detail):
    """与 login_manager 一致：写入操作日志表（失败不影响主流程）。"""
    try:
        operation_log.record_operation_log(
            user_id,
            login_ip or '',
            OpLogModule.CODEMIG,
            event,
            result,
            detail,
        )
    except (DatabaseException, OSError, IOError, RuntimeError, ValueError, TypeError) as e:
        LOGGER.warning('record_operation_log failed: %s', e, exc_info=True)


def _safe_model_fmt(model):
    m = (model or '').strip()
    return m if m else '(empty)'


def _perform_api_key_validity_check(params):
    """
    实际执行 API Key 有效性校验（发起一次最小化请求），不写操作日志。

    供 do_test_api_key（“测试”入口）与 do_store_api_key_to_db（存储前校验）复用，
    保证两者判定口径完全一致。返回 {code, msg, data}，code == 0 表示有效。
    """
    api_key = params.get("api_key", "")
    base_url = params.get("base_url", "")
    model = params.get("model", "")
    api_format = params.get("api_format", "")

    # 读取代理配置（与原测试逻辑保持一致）
    status, https_proxy, _ = SysConfig.query_system_configuration(ConfigKeys.DOCKER_HTTPS_PROXY)
    if not status:
        https_proxy = ''
    status, http_proxy, _ = SysConfig.query_system_configuration(ConfigKeys.DOCKER_HTTP_PROXY)
    if not status:
        http_proxy = ''
    status, no_proxy, _ = SysConfig.query_system_configuration(ConfigKeys.DOCKER_NO_PROXY)
    if not status:
        no_proxy = ''

    os.environ.update({
        'https_proxy': https_proxy,
        'http_proxy': http_proxy,
        'no_proxy': no_proxy,
        'CURSOR_API_KEY': api_key,
    })

    # 参数校验
    if not api_key:
        return {
            "code": -1,
            "msg": "API Key 不能为空",
            "data": ""
        }

    # Cursor 格式：使用 docker run 命令测试
    if api_format == 'cursor':
        return _test_cursor_api_key(api_key, model, http_proxy, https_proxy)
    # OpenAI 格式：使用 HTTP 请求测试
    return _test_openai_api_key(api_key, base_url, model)


def do_test_api_key(params, user_id=None, login_ip=None):
    api_format = params.get("api_format", "")
    model = params.get("model", "")

    out = _perform_api_key_validity_check(params)

    if out.get('code') == 0:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_TEST,
            OpLogResult.SUCCESS,
            f'Test API Key successfully (format={api_format}, model={_safe_model_fmt(model)}).',
        )
    else:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_TEST,
            OpLogResult.FAILED,
            f'Test API Key failed (format={api_format}, model={_safe_model_fmt(model)}): {out.get("msg", "")}',
        )
    return out


def _test_cursor_api_key(api_key, model, http_proxy, https_proxy):
    """使用 docker run 命令测试 Cursor 格式的 API Key"""
    docker_image = "codemig-agent-base:1.0.0"
    test_prompt = "Hello, are you working?"
    
    # 构建 docker run 命令
    docker_cmd = [
        "docker", "run", "--rm",
        "--network", "host",
        "-e", f"http_proxy={http_proxy}",
        "-e", f"https_proxy={https_proxy}",
        "-e", f"CURSOR_API_KEY",
        docker_image,
        "agent",
        "-p", test_prompt,
        "--model", model if model else "auto",
        "--yolo"
    ]
    try:
        LOGGER.info(f"Testing cursor API key with command: {' '.join(sanitize_cmd_for_log(docker_cmd))}")
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=120  # 60秒超时
        )
        
        LOGGER.info(f"Cursor test stdout: {result.stdout[:500] if result.stdout else 'empty'}")
        LOGGER.info(f"Cursor test stderr: {result.stderr[:500] if result.stderr else 'empty'}")
        LOGGER.info(f"Cursor test return code: {result.returncode}")
        
        # 检查返回结果
        if result.returncode == 0:
            return {
                "code": 0,
                "msg": "API Key 测试成功",
                "data": {
                    "model": model,
                    "status": "valid",
                    "output": result.stdout[:200] if result.stdout else ""
                }
            }
        else:
            # 解析错误信息
            error_msg = result.stderr if result.stderr else result.stdout
            if "401" in error_msg or "Unauthorized" in error_msg or "invalid" in error_msg.lower():
                return {
                    "code": -1,
                    "msg": "API Key 无效或已过期",
                    "data": ""
                }
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                return {
                    "code": -1,
                    "msg": "API Key 配额已用尽或请求过于频繁",
                    "data": ""
                }
            elif "403" in error_msg or "Forbidden" in error_msg:
                return {
                    "code": -1,
                    "msg": "API Key 被拒绝访问",
                    "data": ""
                }
            else:
                return {
                    "code": -1,
                    "msg": f"API 请求失败: {error_msg[:200] if error_msg else '未知错误'}",
                    "data": ""
                }
                
    except subprocess.TimeoutExpired:
        return {
            "code": -1,
            "msg": "请求超时，请检查网络或代理配置",
            "data": ""
        }
    except FileNotFoundError:
        return {
            "code": -1,
            "msg": "Docker 未安装或不可用",
            "data": ""
        }
    except PermissionError:
        return {
            "code": -1,
            "msg": "无法执行 Docker 命令（权限不足或当前用户无权访问 Docker 套接字）",
            "data": ""
        }
    except UnicodeDecodeError:
        return {
            "code": -1,
            "msg": "Docker 输出解码失败（可能包含非 UTF-8 字符），请检查运行环境/镜像输出",
            "data": ""
        }
    except subprocess.SubprocessError:
        return {
            "code": -1,
            "msg": "Docker 子进程执行失败",
            "data": ""
        }
    except OSError as e:
        errno = getattr(e, "errno", None)
        return {
            "code": -1,
            "msg": f"运行 Docker 时发生系统错误 (errno={errno}): {e}",
            "data": ""
        }


def _test_openai_api_key(api_key, base_url, model):
    """使用 HTTP 请求测试 OpenAI 格式的 API Key"""
    # 构造请求头
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # 绕过部分网关对默认 python-requests UA 的限流(1305)，详见 ai_key_utils.DEFAULT_AI_HTTP_UA
        "User-Agent": DEFAULT_AI_HTTP_UA,
    }

    # 构造最小化测试请求（避免产生高额费用）
    test_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello, are you working?"}],
        "max_tokens": 64  # 限制输出长度，降低成本
    }

    try:
        # 发送 POST 请求
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=test_payload,
            timeout=60  # 60秒超时
        )

        # 检查 HTTP 状态码
        if response.status_code == 200:
            # 成功：返回成功信息
            return {
                "code": 0,
                "msg": "API Key 测试成功",
                "data": {
                    "model": model,
                    "status": "valid"
                }
            }
        elif response.status_code == 401:
            # 401 Unauthorized：API Key 无效
            return {
                "code": -1,
                "msg": "API Key 无效或已过期",
                "data": ""
            }
        elif response.status_code == 429:
            # 429 Too Many Requests：配额用尽
            return {
                "code": -1,
                "msg": "API Key 配额已用尽或请求过于频繁",
                "data": ""
            }
        elif response.status_code == 403:
            # 403 Forbidden：可能被封禁
            return {
                "code": -1,
                "msg": "API Key 被拒绝访问（可能被封禁）",
                "data": ""
            }
        else:
            # 其他错误
            error_detail = response.json().get("error", {}).get("message", "未知错误")
            return {
                "code": -1,
                "msg": f"API 请求失败: {response.status_code} - {error_detail}",
                "data": ""
            }

    except requests.exceptions.Timeout:
        return {
            "code": -1,
            "msg": "请求超时，请检查网络或 base_url 是否正确",
            "data": ""
        }
    except requests.exceptions.ConnectionError:
        return {
            "code": -1,
            "msg": "无法连接到 API 服务器，请检查 base_url 和网络",
            "data": ""
        }

def do_del_api_key_from_db(user_id, user_name, api_key_id, login_ip=None, is_admin=False):
    """
    根据 user_name 和 api_key_id 删除 API Key 记录
    注意：同时校验 user_name 是为了防止越权删除（安全最佳实践）
    - admin 可以删除任意 key
    - 普通用户只能删除自己的 key，不能删除 admin 的 key
    """

    # 参数校验
    if not user_name or not str(api_key_id).strip():
        LOGGER.error("删除API Key失败：参数 user_name 或 api_key_id 为空")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.FAILED,
            'Delete API Key failed: invalid parameters.',
        )
        return {
            "code": -3,
            "msg": "参数错误：user_name 和 api_key_id 不能为空",
            "data": ""
        }

    # 确保 api_key_id 是整数（防止 SQL 注入或类型错误）
    try:
        api_key_id = int(api_key_id)
        if api_key_id <= 0:
            raise ValueError("api_key_id 必须是正整数")
    except (ValueError, TypeError) as e:
        LOGGER.error(f"删除API Key失败：api_key_id 格式无效 - {e}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.FAILED,
            f'Delete API Key failed: invalid api_key_id ({e}).',
        )
        return {
            "code": -3,
            "msg": "参数错误：api_key_id 必须是正整数",
            "data": ""
        }

    result = UserApiKey.del_api_key(user_id, api_key_id, is_admin=is_admin)
    
    if result == 0:
        LOGGER.info(f"API Key删除成功：user_name={user_name}, api_key_id={api_key_id}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.SUCCESS,
            f'Delete API Key successfully (api_key_id={api_key_id}).',
        )
        return {
            "code": 0,
            "msg": "API Key删除成功",
            "data": {"deleted_id": api_key_id}
        }
    elif result == -2:
        LOGGER.warning(f"未找到匹配的API Key记录：user_name={user_name}, api_key_id={api_key_id}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.FAILED,
            f'Delete API Key failed: record not found (api_key_id={api_key_id}).',
        )
        return {
            "code": -2,
            "msg": "未找到指定的API Key记录（可能已被删除或无权限）",
            "data": ""
        }
    elif result == -3:
        LOGGER.warning(f"API Key删除失败：user_name={user_name}, api_key_id={api_key_id} 无权限")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.FAILED,
            f'Delete API Key failed: no permission (api_key_id={api_key_id}).',
        )
        return {
            "code": -3,
            "msg": "无权限：不能删除管理员的API Key",
            "data": ""
        }
    else:  # result == -1
        LOGGER.error(f"数据库删除操作失败：user_name={user_name}, api_key_id={api_key_id}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_DELETE,
            OpLogResult.FAILED,
            f'Delete API Key failed: database error (api_key_id={api_key_id}).',
        )
        return {
            "code": -1,
            "msg": "API Key删除失败",
            "data": ""
        }

def do_store_api_key_to_db(user_id, params, login_ip=None):
    # 读取所有需要的参数，兜底空值
    user_name = params.get("user_name", "")
    api_key = params.get("api_key", "")
    base_url = params.get("base_url", "")
    model = params.get("model", "")
    api_format = params.get("api_format", "")
    others = params.get("others", "")  # 读取others参数，兜底空值
    is_default = bool(params.get("is_default", 0))

    ok, msg = _validate_api_config_params(api_key, base_url, model)
    if not ok:
        return {
            "code": -3,
            "msg": msg,
            "data": ""
        }

    # 存储 API Key 之前，校验其有效性（实际发起一次最小化请求，与"测试"入口判定口径一致）
    validity_out = _perform_api_key_validity_check(params)
    if validity_out.get('code') != 0:
        validity_msg = validity_out.get("msg", "")
        LOGGER.warning(
            f'存储前API Key有效性校验未通过：user_name={user_name}, '
            f'format={api_format}, model={_safe_model_fmt(model)}: {validity_msg}'
        )
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_STORE,
            OpLogResult.FAILED,
            f'Store API Key failed: validity check failed (format={api_format}, model={_safe_model_fmt(model)}): {validity_msg}.',
        )
        return {
            "code": -4,
            "msg": f"API Key 有效性校验未通过：{validity_msg}",
            "data": ""
        }

    encrypted_api_key = encrypt_passphrase(api_key)

    # 使用 ORM 静态方法存储
    result, new_api_key_id = UserApiKey.store(user_id, encrypted_api_key, base_url, model, api_format, others, is_default)
    
    if result == 0:
        LOGGER.info(f"API Key插入成功，ID：{new_api_key_id}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_STORE,
            OpLogResult.SUCCESS,
            f'Store API Key successfully (api_key_id={new_api_key_id}, format={api_format}, model={_safe_model_fmt(model)}, default={is_default}).',
        )
        return {
            "code": 0,
            "msg": "api_key储存成功",
            "data": {"api_key_id": new_api_key_id}  # 返回新增ID，更实用
        }
    elif result == -2:
        LOGGER.error(f"插入失败：用户{user_name}的API Key已存在")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_STORE,
            OpLogResult.FAILED,
            f'Store API Key failed: duplicate key (format={api_format}, model={_safe_model_fmt(model)}).',
        )
        return {
            "code": -2,
            "msg": "该API Key已存在，无需重复添加",
            "data": ""
        }
    else:  # result == -1
        LOGGER.error(f"数据库操作失败：用户{user_name}")
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_STORE,
            OpLogResult.FAILED,
            'Store API Key failed: database error.',
        )
        return {
            "code": -1,
            "msg": "api_key储存失败",
            "data": ""
        }

def get_agent_config_from_db(agent_model, user_id=None, is_admin=False):
    # 使用 ORM 静态方法获取配置（按用户权限范围查找）
    result, agent_config = UserApiKey.get_agent_config(agent_model, user_id=user_id, is_admin=is_admin)
    
    if result == 0:
        return agent_config
    elif result == -2:
        LOGGER.warning(f"No API key found for model: {agent_model}")
        return None
    else:  # result == -1
        LOGGER.error(f'Error getting agent config for model: {agent_model}')
        return {
            "code": -1,
            "msg": "api_key获取失败",
            "data": ""
        }


def do_get_api_key_from_db(user_id=None, is_admin=False):
    # 使用 ORM 静态方法获取 API Key（按角色过滤）
    result, apikey_list = UserApiKey.get_all_api_keys(user_id=user_id, is_admin=is_admin)
    
    if result == 0:
        # 返回前端适配的格式：核心是包含apikey_list字段
        return jsonify({
            "code": 0,  # 成功状态码
            "msg": "查询成功",
            "apikey_list": apikey_list  # 前端解析的核心字段
        })
    else:  # result == -1
        LOGGER.error('Error getting API keys')
        return {
            "code": -1,
            "msg": "api_key获取失败",
            "data": ""
        }

def do_set_default_api_key_to_db(api_key_id, user_id=None, login_ip=None, is_admin=False):
    """
    将指定的API Key设置为当前用户的默认（按用户隔离）

    Args:
        api_key_id (int): 要设置为默认的API Key的ID
        user_id: 操作用户的ID
        is_admin: 是否为管理员
    """
    # 使用 ORM 静态方法设置默认（写入 user_default_selection 表，按用户隔离）
    result = UserApiKey.set_default_api_key(api_key_id, user_id=user_id, is_admin=is_admin)
    
    if result == 0:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_DEFAULT,
            OpLogResult.SUCCESS,
            f'Set default API Key successfully (api_key_id={api_key_id}).',
        )
        return {
            "code": 0,
            "msg": f"已成功将API Key ID {api_key_id} 设为默认",
            "data": ""
        }
    elif result == -3:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_DEFAULT,
            OpLogResult.FAILED,
            f'Set default API Key failed: no permission (api_key_id={api_key_id}).',
        )
        return {
            "code": -3,
            "msg": "无权限：只能将自己的或共享（管理员）的API Key设为默认",
            "data": ""
        }
    elif result == -4:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_DEFAULT,
            OpLogResult.FAILED,
            f'Set default API Key failed: not found (api_key_id={api_key_id}).',
        )
        return {
            "code": -4,
            "msg": f"设置默认失败，未找到API Key ID {api_key_id}",
            "data": ""
        }
    else:  # result == -1
        LOGGER.error(f'Error setting default API key: api_key_id={api_key_id}')
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_DEFAULT,
            OpLogResult.FAILED,
            f'Set default API Key failed: database error (api_key_id={api_key_id}).',
        )
        return {
            "code": -1,
            "msg": "数据库操作错误",
            "data": ""
        } 


def set_default_api_key_to_db(params, user_id=None, login_ip=None, is_admin=False):
    api_key_id = params.get("api_key_id")
    return do_set_default_api_key_to_db(api_key_id, user_id=user_id, login_ip=login_ip, is_admin=is_admin)


def do_set_model_default_api_key_to_db(api_key_id, user_id=None, login_ip=None, is_admin=False):
    """
    将指定的API Key设置为该用户在该model下的选中项（is_model_default）。
    与全局 is_default 不同：每个用户对每个model最多一条为 is_model_default=True。
    """
    result = UserApiKey.set_model_default_api_key(api_key_id, user_id=user_id, is_admin=is_admin)

    if result == 0:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_MODEL_DEFAULT,
            OpLogResult.SUCCESS,
            f'Set model default API Key successfully (api_key_id={api_key_id}).',
        )
        return {
            "code": 0,
            "msg": f"已成功将API Key ID {api_key_id} 设为该模型选中项",
            "data": ""
        }
    elif result == -4:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_MODEL_DEFAULT,
            OpLogResult.FAILED,
            f'Set model default API Key failed: not found (api_key_id={api_key_id}).',
        )
        return {
            "code": -4,
            "msg": f"设置失败，未找到API Key ID {api_key_id}",
            "data": ""
        }
    elif result == -3:
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_MODEL_DEFAULT,
            OpLogResult.FAILED,
            f'Set model default API Key failed: no permission (api_key_id={api_key_id}).',
        )
        return {
            "code": -3,
            "msg": "无权限：只能选择自己的或共享（管理员）的API Key",
            "data": ""
        }
    else:  # result == -1
        LOGGER.error(f'Error setting model default API key: api_key_id={api_key_id}')
        _record_op_log(
            user_id,
            login_ip,
            OpLogEvent.API_KEY_SET_MODEL_DEFAULT,
            OpLogResult.FAILED,
            f'Set model default API Key failed: database error (api_key_id={api_key_id}).',
        )
        return {
            "code": -1,
            "msg": "数据库操作错误",
            "data": ""
        }


def set_model_default_api_key_to_db(params, user_id=None, login_ip=None, is_admin=False):
    api_key_id = params.get("api_key_id")
    return do_set_model_default_api_key_to_db(api_key_id, user_id=user_id, login_ip=login_ip, is_admin=is_admin)

def store_api_key_to_db(user_id, params, login_ip=None):
    return do_store_api_key_to_db(user_id, params, login_ip=login_ip)

def get_api_key_from_db(user_id=None, is_admin=False):
    return do_get_api_key_from_db(user_id=user_id, is_admin=is_admin)

def del_api_key_from_db(user_id, params, login_ip=None, is_admin=False):
    user_name = params.get("user_name")
    api_key_id = params.get("api_key_id")
    return do_del_api_key_from_db(user_id, user_name, api_key_id, login_ip=login_ip, is_admin=is_admin)

def test_api_key_by_post(params, user_id=None, login_ip=None):
    return do_test_api_key(params, user_id=user_id, login_ip=login_ip)
