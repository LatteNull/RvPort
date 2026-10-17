# 标准库导入
import json
import re
import os
import platform
import shlex
import sqlite3
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Optional

# 第三方库导入
import requests
import sqlcipher3
from flask import Response

# 项目路径设置
MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# 项目导入 - common 模块
from common.ai_key.ai_key_utils import AIKey, get_model, DEFAULT_AI_HTTP_UA
from common.db.SQLOperation import get_conn
from common.public import logger
from common.public.public import get_codemig_data_path

# 项目导入 - framework 模块
from framework.user_manager.user_db import UserManager

# 项目导入 - plugin.codemig 模块
from plugin.codemig.ai_assistant.ai_data_status import AiDataStatus
from plugin.codemig.ai_assistant.api_key_manager import get_agent_config_from_db, sanitize_cmd_for_log
from plugin.codemig.ai_assistant.analysis_stream_event import (
    _format_pi_env_summary,
    _get_action_map,
    _handle_assistant_message,
    _handle_content_block_delta,
    _handle_content_block_start,
    _handle_error_message,
    _handle_pi_message_end,
    _handle_pi_message_update,
    _handle_pi_tool_execution_end,
    _handle_pi_tool_execution_start,
    _handle_pi_tool_execution_update,
    _handle_pi_toolcall_end,
    _handle_system_message,
    _handle_tool_call_message,
    _handle_user_message,
    _sanitize_fences_in_details,
)
from plugin.codemig.codemig_common.common_git import (
    commit_git_repo,
    get_repo_path,
    query_new_files_from_git,
    restore_workspace,
    reset_to_commit,
    list_project_history,
    generate_patch_between,
)
from plugin.codemig.codemig_common.codemig_common_utils import (
    FileSource,
    get_database_path,
    query_file_by_path_from_database,
    query_file_info_from_database,
    query_user_id_from_database,
    save_generated_file_to_database,
    query_ai_suggestion_from_database,
    set_ai_score_to_database,
    query_ai_score_from_database,
    create_ai_info_to_database,
    update_ai_suggestion,
    update_ai_exception,
    update_ai_result,
    NUMBER_LINES_TOO_LONG,
    CodeTooLong,
)
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.codemig_task_manager.request_processor import (
    process_updated_file,
    update_file_suggestion_to_database,
)
from plugin.codemig.dependence_process.models import (
    FileDependence,
    FileDependenceSuggestion,
)
from plugin.codemig.solver.solvers_mapping import SolverType
from framework.config_manager.config import ConfigKeys,SysConfig

LOGGER = logger.init_log('codemig')
TIMEOUT = 600  # 600秒超时

# AI模型配置
AGENT_MODEL = "DeepSeek-V3"
NORMAL_MODEL = "Qwen3"
REASONING_MODEL = "DeepSeek"

# 环境变量配置
ENV_VARS = {
    "api_key": "OPENAI_API_KEY",
    "model": "OPENAI_MODEL",
    "base_url": "OPENAI_BASE_URL",
    "http_proxy": "http_proxy",
    "https_proxy": "https_proxy"
}

# 错误消息
ERROR_MESSAGES = {
    "think_mode_not_set": "Think mode is not set",
    "working_directory_not_found": "Working directory not found",
    "unknown_think_mode": "Unknown think mode"
}


# AI 建议（Agent 过程日志）入库/回显的长度上限。
# 背景：功能验证（uttest）等阶段 Agent 会通过 write_file 产出大量文件与命令输出，
# 全量日志动辄数 MB，直接入库会导致刷新恢复时前端一次性渲染超长 Markdown 卡死。
# 策略：保留头部（含任务规划）+ 尾部（含结论），中部折叠为省略标记。
SUGGESTION_DB_HEAD_LIMIT = 300_000   # 保留前 300KB
SUGGESTION_DB_TAIL_LIMIT = 100_000   # 保留后 100KB


_CHUNK_FENCE_RE = re.compile(r"^(\s*)`{3,}")


def _indent_fences_in_chunk(chunk: str) -> str:
    """流式增量内的 ``` 围栏行加 4 空格缩进（仅在思考折叠块开启期间被调用）。

    与 _sanitize_fences_in_details 的整串状态机不同：这里拿到的只是当前 delta，
    没有"块内"上下文（调用方已保证此时块处于开启态），因此对所有围栏行
    一律缩进化——思考块内本就不应保留围栏语法（模型不知道自己在 HTML 块
    里写代码），渲染为缩进代码块观感等价且绝对安全。
    快速路径：不含 ``` 前缀的行直接原样返回，流式热路径零开销。
    """
    if "`" not in chunk or "```" not in chunk:
        return chunk
    out = []
    for line in chunk.split("\n"):
        if _CHUNK_FENCE_RE.match(line):
            out.append("    " + line.lstrip(" \t"))
        else:
            out.append(line)
    return "\n".join(out)


class ThinkingFenceBuffer:
    """思考折叠块流式增量的换行缓冲清洗器。

    问题（实测复现）：pi 的 thinking_delta 是任意切分的 token 片段，一个
    ``` 围栏可能拆成 "``" + "`" 两个 delta 到达。逐 delta 扫描时两个片段都
    不含完整 ```，快速路径直接放行——原始围栏进入前端累积 buffer，marked
    把块后所有内容吞进代码块、全部 <details> 被转义（"思考和正文全包进思考
    块"+"展开态丢失"两个表象同源）。前端 buffer 不会重新清洗，泄漏一次整个
    会话视图就持续损坏。

    做法：只对"完整行"（以 \n 结尾）做清洗放行；行尾残片留在缓冲区等下个
    delta 拼接。围栏行只在拼完整后才可见，跨 delta 拆分不再漏。块关闭/
    边界处 flush 把残片放出（此时块已不在开启态，残片按普通文本走，但为
    保险 flush 也过一遍缩进化——调用方保证 flush 时块仍开启的场景）。
    """

    def __init__(self):
        self._pending = ""

    def feed(self, delta: str) -> str:
        """喂入一个 delta，返回可安全下发的完整行部分（可能为空串）。"""
        if not delta:
            return ""
        self._pending += delta
        if "\n" not in self._pending:
            return ""
        idx = self._pending.rfind("\n")
        complete, self._pending = self._pending[:idx + 1], self._pending[idx + 1:]
        return _indent_fences_in_chunk(complete)

    def flush(self) -> str:
        """块关闭/边界时放出残片（调用方决定是否再过缩进化）。"""
        rest, self._pending = self._pending, ""
        return rest


def _line_value_of(result) -> str:
    """从 to_line 产出的行结构里取 value 字段（status|value 的 json bytes）。"""
    try:
        payload = json.loads(result.decode("utf-8"))
        return payload.get("value") or ""
    except Exception:
        return ""


def _replace_line_value(result, new_value) -> bytes:
    """替换 to_line 行的 value 字段，status 保持不变。"""
    payload = json.loads(result.decode("utf-8"))
    payload["value"] = new_value
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def close_unclosed_details(text: str) -> str:
    """为流中断遗留的未闭合 <details> 块补齐闭合标签。

    背景：pi 协议 tool_execution_start 会向前端流出 "<details>...<summary>...</summary>"，
    正常由 tool_execution_end 补 "</div></details>" 收尾；但用户点"停止生成"
    （GeneratorExit 后 generator 不能再 yield）或协议丢事件时，这个闭合标签永远
    不会发出。未闭合的 <details> 在 markdown 渲染时会把其后所有内容吞进折叠块。

    前端（file-change-view / project-migrate-view）只有 s/strike/del 与 <div>
    行级清洗，**没有** details 兜底，所以必须在持久化前（后端）清洗。

    做法：统计 <details...> 开标签与 </details> 闭标签的差值，在文末补齐。
    <summary> 是 <details> 的子元素且总在开标签后立即出现，无需单独处理。
    与 </div></details> 成对出现的 </div> 属于历史存量噪声（前端已有行级清洗），
    这里只对齐 details 的配对，不追算 div。
    """
    if not isinstance(text, str) or not text:
        return text
    open_count = len(re.findall(r"<details\b[^>]*>", text))
    if open_count == 0:
        return text
    close_count = len(re.findall(r"</details\s*>", text))
    deficit = open_count - close_count
    if deficit <= 0:
        return text
    return text + "\n</details>\n" * deficit


def truncate_suggestion_for_db(suggestion: str,
                               head_limit: int = SUGGESTION_DB_HEAD_LIMIT,
                               tail_limit: int = SUGGESTION_DB_TAIL_LIMIT) -> str:
    """超长 AI 建议入库前的截断：保头 + 保尾 + 省略标记。

    头部承载任务规划/前期动作、尾部承载结论与收尾输出，中部多为重复的工具输出，
    截断后仍能完整还原"做了什么、结果如何"。低于阈值时原样返回。

    入库前先过 close_unclosed_details：用户"停止生成"时 parse_agent_output 收到
    GeneratorExit 不能再 yield（pi 路径 tool_execution_start 开启的 <details> 折叠块
    无法在流内闭合），中断路径的 finally 把 log 原样读回入库 —— 未闭合标签必须
    在这个持久化出口统一补齐。先闭合再截断，还能避免截断恰好切掉闭合标签。

    同时过 _sanitize_fences_in_details：<details> 块内模型输出的裸 ``` 围栏经
    marked 解析会吞掉块后所有内容（实测 90KB），入库前统一缩进化，刷新恢复
    与流式视图表现一致。
    """
    if not isinstance(suggestion, str):
        return suggestion
    suggestion = _sanitize_fences_in_details(suggestion)
    suggestion = close_unclosed_details(suggestion)
    total_limit = head_limit + tail_limit
    if len(suggestion) <= total_limit:
        return suggestion
    omitted = len(suggestion) - total_limit
    head = suggestion[:head_limit]
    tail = suggestion[-tail_limit:]
    marker = (
        f"\n\n…（中间内容过长已省略 {omitted} 字符；"
        f"原始长度 {len(suggestion)} 字符，仅保留前 {head_limit // 1000}KB 与后 {tail_limit // 1000}KB）\n\n"
    )
    return head + marker + tail


SELECT_CHANGE_SQL = (
    "SELECT "
    "    File.file_path AS file_path,"
    "    Suggestion.type AS suggestion_type,"
    "    Suggestion.start_line_number AS start_line_number,"
    "    Suggestion.end_line_number AS end_line_number,"
    "    Suggestion.suggestion AS suggestion "
    "FROM codemig_task_directory_file AS File "
    "JOIN codemig_task_directory_file_suggestion AS Suggestion "
    "    ON File.file_id = Suggestion.file_id "
    "WHERE Suggestion.file_id = ? "
    "    AND Suggestion.change_id = ? "
    "    AND File.has_removed = 0 "
    "    AND File.type = 0")

# 查询文件信息（不需要change_id，用于选中行号的情况）
SELECT_FILE_SQL = (
    "SELECT "
    "    File.file_path AS file_path "
    "FROM codemig_task_directory_file AS File "
    "WHERE File.dir_id = ? "
    "    AND File.file_id = ? "
    "    AND File.has_removed = 0 "
    "    AND File.type = 0")


def create_headers() -> dict:
    """创建HTTP请求头"""
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + AIKey.get_api_key(),
        # 绕过部分网关对默认 python-requests UA 的限流(1305)，详见 ai_key_utils.DEFAULT_AI_HTTP_UA
        "User-Agent": DEFAULT_AI_HTTP_UA,
    }


def create_data(content: str, model_name: str) -> dict:
    """创建AI请求数据"""
    return {
        "model": get_model(model_name),
        "messages": [{
            "role": "user",
            "content": content,
        }],
        "temperature": 0.6,
        "max_tokens": 15_000,
        "stream": True,
    }


def create_think_mode_data(content: str, model_name: str) -> dict:
    """创建思考模式请求数据"""
    return {
        "model": get_model(model_name),
        "messages": [{
            "role": "user",
            "content": content,
        }],
        "temperature": 0.6,
        "max_tokens": 15_000,
        "stream": True,
        "chat_template_kwargs": {
            "enable_thinking": False
        },
    }


def to_line(status: AiDataStatus, value: str = "") -> bytes:
    """将状态和数据转换为JSON格式的字节流"""
    data = {"status": status.value, "value": value}
    json_data = json.dumps(data, ensure_ascii=False) + "\n"
    return json_data.encode('utf-8')


def create_response(data) -> Response:
    """创建Flask响应对象"""
    return Response(data, mimetype='application/json')


def _chown_app_before_kill(container_name: Optional[str]) -> None:
    """强杀容器前，借容器内 root 身份把 /app 属主刷回宿主机用户（best-effort）。

    背景：容器内 agent 以 root 运行，写进 bind mount（/app = 宿主机仓库目录）
    的文件属主是 root:root。正常结束时由容器命令尾部的
    `chown -R ${HOST_UID}:${HOST_GID} /app` 收尾；但 docker rm -f 发的是
    SIGKILL，sh 连同尾部 chown 一起被杀，导致 root 属主残留，宿主机 server
    （普通用户）后续 rmtree / git clean -fd / reset --hard 全部 PermissionError。

    修复：在 rm -f -v 之前 docker exec 补一次 chown。容器还活着就能把
    /app 全量（含历史强杀残留）刷回宿主机 uid/gid；容器已死则本函数
    静默失败，行为退化为改动前。

    注意：
      - uid/gid 必须在宿主机侧算好拼进 argv——docker run -e 传入的环境变量
        不会被 docker exec 继承（exec 只继承镜像 ENV），不能引用 $HOST_UID；
      - chown -R 大仓库可能耗时，设超时；超时/异常一律吞掉，保证停止主流程不被阻塞；
      - Windows 等无 os.getuid 的环境直接跳过（与 _build_chown_tail 的退化策略一致）。
    """
    if not container_name:
        return
    try:
        host_uid, host_gid = os.getuid(), os.getgid()
    except AttributeError:
        return
    try:
        subprocess.run(
            ["docker", "exec", container_name,
             "chown", "-R", f"{host_uid}:{host_gid}", "/app"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        # 容器已退出 / 不存在 / docker daemon 不可用 / chown 超时 —— 吞掉，
        # 由随后的 docker rm -f -v 收尾，残留留给运维救援命令处理。
        pass


def cleanup_process(process: subprocess.Popen, container_name: Optional[str] = None) -> None:
    """清理进程资源 + 兜底清理 docker 容器。

    之前只 terminate/kill Popen（宿主机上的 docker CLI 进程），但容器
    docker_<uuid> 是 docker daemon 启动的独立进程，父进程死掉不会被带走，
    会出现孤儿容器。本函数在 finally 中调用，等同于给容器清理上兜底：
    任何 SSE 中断 / generator 异常 / 客户端刷新页面触发的退出，
    都能保证 docker_<uuid> 被 docker rm -f -v 清掉。

    container_name 为 None 时只清理 Popen（保持旧行为）。

    rm -f -v 之前先 _chown_app_before_kill：SIGKILL 会连带杀掉容器命令尾部
    的 chown 收尾语句，借将死容器把 /app 属主刷回宿主机用户再杀。
    """
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    for pipe in [process.stdout, process.stderr]:
        if pipe:
            pipe.close()

    if container_name:
        _chown_app_before_kill(container_name)
        try:
            subprocess.run(
                ["docker", "rm", "-f", "-v", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            # 容器已退出 / 不存在 / docker daemon 抽风 —— 都算成功，吞掉
            pass


def generate_agent_response(process: subprocess.Popen, user_name: str,
                            dir_id: int, file_id=None, request_uuid=None,
                            start_time=None, agent_model=None, key_prefix=None):
    """生成Agent响应流

    Args:
        process: Agent进程对象
        user_name: 用户名, 用于保存 git 状态
        dir_id: 目录ID, 用于保存 git 状态
        log_path: 日志文件路径
        file_id: 缺失文件的ID
        request_uuid: 请求UUID
        start_time: 开始时间
        agent_model: 实际使用的模型名（仅用于前端提示）
        key_prefix: 实际使用的 API Key 前三位（仅用于前端提示，不含完整 key）
    """
    log_path = os.path.join(get_codemig_data_path(), user_name, str(dir_id), "agent_"+request_uuid+".log")
    if os.path.exists(log_path):
        os.remove(log_path)
    suggestion = ''
    interrupted = False
    try:
        if agent_model is not None:
            key_info = json.dumps({"model": agent_model, "key_prefix": key_prefix or ''},
                                  ensure_ascii=False)
            yield to_line(AiDataStatus.AGENT_KEY_INFO, key_info)
        yield to_line(AiDataStatus.RECEIVING_RESULT, "</think>")
        info = parse_agent_output(process, container_name=f"docker_{request_uuid}",
                                  env_summary=_build_env_summary(agent_model, key_prefix))
        with open(log_path, 'a', encoding='utf-8') as f:
            for chunk in info:
                # 将流数据的 value 内容写入 log_path
                try:
                    data = json.loads(chunk.decode('utf-8').strip())
                    value = data.get('value', '')
                    if value:
                        f.write(value)
                    status = data.get('status','')
                    if status == AiDataStatus.DONE.value or status == AiDataStatus.AI_SUGGESTION_CODE.value:
                        # changed 需要重新扫描
                        rescan_file(user_name, dir_id, file_id)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                yield chunk
    except (OSError, UnicodeDecodeError, subprocess.SubprocessError) as e:    
        suggestion = str(e)
        raise
    except GeneratorExit:
        # 客户端断开连接：仅做必要清理，不再 re-raise（避免 werkzeug 打印刷屏警告）
        interrupted = True
    finally:
        try:
            cleanup_process(process, container_name=f"docker_{request_uuid}")
        except Exception:
            pass
        finished_status = "interrupted" if interrupted else "completed"

        if interrupted:
            LOGGER.info(f"Agent stream interrupted by client disconnect (user={user_name}, dir_id={dir_id})")
        else:
            # Agent 生成完成后，保存 git 状态
            if user_name and dir_id and file_id:
                # Agent 生成完成后，将新增文件插入数据库
                status, msg = insert_generated_files_to_database(user_name, dir_id, file_id)
                if status:
                    LOGGER.info(f"Inserted new files after agent completion")
                else:
                    LOGGER.warning(f"Failed to insert new files after agent completion: {msg}")

                # ★ v5.0.0-DEDUP：单文件 AI 建议路径没有前端 _postBoundaryCommit 锚点；
                # 改用 force_commit_marker 强制 commit（force=True）。无论 working tree
                # dirty 与否都留 marker，避免 clean 时丢 anchor。
                force_commit_marker(
                    user_name, dir_id,
                    reason='agent-finish',
                    src='codemig-agent', stage='end', type='marker',
                )

                # changed 需要重新扫描
                rescan_file(user_name, dir_id, file_id)
            else:
                LOGGER.error(f"generate agent response err, as user_name{user_name} dir_id{dir_id} file_id{file_id}.")
        # 流式输出完成后，更新AI信息到数据库
        end_time = time.time()
        # 如果 suggestion 为空，从日志文件中读取流式输出数据
        if len(suggestion) == 0 and os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    suggestion = f.read()
            except Exception as e:
                LOGGER.error(f"Failed to read log file: {e}")
                suggestion = f"Failed to read log file: {str(e)}"

        # 计算运行时间
        run_time = end_time - start_time if start_time else 0
        update_ai_result(user_name, dir_id, request_uuid, run_time,
                         truncate_suggestion_for_db(suggestion), finished_status)
        if os.path.exists(log_path):
            # suggestion 已存到数据库，可以删除记录文件
            os.remove(log_path)


def insert_generated_files_to_database(user_name: str, dir_id: int,
                                       source_file_id: int) -> tuple[bool, str]:
    """
    将新增文件插入数据库
    1. 查询 user_id
    2. 通过git查询新增文件 common_git.py中的函数 query_new_files_from_git
    3. 将文件信息插入数据库
    """
    try:
        status, user_id = query_user_id_from_database(user_name, dir_id)
        if not status or user_id is None:
            return False, "Query user_id failed"

        # 通过 git 获取新增文件（相对 repo 根目录的路径）
        status, new_files = query_new_files_from_git(user_name, dir_id)
        if not status:
            return False, "Query new files from git failed"
        if len(new_files) == 0:
            return True, "Success, no new files"

        # repo 目录（用于将相对路径转为绝对路径写入数据库）
        code_path = get_repo_path(user_name, dir_id)
        # 去重、并补齐父目录
        dir_paths: set[str] = set()
        file_paths: set[str] = set()
        for rel in new_files:
            rel = (rel or "").strip().lstrip("./")
            if not rel:
                continue
            # 迁移内部产物不入库：agent 容器写入的 .prompt.txt（提示词）与
            # .skills/（skill 文档）属于工具运行机制，不是迁移产物，
            # 混入 DB 会经 filetree 接口泄漏进前端文件树。
            parts = PurePosixPath(rel).parts
            if ".skills" in parts or PurePosixPath(rel).name == ".prompt.txt":
                continue
            abs_path = (code_path / rel).resolve()
            file_paths.add(abs_path.as_posix())

            # 记录父目录链路（避免新增目录未入库）
            parent = abs_path.parent
            while parent != code_path and str(parent).startswith(str(code_path)):
                dir_paths.add(parent.as_posix())
                parent = parent.parent

        # 先插入目录（从浅到深）
        for d in sorted(dir_paths, key=lambda x: x.count("/")):
            # 若数据库已存在则跳过
            ok, existing_id = query_file_by_path_from_database(user_name, dir_id, d)
            if ok and existing_id is not None:
                continue
            save_generated_file_to_database(user_name, user_id, dir_id, d, 
                                            FileSource.GENERATE.value, 
                                            False, source_file_id)

        # 再插入文件
        inserted = 0
        for f in sorted(file_paths):
            ok, existing_id = query_file_by_path_from_database(user_name, dir_id, f)
            if ok and existing_id is not None:
                continue
            # 文件可能被删除/移动，若不存在则跳过
            if not Path(f).exists():
                continue
            is_file = Path(f).is_file()
            status, _file_id = save_generated_file_to_database(user_name, user_id,
                                                               dir_id, f,
                                                               FileSource.GENERATE.value,
                                                               is_file, source_file_id)
            if status:
                inserted += 1

        return True, f"Success, inserted {inserted} new files"

    except OSError as e:
        LOGGER.error("insert_generated_files_to_database failed: %s", e, exc_info=True)
        return False, str(e)


def generate_streaming_response(response: requests.Response,
                                user_name=None, dir_id=None,
                                request_uuid=None, start_time=None):
    """生成流式响应
    
    Args:
        response: requests响应对象
        log_path: 日志文件路径
        user_name: 用户名
        dir_id: 目录ID
        request_uuid: 请求UUID
        start_time: 开始时间
    """
    log_path = os.path.join(get_codemig_data_path(), user_name, str(dir_id), "agent_"+request_uuid+".log")
    if os.path.exists(log_path):
        os.remove(log_path)
    suggestion = ''
    in_reasoning = False  # 追踪是否处于推理内容阶段
    try:
        with open(log_path, "a") as f:
            for chunk in response.iter_lines():
                if not chunk:
                    yield to_line(AiDataStatus.RECEIVING_RESULT)
                    continue

                chunk_data = chunk[6:]
                if chunk_data == b'[DONE]':
                    # 如果仍在推理阶段，发送结束标签
                    if in_reasoning:
                        in_reasoning = False
                        yield to_line(AiDataStatus.RECEIVING_RESULT, '</think/>')
                    yield to_line(AiDataStatus.DONE)
                    continue

                try:
                    json_data = json.loads(chunk_data)
                    choices = json_data.get('choices', [])
                    if not choices:
                        yield to_line(AiDataStatus.RECEIVING_RESULT)
                        continue

                    delta = choices[0].get('delta', {})
                    reasoning_content = delta.get('reasoning_content', '')
                    delta_content = delta.get('content', '')

                    # 处理推理内容（reasoning_content）
                    if reasoning_content:
                        if not in_reasoning:
                            in_reasoning = True
                            yield to_line(AiDataStatus.RECEIVING_RESULT, '<think/>')
                        yield to_line(AiDataStatus.RECEIVING_RESULT, reasoning_content)

                    # 处理正文内容（content）
                    if delta_content:
                        # 如果从推理阶段切换到正文，发送结束标签
                        if in_reasoning:
                            in_reasoning = False
                            yield to_line(AiDataStatus.RECEIVING_RESULT, '</think/>')
                        f.write(delta_content)
                        yield to_line(AiDataStatus.RECEIVING_RESULT, delta_content)

                    # 既没有推理内容也没有正文内容（空delta），跳过
                    if not reasoning_content and not delta_content:
                        yield to_line(AiDataStatus.RECEIVING_RESULT)
                except json.JSONDecodeError as e:
                    LOGGER.error(f'Json decode err {e}')
                    yield to_line(AiDataStatus.RECEIVING_RESULT)
    except (OSError, PermissionError, requests.RequestException) as e:
        suggestion = str(e)
        yield to_line(AiDataStatus.UNKNOWN_ERROR)
    finally:
        # 流式输出完成后，保存AI信息到数据库
        end_time = time.time()
        # 如果 suggestion 为空，从日志文件中读取流式输出数据
        if len(suggestion) == 0 and os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    suggestion = f.read()
            except (OSError, PermissionError, UnicodeDecodeError) as e:
                LOGGER.error(f"Failed to read log file: {e}")
                suggestion = f"Failed to read log file: {str(e)}"
        # 计算运行时间
        run_time = end_time - start_time if start_time else 0
        update_ai_suggestion(user_name, dir_id, request_uuid, run_time, suggestion)


# agent stream-json 的 result 行里，表示失败的 subtype 取值（含常见拼写变体）
_AGENT_RESULT_FAILURE_SUBTYPES = frozenset({
    "error", "failed", "fail", "cancel", "cancelled", "canceled", "cancle",
})


def _sanitize_agent_user_visible_error(text: str) -> str:
    """对用户可见文案去品牌化，避免出现第三方 IDE/产品名。"""
    if not isinstance(text, str):
        return str(text)
    t = re.sub(r"(?i)\bcursor\b", "", text)
    t = " ".join(t.split())
    return (t.strip() or "AI 服务调用失败")[:4000]


def _format_agent_stream_json_result_error_message(data: dict) -> str:
    """从 agent stream-json 的 result 行中整理对外展示的错误文案。"""
    err_obj = data.get("error")
    if err_obj is not None:
        if isinstance(err_obj, dict):
            for key in ("message", "msg", "detail", "reason", "description"):
                val = err_obj.get(key)
                if isinstance(val, str) and val.strip():
                    return _sanitize_agent_user_visible_error(val)
        elif isinstance(err_obj, str) and err_obj.strip():
            return _sanitize_agent_user_visible_error(err_obj)

    # 仅在已标记失败时读取顶层 message，避免与成功响应中的附言字段冲突
    if data.get("is_error") is True or data.get("failed") is True:
        for key in ("message", "reason", "detail", "failure_reason"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return _sanitize_agent_user_visible_error(val)

    result_text = data.get("result")
    if isinstance(result_text, str) and result_text.strip():
        first_line = result_text.strip().split("\n", 1)[0].strip()
        if first_line.startswith("[") and "]" in first_line:
            end = first_line.index("]")
            inner = first_line[1:end].strip()
            if inner:
                return _sanitize_agent_user_visible_error(inner)
        return _sanitize_agent_user_visible_error(first_line[:4000])
    return "AI 服务调用失败（无详细说明）"


def _agent_result_embedded_failure_in_body(result_text: str) -> bool:
    """result 正文中是否内嵌了失败信息（与 is_error=false 等矛盾时仍视为失败）。"""
    if not isinstance(result_text, str) or not result_text.strip():
        return False
    low = result_text.lower()
    markers = (
        "[api error:",
        "\napi error:",
        "api error:",
        "[error:",
        "[request cancelled",
        "request cancelled",
        "[cancelled]",
        "[canceled]",
        "quota limitations",
        "rate limit",
        "余额不足",
    )
    return any(m in low for m in markers)


def _agent_stream_json_result_api_error_message(data: dict) -> Optional[str]:
    """
    判断 agent stream-json 中 type==result 是否表示底层 API/额度/取消等失败。

    需同时考虑：is_error、subtype、error/failed/cancel 等字段，以及 result 正文内嵌报错。
    若判定为失败则返回对外展示字符串（已去品牌化），否则返回 None。
    """
    if not isinstance(data, dict):
        return None

    if data.get("is_error") is True:
        return _format_agent_stream_json_result_error_message(data)

    if data.get("failed") is True:
        return _format_agent_stream_json_result_error_message(data)

    for cancel_key in ("cancel", "cancelled", "canceled", "cancle"):
        if data.get(cancel_key) is True:
            msg = _format_agent_stream_json_result_error_message(data)
            if msg and msg != "AI 服务调用失败（无详细说明）":
                return msg
            return "请求已取消或中断"

    subtype = (data.get("subtype") or "").lower()
    if subtype in _AGENT_RESULT_FAILURE_SUBTYPES:
        return _format_agent_stream_json_result_error_message(data)

    err_top = data.get("error")
    if err_top is not None and not (isinstance(err_top, str) and not err_top.strip()):
        return _format_agent_stream_json_result_error_message(data)

    result_text = data.get("result")
    if isinstance(result_text, str) and result_text:
        if _agent_result_embedded_failure_in_body(result_text):
            return _format_agent_stream_json_result_error_message(data)
        stripped = result_text.lstrip()
        if stripped.upper().startswith("API ERROR:") or stripped.upper().startswith("ERROR:"):
            return _format_agent_stream_json_result_error_message(data)
    return None


def parse_agent_output(process: subprocess.Popen, container_name: Optional[str] = None,
                       env_summary: Optional[dict] = None):
    """
    解析Agent输出流，按行读取JSON并提取内容，注：高版本的glm才支持流式输出

    Args:
        process: Agent进程对象
        container_name: 容器名（清理用）
        env_summary: 开头运行信息摘要上下文（model / key_prefix / mcp_servers），
                     由调用侧（generate_agent_response 等）传入；None 则不输出摘要。

    Yields:
        bytes: 流式响应数据
    """
    active_tool_name = ""  # 记录当前正在调用的工具名
    json_buffer = ""  # 记录当前正在生成的参数字符串
    # [累积参数buffer, 上次已展示摘要(单路径工具去重), write_file头部是否已发送]
    # 持久引用：跨多个 input_json_delta 事件保持去重/标记状态，避免重复输出
    json_buffer_ref = ["", None, False]
    is_in_details = False  # 追踪当前是否处于折叠标签内
    saw_stream_event = False  # 是否收到过流式事件
    saw_result = False  # 是否收到过 type=="result"（用于判断 agent 是否正常结束）
    saw_result_ok = True  # result 行是否表示成功（无 API 内嵌错误）；未收到 result 时仍走无 result 分支
    # ★ pi 协议 API 错误透传：pi 的 message_end/turn_end 在底层 API 调用失败（如
    #   413 Payload Too Large / 超时 / 5xx）时 message.stopReason=="error" 且带
    #   errorMessage；且 pi 进程仍以 exit 0 + agent_settled 正常收尾——不在这里
    #   捕获的话，DONE 事件会带 has_result:true/returncode:0/result_ok:true，
    #   前端把"Agent 死于 API 错误"判成迁移成功并解锁下一阶段（线上实锤：
    #   ai_id=8 建议 164 字符、docker 容器内 413）。
    #   首个错误记全文（对用户展示），后续错误（pi 自动重试同错）只计数抑制刷屏。
    pi_api_error_reported = False
    pi_api_error_count = 0
    sent_tasks = set()  # 用于记录 todo_write 已经发送过的任务，防止重复
    action_map = _get_action_map()
    stream_text_accum = ""  # 累积 text_delta，用于 assistant 汇总去重/补发，避免丢文本
    # pi agent stream-json 协议适配状态（与现有 cursor/anthropic 协议并行）
    pi_in_thinking = [False]  # 当前是否处于 thinking 段（list 包装，便于 generator 内 mutate）
    pi_in_text = [False]  # 当前是否处于 text 段
    pi_thinking_buffer = [""]  # message_update.assistantMessageEvent.thinking_delta 累加（list 包装，供 handler 内部 mutate）
    pi_text_buffer = [""]  # message_update.assistantMessageEvent.text_delta 累加（list 包装）
    pi_saw_any_delta = False  # 是否收到过任何 pi 的 thinking/text delta（触发去重路径）
    pi_assistant_message_started = False  # 当前是否处于 assistant message_start..message_end 区间
    pi_active_tool_name_ref = [""]  # 当前 pi tool_call 名，供 tool_execution_* 复用
    pi_json_buffer_ref = [""]  # 当前 pi tool_call 的 arguments json 字符串
    pi_is_in_details_ref = [False]  # 是否处于 pi 工具的折叠块内
    # tool_execution_start 开启的折叠块独立跟踪（由 tool_execution_end 收尾）；
    # 流异常中断时据此在收尾处补发闭合标签，避免未闭合 <details> 吞掉后续输出
    pi_exec_in_details_ref = [False]
    # ★ tool_execution_update 进度去重签名：subagent_wait 等长轮询工具的进度
    #   是周期性全量快照（数字归一后形态几乎不变），逐条透传会把折叠块撑到
    #   数千行。start/end 事件处复位（新块新签名）。
    pi_last_update_sig_ref = [""]
    # ★ update 已发出的最后一条原文：pi 短工具的 end.result 常与最后一条
    #   update.partialResult 完全一致，一致时 end 跳过结果避免双份。
    pi_last_update_text_ref = [""]
    # ★ 思考折叠块独立跟踪（thinking_delta 开 / thinking_end 关）：
    #   thinking_end 丢失（协议丢事件）时在 turn/message 边界据此补发 </details>；
    #   与 pi_exec_in_details_ref 同套路。「停止生成」（GeneratorExit）路径的
    #   兜底同样落在持久化出口 close_unclosed_details。
    pi_thinking_details_open_ref = [False]
    # ★ 思考块流式围栏清洗的换行缓冲：跨 delta 拆分的 ``` 围栏只有拼成完整
    #   行后才可判定，逐 delta 扫描会漏（详见 ThinkingFenceBuffer docstring）。
    pi_thinking_fence_buffer = ThinkingFenceBuffer()

    def _flush_thinking_fence_buffer(indent=True):
        """放出换行缓冲残片。indent=True 时（块仍开启）过围栏缩进化。"""
        rest = pi_thinking_fence_buffer.flush()
        if rest and indent:
            rest = _indent_fences_in_chunk(rest)
        return rest

    def _close_pi_thinking_details():
        """补发思考折叠块的 </details>（仅当块仍开启）。边界处 yield from 调用。

        关闭前先 flush 换行缓冲：thinking_end 到达时最后一段思考文本还挂在
        缓冲区里，不 flush 会丢内容；flush 在块仍开启时过围栏缩进化。
        """
        if pi_thinking_details_open_ref[0]:
            tail = _flush_thinking_fence_buffer(indent=True)
            if tail:
                yield to_line(AiDataStatus.RECEIVING_RESULT, tail)
            pi_thinking_details_open_ref[0] = False
            yield to_line(AiDataStatus.RECEIVING_RESULT, "\n</details>\n")
    pi_sent_tasks = set()  # pi 协议下 todo_write 去重集合（与 cursor 协议独立）
    _raise = False  # 标记是否因 GeneratorExit 退出，用于 finally 决定是否 yield DONE
    try:
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                msg_type = data.get("type")
                # --- 情况 1: 系统初始化 (system) ---
                if msg_type == "system":
                    for result in _handle_system_message(data):
                        yield result

                # --- 情况 2: 流式增量事件 (stream_event) ---
                elif msg_type == "stream_event":
                    event = data.get("event", {})
                    event_type = event.get("type")
                    saw_stream_event = True
                    
                    if event_type == "content_block_delta":
                        # 复用持久 json_buffer_ref（3槽），在函数内部原地更新
                        json_buffer_ref[0] = json_buffer
                        # 先累计 text_delta，避免 assistant 汇总阶段被丢弃导致缺失
                        delta = event.get("delta", {}) or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                stream_text_accum += text

                        for result in _handle_content_block_delta(event, json_buffer_ref, active_tool_name, action_map, sent_tasks):
                            yield result
                        json_buffer = json_buffer_ref[0]  # 获取更新后的值
                    elif event_type == "content_block_start":
                        tool_name, init_msg = _handle_content_block_start(event)
                        if tool_name:
                            active_tool_name = tool_name
                            json_buffer = ""  # 重置参数缓冲区
                            json_buffer_ref[0] = ""
                            json_buffer_ref[1] = None
                            json_buffer_ref[2] = False
                            is_in_details = True
                            sent_tasks.clear()
                            yield to_line(AiDataStatus.RECEIVING_RESULT, init_msg)
                    elif event_type == "content_block_stop":
                        if is_in_details:
                            if active_tool_name == "write_file" and json_buffer_ref[2]:
                                yield to_line(AiDataStatus.RECEIVING_RESULT, "```\n")
                            yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")
                            is_in_details = False

                # --- 情况 3: 汇总消息 (assistant) ---
                elif msg_type == "assistant":
                    for result in _handle_assistant_message(data, saw_stream_event, stream_text_accum):
                        yield result


                # --- 情况 4: 工具执行结果 (user类型反馈) ---
                elif msg_type == "user":
                    _handle_user_message(data, is_in_details)

                # --- 情况 5: 错误处理 (error) ---
                elif msg_type == "error":
                    for result in _handle_error_message(data):
                        yield result

                # --- 情况 6: 工具调用 (tool_call, stream-json) ---
                elif msg_type == "tool_call":
                    for result in _handle_tool_call_message(data, action_map, sent_tasks):
                        yield result

                # --- 情况 7: 结果输出 result ---
                elif msg_type == "result":
                    # agent 正常结束的标志：stream-json 最终会输出一条 type=="result"
                    saw_result = True
                    err_msg = _agent_stream_json_result_api_error_message(data)
                    if err_msg:
                        saw_result_ok = False
                        LOGGER.warning(
                            "Agent result 行表示 API/额度失败: subtype=%s is_error=%s detail=%s",
                            data.get("subtype"),
                            data.get("is_error"),
                            err_msg[:500],
                        )
                        yield to_line(AiDataStatus.BACKEND_ERROR, err_msg)
                    # 成功时通常无需向前端重复展示 result 全文（避免重复/过长）
                    continue

                # --- 情况 8: pi agent stream-json 协议 ---
                # 与 cursor/anthropic 协议并行；不修改上述任何 elif 的处理逻辑。
                elif msg_type == "session":
                    # 开头运行信息摘要：模型 / Key / session / MCP（替代旧的
                    # 🔌 session 独立帧）。session_id 从事件里取，模型与 Key
                    # 由调用侧 env_summary 提供；两处都没有时不输出。
                    summary_ctx = dict(env_summary or {})
                    summary_ctx["session_id"] = data.get("id") or ""
                    if summary_ctx.get("model") or summary_ctx.get("session_id"):
                        yield to_line(
                            AiDataStatus.RECEIVING_RESULT,
                            _format_pi_env_summary(summary_ctx),
                        )
                    yield from _close_pi_thinking_details()
                    pi_in_thinking[0] = False
                    pi_in_text[0] = False
                    pi_thinking_buffer[0] = ""
                    pi_text_buffer[0] = ""
                elif msg_type == "agent_start":
                    # 仅做状态复位，状态变量由 message_update 维护。
                    # 「▶️ Agent 开始」帧已删除：开始态由前端 loading 动画表达。
                    yield from _close_pi_thinking_details()
                    pi_in_thinking[0] = False
                    pi_in_text[0] = False
                    pi_thinking_buffer[0] = ""
                    pi_text_buffer[0] = ""
                    pi_saw_any_delta = False

                elif msg_type == "turn_start":
                    # turn 开始时清理上一 turn 残留
                    yield from _close_pi_thinking_details()
                    pi_in_thinking[0] = False
                    pi_in_text[0] = False
                    pi_thinking_buffer[0] = ""
                    pi_text_buffer[0] = ""
                    pi_saw_any_delta = False

                elif msg_type == "message_start":
                    # message_start.message.role 用于区分 assistant / user / toolResult / custom
                    # - assistant：模型输出的消息主链
                    # - toolResult：工具调用的 I/O 上下文消息（内容已经通过 tool_execution_end
                    #   流向前端，这里仅做状态隔离，避免被 assistant 路径误处理）
                    # - custom：pi agent 注入的系统级提示（如 subagent-notify 后台任务完成
                    #   通知）；内容是 markdown 文本，需要透传到前端，否则 AI 面板看不到
                    #   后台异步 subagent 的完成汇报
                    msg = data.get("message") or {}
                    role = msg.get("role") or ""
                    pi_assistant_message_started = (role == "assistant")
                    if role == "toolResult":
                        # 重置 in-message 流式状态，避免与上一轮残留混淆
                        yield from _close_pi_thinking_details()
                        pi_in_thinking[0] = False
                        pi_in_text[0] = False
                        pi_thinking_buffer[0] = ""
                        pi_text_buffer[0] = ""
                        pi_saw_any_delta = False

                elif msg_type == "message_update":
                    sub = data.get("assistantMessageEvent") or {}
                    sub_type = sub.get("type")
                    if sub_type == "toolcall_end":
                        for result in _handle_pi_toolcall_end(
                            data,
                            action_map,
                            pi_sent_tasks,
                            pi_active_tool_name_ref,
                            pi_json_buffer_ref,
                            pi_is_in_details_ref,
                        ):
                            yield result
                    else:
                        # thinking_start/_delta/_end + text_start/_delta/_end 全部走这里
                        if sub_type in ("thinking_delta", "text_delta"):
                            pi_saw_any_delta = True
                        # ★ 思考块流式围栏清洗（换行缓冲版）：thinking_delta 经
                        # ThinkingFenceBuffer 只放行完整行，跨 delta 拆分的 ```
                        # 围栏拼完整后才被缩进化，杜绝逐 delta 扫描的漏网——
                        # 一旦泄漏，前端累积 buffer 不再清洗，marked 会把块后
                        # 所有内容吞进代码块（"正文全包进思考块"的根因）。
                        # text_delta 不缓冲：正文在块外，围栏合法且需要实时性。
                        pending_thinking_delta = sub_type == "thinking_delta"
                        for result in _handle_pi_message_update(
                            data,
                            pi_in_thinking,
                            pi_in_text,
                            pi_thinking_buffer,
                            pi_text_buffer,
                            pi_thinking_details_open_ref,
                            _flush_thinking_fence_buffer,
                        ):
                            value = _line_value_of(result)
                            if (pending_thinking_delta and value
                                    and not value.lstrip(" \t").startswith("<details>")
                                    and not value.lstrip(" \t").startswith("</details>")):
                                # 块开标签行直接放行；思考文本经换行缓冲清洗
                                safe = pi_thinking_fence_buffer.feed(value)
                                if safe:
                                    yield _replace_line_value(result, safe)
                                continue
                            yield result
                        # thinking_end 的关块路径在 _handle_pi_message_update 内部
                        # 已通过 _flush_thinking_fence_buffer 放出残片，此处无需处理。

                elif msg_type == "message_end":
                    # assistant 消息定型；按已收集的 stream 做去重
                    if pi_assistant_message_started:
                        # ★ API 错误透传：stopReason=error 且带 errorMessage 说明模型
                        #   调用失败（pi 自动重试耗尽后放弃）。置 saw_result_ok=False，
                        #   让 DONE 的 result_ok=false 走前端错误分支；同时发一条
                        #   BACKEND_ERROR 流事件，把具体错误（413/超时等）透传到
                        #   AI 建议区，而不是让用户看到"什么都没输出"。
                        msg = data.get("message") or {}
                        if msg.get("stopReason") == "error":
                            pi_api_error_count += 1
                            if not pi_api_error_reported:
                                pi_api_error_reported = True
                                saw_result_ok = False
                                err_text = _sanitize_agent_user_visible_error(
                                    msg.get("errorMessage") or "模型服务调用失败")
                                LOGGER.warning(
                                    "pi agent 模型调用失败: %s（后续同错已抑制）", err_text[:500])
                                yield to_line(
                                    AiDataStatus.BACKEND_ERROR,
                                    f"AI 服务调用失败：{err_text}")
                        for result in _handle_pi_message_end(
                            data,
                            pi_thinking_buffer[0],
                            pi_text_buffer[0],
                            pi_saw_any_delta,
                        ):
                            yield result
                    else:
                        # toolResult / user / custom 等其它角色的 message_end：清理局部流式状态，
                        # 但不触发 assistant 路径的 _handle_pi_message_end。
                        msg = data.get("message") or {}
                        role = msg.get("role") or ""
                        # role=="custom"：pi 注入的系统通知（典型如 subagent-notify 后台任务
                        # 完成汇报），content 是 markdown 文本块；透传到前端以便 AI 面板看到。
                        if role == "custom":
                            custom_type = msg.get("customType") or "notify"
                            raw_content = msg.get("content")
                            pieces = []
                            # pi 的 subagent-notify 在 message_start/message_end 阶段
                            # content 是字符串（直接是 markdown 文本），而在
                            # agent_end 的 messages 数组里 content 才是
                            # list-of-dict；两种形态都要兼容。
                            if isinstance(raw_content, str):
                                if raw_content:
                                    pieces.append(raw_content)
                            elif isinstance(raw_content, list):
                                for item in raw_content:
                                    if isinstance(item, dict):
                                        txt = item.get("text") or ""
                                        if txt:
                                            pieces.append(txt)
                            joined = "".join(pieces)
                            if joined:
                                if len(joined) > 10_000:
                                    joined = joined[:10_000] + "\n…（系统通知过长，已截断）"
                                header = f"\n\n📣 **[Agent 通知 · {custom_type}]**\n\n"
                                yield to_line(
                                    AiDataStatus.RECEIVING_RESULT,
                                    f"{header}{joined}\n",
                                )
                        else:
                            LOGGER.debug(
                                "pi message_end role=%s toolCallId=%s (skipped assistant finalize)",
                                role,
                                msg.get("toolCallId"),
                            )
                    yield from _close_pi_thinking_details()
                    pi_in_thinking[0] = False
                    pi_in_text[0] = False
                    pi_thinking_buffer[0] = ""
                    pi_text_buffer[0] = ""
                    pi_saw_any_delta = False
                    pi_assistant_message_started = False

                elif msg_type == "turn_end":
                    # turn 结束：仅清理状态
                    yield from _close_pi_thinking_details()
                    pi_in_thinking[0] = False
                    pi_in_text[0] = False

                elif msg_type == "agent_end":
                    # agent 结束：不再发「⏹️ Agent 结束」视觉帧——结束态已由 DONE
                    # 事件 + 前端节点徽章表达，重复帧只占 AI 建议区空间。
                    # turn_end.message 与 agent_end.messages 里同样可能带
                    # stopReason=error（message_end 丢失时的兜底路径），补一次
                    # API 错误检测，保证任何形态的 413/超时都能透传。
                    msg = data.get("message") or {}
                    if msg.get("stopReason") == "error":
                        pi_api_error_count += 1
                        if not pi_api_error_reported:
                            pi_api_error_reported = True
                            saw_result_ok = False
                            err_text = _sanitize_agent_user_visible_error(
                                msg.get("errorMessage") or "模型服务调用失败")
                            LOGGER.warning(
                                "pi agent 模型调用失败(agent_end 兜底): %s", err_text[:500])
                            yield to_line(
                                AiDataStatus.BACKEND_ERROR,
                                f"AI 服务调用失败：{err_text}")

                elif msg_type == "agent_settled":
                    # pi 协议的结束信号，等价于 cursor 协议的 {"type": "result"}
                    saw_result = True

                elif msg_type == "tool_execution_start":
                    pi_last_update_sig_ref[0] = ""
                    pi_last_update_text_ref[0] = ""
                    for result in _handle_pi_tool_execution_start(data, pi_exec_in_details_ref):
                        yield result

                elif msg_type == "tool_execution_update":
                    for result in _handle_pi_tool_execution_update(
                            data, pi_last_update_sig_ref, pi_last_update_text_ref):
                        yield result

                elif msg_type == "tool_execution_end":
                    pi_last_update_sig_ref[0] = ""
                    for result in _handle_pi_tool_execution_end(
                            data, pi_exec_in_details_ref, pi_last_update_text_ref):
                        yield result

            except json.JSONDecodeError:
                # pi agent 在 stream-json 模式下，最初会有命令回显或 [url-provider] registered ... 这样的非 JSON 行；
                # 只记日志，不向前端 yield，避免 [url-provider] registered ... 污染展示。
                LOGGER.warning("pi agent 非 JSON 输出（已抑制）: %s", line)

        # 等待进程完全退出
        process.wait()

        # ★ pi 协议兜底（正常结束路径）：tool_execution_start 开启的折叠块若因
        #   agent 崩溃 / 协议丢 tool_execution_end 而未闭合，在流内补发闭合标签，
        #   避免未闭合的 <details> 把后续内容全部吞进折叠块。
        #   「停止生成」（GeneratorExit）路径 generator 不能再 yield —— 那条路径的
        #   兜底在持久化出口 truncate_suggestion_for_db → close_unclosed_details。
        if pi_exec_in_details_ref[0]:
            pi_exec_in_details_ref[0] = False
            yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")

        # 思考折叠块同理：thinking_end 丢失时在此补闭合（正常路径已在
        # thinking_end / 各边界处关闭，这里通常无操作）
        yield from _close_pi_thinking_details()

        if not saw_result:
            # 没有收到 result：通常意味着 agent 异常中断或输出格式不符合预期
            LOGGER.warning(
                "Agent stream-json finished without 'result' message. returncode=%s",
                process.returncode,
            )
            yield to_line(
                AiDataStatus.UNKNOWN_ERROR,
                "Agent 异常中断或输出格式不符合预期",
            )
        elif saw_result_ok:
            yield to_line(AiDataStatus.AI_SUGGESTION_CODE, "生成完毕")

    except (OSError, PermissionError, FileNotFoundError, FileExistsError) as e:
        LOGGER.error(f"解析Agent输出时发生错误: {e}")
        yield to_line(AiDataStatus.BACKEND_ERROR, f"解析输出错误")
    except GeneratorExit:
        # 客户端断开连接（如刷新页面、关闭标签页、切换任务）触发 generator 关闭
        # 此处必须安静退出，不能再 yield，否则会抛 "generator ignored GeneratorExit"
        _raise = True
        raise
    finally:
        # 确保进程资源被清理
        try:
            cleanup_process(process, container_name=container_name)
        except Exception:
            pass
        # DONE 标志位仅在 generator 正常生命周期内 yield；
        # 收到 GeneratorExit 后再 yield 会触发 RuntimeError 刷屏，故跳过
        if not _raise:
            yield to_line(
                AiDataStatus.DONE,
                json.dumps(
                    {
                        "has_result": saw_result,
                        "returncode": process.returncode,
                        "result_ok": bool(saw_result and saw_result_ok),
                    },
                    ensure_ascii=False,
                ),
            )


def create_ai_agent_file(file_path: str, dir_id: int, reference_arch_paths: list,
                         model: str, api_format: str, user_name: str, 
                         file_id: int, request_uuid: str):
    """
    创建AI Agent文件

    Args:
        file_path: 文件路径
        dir_id: 目录ID
        reference_arch_paths: 现有架构数据
        model: 模型名称
        user_name: 用户名
        api_format: 使用的api格式(openai或cursor)

    Returns:
        AI生成的文件内容或错误信息
    """
    if request_uuid is None or len(request_uuid) < 1:
        LOGGER.error("There is no request uuid")
        suggestion = "There is no request uuid"
        return Response(to_line(AiDataStatus.NO_REQUEST_UUID, suggestion), mimetype='application/json')

    file_path, file_name = truncate_path_to_subdir_of_dir_id(file_path, dir_id)
    full_file_path = os.path.join(file_path, file_name)
    reference_arch_paths_str = ""
    if reference_arch_paths:
        reference_arch_paths = [
            "@" + truncate_path_to_subdir_of_dir_id(existing_file, dir_id)[1]
            for existing_file in reference_arch_paths
        ]
        reference_arch_paths_str = "\n".join(reference_arch_paths)
    LOGGER.info(f"Creating AI agent file: {file_path}")

    # 在执行创建 Agent 前，检查并保存 git 状态
    if user_name and dir_id:
        # ★ v5.0.0-DEDUP：单文件 AI 建议路径没有前端 _preBoundaryCommit 锚点；
        # 改用 force_commit_marker 强制 commit（force=True）。无论 working tree
        # dirty 与否都留 marker，避免 clean 时丢 anchor。
        force_commit_marker(
            user_name, dir_id,
            reason='agent-start',
            src='codemig-agent', stage='start', type='marker',
        )

    suggestion = ''
    start_time = time.time()

    if model:
        # 按当前用户权限范围查找 API Key 配置，避免越权使用其他普通用户的 key
        user_id, is_admin = _get_user_id_and_role(user_name)
        agent_config = get_agent_config_from_db(model, user_id=user_id, is_admin=is_admin)
    else:
        LOGGER.error(f"未选择使用模型: {full_file_path}")
        suggestion = "未选择使用模型"
        return create_response(to_line(AiDataStatus.UNKNOWN_ERROR, suggestion))

    # 校验拿到的 API Key 配置有效性，避免 None/错误字典继续往下传到进程处理逻辑
    if not agent_config or not isinstance(agent_config, dict) or not agent_config.get("api_key"):
        LOGGER.error(f"未找到模型 {model} 可用的 API Key 配置 (user_id={user_id}, is_admin={is_admin})")
        suggestion = agent_config.get("msg") if isinstance(agent_config, dict) else "未找到可用的 API Key 配置"
        return create_response(to_line(AiDataStatus.BACKEND_ERROR, suggestion or "未找到可用的 API Key 配置"))
    try:
        base_prompt = prompt_templates["agent_file_prompt"].format(
            file_name=file_name,  # 传递实际的文件路径
            existing_file_paths_str=reference_arch_paths_str
        )
        cmd_list = []
        # 创建agent进程
        process = create_agent_process(base_prompt, file_path, agent_config, request_uuid, cmd_list, api_format)
        cmd = " ".join(cmd_list) if cmd_list else ""
        create_ai_info_to_database(user_name, dir_id, file_id, request_uuid, file_path, model, cmd)
        _key_prefix = (agent_config.get("api_key") or "")[:3] if agent_config else ""
        return Response(generate_agent_response(
            process, user_name, dir_id, file_id, request_uuid, start_time,
            agent_model=model, key_prefix=_key_prefix
        ), mimetype='application/json')
    except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError)  as e:
        save_intermediate_state_on_failure(user_name, dir_id, reason='intermediate-error')
        LOGGER.error(f"Working directory not found: {e}")
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)

        return Response(to_line(AiDataStatus.BACKEND_ERROR, suggestion), mimetype='application/json')
    except Exception as e:
        save_intermediate_state_on_failure(user_name, dir_id, reason='intermediate-error')
        LOGGER.error(f"创建AI Agent文件失败: {e}")
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)

        return Response(to_line(AiDataStatus.BACKEND_ERROR, suggestion), mimetype='application/json')



def _resolve_agent_credentials(agent_config):
    """从 agent_config 中取出 api_key / base_url / model；缺失 api_key 时返回错误 dict。

    返回 (creds, error)：creds 为 dict 或 None；error 为 dict 或 None（error 非空时调用方直接 return）。
    """
    if agent_config.get("api_key"):
        return (
            {
                "api_key": agent_config.get("api_key"),
                "base_url": agent_config.get("base_url"),
                "model": agent_config.get("model"),
            },
            None,
        )
    LOGGER.error("命令执行失败: Unkown API key.", exc_info=True)
    return None, {"code": -1, "msg": "Unkown API key."}


def _load_proxy_settings():
    """从 SysConfig 读取 docker 代理三项配置，缺失项置空串；同时把它们注入到 os.environ。

    返回 dict：{'https_proxy': str, 'http_proxy': str, 'no_proxy': str}。
    """
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
    })
    return {'https_proxy': https_proxy, 'http_proxy': http_proxy, 'no_proxy': no_proxy}


def _build_agent_cmd_and_env(api_format, api_key, base_url, model, content=None, use_prompt_file=False, resume=False):
    """根据 api_format 构造 agent_cmd 与注入 env 的 API 凭据。

    Args:
        api_format: 'openai' / 'cursor'。
        api_key / base_url: 来自 _resolve_agent_credentials。
        model: 模型名。
        content: create_agent_process 旧路径用——把 prompt 塞进 shell 单引号（escape '）。
        use_prompt_file: _create_project_agent_process 新路径——agent 通过 cat /app/.prompt.txt 读。
        resume: v4.x.0-RESUME 路径——切到 pi --continue / agent --continue。

    返回 (agent_cmd, env, error)；error 非空时调用方直接 return。
    """
    env = os.environ.copy()
    if api_format == 'openai':                                                                  
        env['PI_BASE_API_KEY'] = api_key                                                          
        env['PI_BASE_URL'] = base_url                                                             
        env['PI_BASE_MODEL_ID'] = model                            
        env['PI_BASE_REASONING'] = "1"                  
        env['PI_BASE_CONTEXT'] = "200000"                                                         
        env['PI_BASE_MAX_TOKENS'] = "200000"  

        if resume:
            # agent_cmd = (
            #     f"pi --continue -p \"接着上次继续\" -o stream-json "
            #     f"-m {shlex.quote(model)} --yolo --include-partial-messages true"
            # )
            # ★ 恢复路径必须重申语言守则：原始 prompt 的中文要求已沉到会话上下文
            #   深处（几十轮工具调用之后），模型对"接着上次继续"的响应很容易回落
            #   到英文思考/正文。每次恢复都把守则顶到最末（最高权重位置）。
            agent_cmd = (
                f"pi --continue -p \"接着上次继续。"
                f"【语言要求（最高优先级）】所有输出全程使用简体中文，"
                f"包括思考过程与正文；禁止英文句子或英文段落；"
                f"代码/命令/路径/寄存器名保持英文原样。\" --mode json "
                f"--provider cli-url --model {shlex.quote(model)}"
            )
        elif use_prompt_file:
            # agent_cmd = (
            #     f"pi -p \"$(cat /app/.prompt.txt)\" -o stream-json "
            #     f"-m {shlex.quote(model)} --yolo --include-partial-messages true"
            # )
            agent_cmd = (                                                                         
                f"pi -p \"$(cat /app/.prompt.txt)\" --mode json "                                 
                f"--provider cli-url --model {shlex.quote(model)}" 
            ) 
        else:
            escaped_content = content.replace("'", "'\"'\"'")
            # agent_cmd = (
            #     f"pi -p '{escaped_content}' -o stream-json "
            #     f"-m {model} --yolo --include-partial-messages true"
            # )
            agent_cmd = (                                                                         
                f"pi -p '{escaped_content}' --mode json "                                 
                f"--provider cli-url --model {shlex.quote(model)}"
            ) 
    elif api_format == 'cursor':
        env['CURSOR_API_KEY'] = api_key
        if resume:
            # ★ 同 pi 恢复路径：--continue 不带 prompt，原始中文守则已沉入上下文深处，
            #   通过 -p 重申语言要求（cursor 协议 --continue 与 -p 可组合）
            agent_cmd = (
                f"agent --continue -p \"接着上次继续。全程使用简体中文输出，"
                f"代码/命令/路径/寄存器名保持英文原样。\" "
                f"--output-format stream-json "
                f"--model {shlex.quote(model)} --yolo --stream-partial-output true"
            )
        elif use_prompt_file:
            agent_cmd = (
                f"agent -p \"$(cat /app/.prompt.txt)\" --output-format stream-json "
                f"--model {shlex.quote(model)} --yolo --stream-partial-output true"
            )
        else:
            escaped_content = content.replace("'", "'\"'\"'")
            agent_cmd = (
                f"agent -p '{escaped_content}' --output-format stream-json "
                f"--model {model} --yolo --stream-partial-output true"
            )
    else:
        LOGGER.error(f"Unknown API format: {api_format}")
        return None, None, {"code": -1, "msg": "Unknown API format."}
    return agent_cmd, env, None


def _api_env_args(api_format, api_key, base_url):
    """构造 docker run 的 -e KEY=VALUE 列表（用显式值，避免依赖父进程 environ）。"""
    if api_format == 'openai':
        return ["-e", f"OPENAI_API_KEY={api_key}", "-e", f"OPENAI_BASE_URL={base_url}"]
    return ["-e", f"CURSOR_API_KEY={api_key}"]


def _pi_base_env_args(api_key, base_url, model):
    """构造 docker run 的 -e PI_BASE_* 列表（openai 路径专用，注入 pi CLI 所需的 6 项配置）。

    这 6 项之前只在宿主子进程 env 中设置（_build_agent_cmd_and_env），
    不会自动跨过 docker run 边界进到容器里。容器内 pi / agent CLI 启动时读不到它们，
    会回落到默认值或报错。这里把它们也通过 -e 显式注入容器，保持与 _build_agent_cmd_and_env 一致。
    """
    return [
        "-e", f"PI_BASE_API_KEY={api_key}",
        "-e", f"PI_BASE_URL={base_url}",
        "-e", f"PI_BASE_MODEL_ID={model}",
        "-e", "PI_BASE_REASONING=1",
        "-e", "PI_BASE_CONTEXT=200000",
        "-e", "PI_BASE_MAX_TOKENS=200000",
    ]


def _url_provider_mount_args():
    """★ 旧镜像兼容：把宿主机的 url-provider.ts 只读挂进容器 extensions 目录。

    背景：openai 路径所有 agent 命令都带 `--provider cli-url`，该 provider
    由镜像内 /root/.pi/agent/extensions/url-provider.ts 读 PI_BASE_URL 后注册
    （构建来源 assets/ai-agent/thirdapp/pipi.tar.gz）。旧版/外部构建的
    codemig-agent-base 镜像缺这个文件，pi 启动即报 `Unknown provider "cli-url"`
    退出，流内只剩 "Agent 异常中断或输出格式不符合预期"。

    做法：解析宿主机 server/assets/ai-agent/<arch>/pipi/url-provider.ts，
    找到则以只读 bind mount 盖到容器内同路径——旧镜像立刻可用；新镜像
    内容相同无副作用。命名卷挂载 /root/.pi 时本挂载更具体（文件级），
    extensions 文件仍生效。

    找不到返回 []（只记日志不阻断主流程）——此时若镜像内已烘焙 extension
    仍可正常工作。
    """
    if not _AGENT_ASSETS_ROOT:
        return []
    host_arch = platform.machine().lower()
    candidates = ['x86'] if host_arch in ('x86_64', 'amd64') else ['arm']
    for fallback in ('x86', 'arm'):
        if fallback not in candidates:
            candidates.append(fallback)
    for arch in candidates:
        src = os.path.join(
            _AGENT_ASSETS_ROOT, arch, 'pipi', 'url-provider.ts',
        )
        if os.path.isfile(src):
            return [
                "-v", f"{src}:/root/.pi/agent/extensions/url-provider.ts:ro",
            ]

    LOGGER.warning(
        "[url-provider] 未找到宿主机 url-provider.ts"
        f"（{_AGENT_ASSETS_ROOT}/<arch>/pipi/ 缺失）。若镜像内也未烘焙该 "
        "extension，pi 将报 Unknown provider \"cli-url\"。"
    )
    return []


def _proxy_env_args(https_proxy, http_proxy, no_proxy):
    """构造 docker run 的 -e https_proxy / -e http_proxy / -e no_proxy（显式值）。"""
    return [
        "-e", f"https_proxy={https_proxy}",
        "-e", f"http_proxy={http_proxy}",
        "-e", f"no_proxy={no_proxy}",
    ]


def _build_chown_tail(prefix):
    """容器内以 root 运行 agent（避免 Permission denied），结束后 chown /app 给宿主机用户。

    返回 (chown_env, shell_cmd)；在 Windows 等无 os.getuid 的环境下退化为不带 chown。
    """
    try:
        host_uid, host_gid = os.getuid(), os.getgid()
        chown_env = ["-e", f"HOST_UID={host_uid}", "-e", f"HOST_GID={host_gid}"]
        shell_cmd = f"{prefix}; chown -R ${{HOST_UID}}:${{HOST_GID}} /app"
    except AttributeError:
        chown_env = []
        shell_cmd = prefix
    return chown_env, shell_cmd


def _assemble_docker_run_cmd(
    request_uuid,
    file_path,
    api_format,
    api_key,
    base_url,
    model,
    https_proxy,
    http_proxy,
    no_proxy,
    shell_cmd,
    extra_mounts=None,
):
    """组装 docker run 命令数组（统一格式：-e 一律 KEY=VALUE 显式传值）。

    Args:
        request_uuid: 容器名后缀。
        file_path: 宿主机工程路径，挂到容器内 /app。
        api_format: 'openai' / 'cursor'。
        api_key / base_url: 用于 -e 显式传值。
        model: 模型名，openai 路径会通过 -e PI_BASE_MODEL_ID 注入容器。
        https_proxy / http_proxy / no_proxy: 代理三项，用于 -e 显式传值。
        shell_cmd: 容器内 sh -c 执行的命令。
        extra_mounts: 可选，列表如 ["-v", "<named_volume>:/root/.pi"]，默认 None=不挂额外卷。
    """
    chown_env, shell_cmd_with_chown = _build_chown_tail(shell_cmd)
    return [
        "docker", "run", "--rm", "--network", "host",
        "--name", f"docker_{request_uuid}",
        "-v", f"{file_path}:/app",
        *(extra_mounts or []),
        *_api_env_args(api_format, api_key, base_url),
        *(_pi_base_env_args(api_key, base_url, model) if api_format == 'openai' else []),
        *(_url_provider_mount_args() if api_format == 'openai' else []),
        *chown_env,
        *_proxy_env_args(https_proxy, http_proxy, no_proxy),
        "-e", "PYTHONUNBUFFERED=1",
        "codemig-agent-base:1.0.0", "sh", "-c",
        shell_cmd_with_chown,
    ]


def _spawn_docker_agent(command, env, cmd_list, err_prefix="命令执行失败"):
    """统一的 cmd_list 回填 + subprocess.Popen 启动 + 异常日志。

    返回 Popen；异常时向上抛 Exception(err_prefix + ...)。
    """
    cmd_list.clear()
    cmd_list.extend(command)
    LOGGER.info(f"Command: {sanitize_cmd_for_log(cmd_list)}", exc_info=True)
    try:
        return subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1,
            env=env,
        )
    except subprocess.CalledProcessError as e:
        LOGGER.error(f"{err_prefix}: {e}", exc_info=True)
        raise Exception(f"{err_prefix}: {e.stderr}")
    except Exception as e:
        LOGGER.error(f"执行Agent命令时发生错误: {e}", exc_info=True)
        raise


def create_agent_process(content: str, file_path: str, agent_config,
                         request_uuid, cmd_list, api_format) -> subprocess.Popen:
    """
    创建Agent进程用于流式处理

    Args:
        content: 命令内容
        file_path: 文件路径
        agent_config: 模型配置
        request_uuid: docker启动的uuid
        cmd_list: 命令列表（输出）
        api_format: 使用的api格式(openai或cursor)
    Returns:
        subprocess.Popen对象用于流式处理
    """
    creds, err = _resolve_agent_credentials(agent_config)
    if err:
        return err

    proxy = _load_proxy_settings()
    agent_cmd, env, err = _build_agent_cmd_and_env(
        api_format, creds["api_key"], creds["base_url"], creds["model"],
        content=content, use_prompt_file=False,
    )
    if err:
        return err

    chown_env, shell_cmd = _build_chown_tail(agent_cmd)

    command = [
        "docker", "run", "--rm", "--network", "host",  # --rm可以在容器运行完成后，自动释放资源
        "--name", f"docker_{request_uuid}",  # --name指定容器唯一名称
        "-v", f"{file_path}:/app",  # -v将本地工程文件映射到docker内部
        *_api_env_args(api_format, creds["api_key"], creds["base_url"]),
        *(_pi_base_env_args(creds["api_key"], creds["base_url"], creds["model"]) if api_format == 'openai' else []),
        *(_url_provider_mount_args() if api_format == 'openai' else []),
        *chown_env,
        *_proxy_env_args(proxy["https_proxy"], proxy["http_proxy"], proxy["no_proxy"]),
        "-e", "PYTHONUNBUFFERED=1",  # 强制不缓冲，非常重要
        "codemig-agent-base:1.0.0", "sh", "-c",  # 镜像名称固定为codemig-agent-base
        shell_cmd,
    ]
    return _spawn_docker_agent(command, env, cmd_list)


def create_ai_response(content: str, think_mode: str, file_path: str,
                       file_name: str, agent_config, request_uuid,
                       user_name: str, dir_id: int, suggestion: str,
                       file_id=None, start_time=None, api_format=None):
    """
    创建AI响应

    Args:
        content: 请求内容
        think_mode: 思考模式 (agent, normal, reasoning)
        file_path: 文件路径
        file_name: 文件名
        agent_config: AI模型的配置参数
        request_uuid: AI响应任务的启动uuid
        user_name: 用户名
        dir_id: 目录ID
        suggestion: 建议信息
        file_id: 文件ID
        start_time: 开始时间

    Returns:
        Flask Response对象
    """
    if not think_mode:
        suggestion = ERROR_MESSAGES["think_mode_not_set"]
        return create_response(
            to_line(AiDataStatus.BACKEND_ERROR, suggestion))

    model = agent_config.get("model", think_mode) if agent_config else think_mode
    
    if think_mode == "agent":
        return _handle_agent_mode(content, file_path, file_name, agent_config,
                                  request_uuid, user_name, dir_id, suggestion,
                                  file_id, model, api_format, start_time)
    elif think_mode == "normal":
        # 与 reasoning 同款：优先用用户在页面配置的 api_key/base_url/model，
        # 未配置（agent_model 为空或 BASE_MODEL）时按原逻辑走内置端点
        custom_model = agent_config.get("model") if agent_config else None
        if custom_model == "BASE_MODEL":
            custom_model = None
        db_model = custom_model if custom_model else NORMAL_MODEL
        create_ai_info_to_database(user_name, dir_id, file_id, request_uuid, file_path, db_model, '')
        custom_api_key = agent_config.get("api_key") if agent_config and custom_model else None
        custom_base_url = agent_config.get("base_url") if agent_config and custom_model else None
        return _handle_normal_mode(content, suggestion, user_name,
                                   dir_id, request_uuid, start_time,
                                   model=custom_model, api_key=custom_api_key,
                                   base_url=custom_base_url)
    elif think_mode == "reasoning":
        custom_model = agent_config.get("model") if agent_config else None
        # BASE_MODEL 表示使用建议模式默认模型，不传自定义 api_key
        if custom_model == "BASE_MODEL":
            custom_model = None
        db_model = custom_model if custom_model else REASONING_MODEL
        create_ai_info_to_database(user_name, dir_id, file_id, request_uuid, file_path, db_model, '')
        custom_api_key = agent_config.get("api_key") if agent_config and custom_model else None
        custom_base_url = agent_config.get("base_url") if agent_config and custom_model else None
        return _handle_reasoning_mode(content, suggestion, user_name,
                                      dir_id, request_uuid, start_time,
                                      model=custom_model, api_key=custom_api_key,
                                      base_url=custom_base_url)
    else:
        suggestion = ERROR_MESSAGES["unknown_think_mode"]
        return create_response(
            to_line(AiDataStatus.BACKEND_ERROR, suggestion))


def _handle_agent_mode(content: str, file_path: str, file_name: str, agent_config, 
                       request_uuid, user_name: str, dir_id: int, suggestion,
                       file_id=None, model=None, api_format=None, start_time=None):
    """处理Agent模式"""
    LOGGER.info(f"Think mode is agent, file_path: {file_path}, file_name: {file_name}")

    # 校验 agent_config 有效性，避免无效配置导致后续进程处理拿到非进程对象
    if not agent_config or not isinstance(agent_config, dict) or not agent_config.get("api_key"):
        LOGGER.error(f"Agent 模式缺少可用的 API Key 配置 (model={model})")
        suggestion = agent_config.get("msg") if isinstance(agent_config, dict) else "未找到可用的 API Key 配置"
        return create_response(to_line(AiDataStatus.BACKEND_ERROR, suggestion or "未找到可用的 API Key 配置"))

    # 在执行创建 Agent 前，检查并保存 git 状态
    if user_name and dir_id:
        # ★ v5.0.0-DEDUP：单文件 AI 建议路径没有前端 _preBoundaryCommit 锚点；
        # 改用 force_commit_marker 强制 commit（force=True）。无论 working tree
        # dirty 与否都留 marker，避免 clean 时丢 anchor。
        force_commit_marker(
            user_name, dir_id,
            reason='agent-start',
            src='codemig-agent', stage='start', type='marker',
        )
    try:
        cmd_list = []
        process = create_agent_process(content, file_path, agent_config, request_uuid, cmd_list, api_format)
        cmd = " ".join(cmd_list) if cmd_list else ""
        create_ai_info_to_database(user_name, dir_id, file_id, request_uuid, file_path, model, cmd)
        _key_prefix = (agent_config.get("api_key") or "")[:3] if agent_config else ""
        return Response(generate_agent_response(
            process, user_name, dir_id, file_id, request_uuid, start_time,
            agent_model=model, key_prefix=_key_prefix
        ), mimetype='application/json')
    except FileNotFoundError as e:
        save_intermediate_state_on_failure(user_name, dir_id, reason='intermediate-error')
        LOGGER.error(f"Working directory not found: {e}")
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        if request_uuid is not None:
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(to_line(AiDataStatus.BACKEND_ERROR, suggestion), mimetype='application/json')
    except Exception as e:
        save_intermediate_state_on_failure(user_name, dir_id, reason='intermediate-error')
        LOGGER.error(f"Agent mode error: {e}")
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        if request_uuid is not None:
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(to_line(AiDataStatus.BACKEND_ERROR, suggestion), mimetype='application/json')


def _handle_normal_mode(content: str, suggestion, user_name=None, dir_id=None,
                        request_uuid=None, start_time=None, model=None, api_key=None,
                        base_url=None):
    """处理普通模式"""
    LOGGER.info("Think mode is normal")
    if model and api_key:
        # 使用前端指定的模型和api_key（与 reasoning 模式一致）
        LOGGER.info(f"Using custom model: {model} with provided api_key")
        data = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": content,
            }],
            "temperature": 0.6,
            "max_tokens": 15_000,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
            # 绕过部分网关对默认 python-requests UA 的限流(1305)，详见 ai_key_utils.DEFAULT_AI_HTTP_UA
            "User-Agent": DEFAULT_AI_HTTP_UA,
        }
        # 已不内置默认端点：用户配置的 base_url 是唯一推理地址
        if not base_url:
            return create_response(to_line(
                AiDataStatus.BACKEND_ERROR,
                "未配置推理服务地址(Base URL)，请先在「API Key 管理」中配置 API Key"))
        url = base_url
        _key_prefix = api_key[:3]
        return _make_ai_request_and_stream(data, model_name=None, suggestion=suggestion,
                                           user_name=user_name, dir_id=dir_id,
                                           request_uuid=request_uuid, start_time=start_time,
                                           headers=headers, url=url,
                                           key_info_model=model, key_info_prefix=_key_prefix)
    model_name = NORMAL_MODEL
    data = create_think_mode_data(content, model_name)
    return _make_ai_request_and_stream(data, model_name, suggestion, user_name,
                                       dir_id, request_uuid, start_time)


def _handle_reasoning_mode(content: str, suggestion, user_name=None, dir_id=None,
                           request_uuid=None, start_time=None, model=None, api_key=None,
                           base_url=None):
    """处理建议模式"""
    LOGGER.info("Think mode is reasoning")
    if model and api_key:
        # 使用前端指定的模型和api_key
        LOGGER.info(f"Using custom model: {model} with provided api_key")
        data = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": content,
            }],
            "temperature": 0.6,
            "max_tokens": 15_000,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
            # 绕过部分网关对默认 python-requests UA 的限流(1305)，详见 ai_key_utils.DEFAULT_AI_HTTP_UA
            "User-Agent": DEFAULT_AI_HTTP_UA,
        }
        # 已不内置默认端点：用户配置的 base_url 是唯一推理地址
        if not base_url:
            return create_response(to_line(
                AiDataStatus.BACKEND_ERROR,
                "未配置推理服务地址(Base URL)，请先在「API Key 管理」中配置 API Key"))
        url = base_url
        _key_prefix = api_key[:3]
        return _make_ai_request_and_stream(data, model_name=None, suggestion=suggestion,
                                           user_name=user_name, dir_id=dir_id,
                                           request_uuid=request_uuid, start_time=start_time,
                                           headers=headers, url=url,
                                           key_info_model=model, key_info_prefix=_key_prefix)
    else:
        model_name = REASONING_MODEL
        data = create_data(content, model_name)
        return _make_ai_request_and_stream(data, model_name, suggestion, user_name,
                                           dir_id, request_uuid, start_time)


def _make_ai_request_and_stream(data: dict, model_name: str, suggestion: str,
                                user_name=None, dir_id=None,
                                request_uuid=None, start_time=None,
                                headers=None, url=None,
                                key_info_model=None, key_info_prefix=None):
    """发起AI请求并返回流式响应"""
    if request_uuid is None or len(request_uuid) < 1:
        LOGGER.error("There is no request uuid")
        suggestion = "There is no request uuid"
        return Response(to_line(AiDataStatus.NO_REQUEST_UUID, suggestion), mimetype='application/json')
    try:
        # 已不内置默认端点：调用方未传 url（normal/reasoning 未配置用户 Key 的
        # 旧兜底路径）时直接报错引导配置，不再查内置端点表
        if not url:
            return create_response(to_line(
                AiDataStatus.BACKEND_ERROR,
                "未配置推理服务地址(Base URL)，请先在「API Key 管理」中配置 API Key"))
        request_url = url
        # 兼容用户仅配置 base_url（缺少 /chat/completions 后缀）的情况，
        if not request_url.rstrip('/').endswith('/chat/completions'):
            request_url = request_url.rstrip('/') + '/chat/completions'
        request_headers = headers if headers else create_headers()
        response = requests.post(
            request_url,
            headers=request_headers,
            json=data,
            stream=True,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        stream = generate_streaming_response(
            response, user_name, dir_id, request_uuid, start_time
        )
        if key_info_model is not None:
            key_info = json.dumps({"model": key_info_model, "key_prefix": key_info_prefix or ''},
                                  ensure_ascii=False)
            def _stream_with_key_info():
                yield to_line(AiDataStatus.AGENT_KEY_INFO, key_info)
                yield from stream
            return Response(_stream_with_key_info(), mimetype='application/json')
        return Response(stream, mimetype='application/json')
    except requests.Timeout as timeout:
        LOGGER.error(f"AI request timed out: {timeout}")
        suggestion = str(timeout)
        # 异常情况下，立即保存到数据库
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(to_line(AiDataStatus.TIMEOUT, suggestion), mimetype='application/json')
    except requests.RequestException as e:
        LOGGER.error(f"AI request failed: {e}")
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(to_line(AiDataStatus.BACKEND_ERROR, suggestion), mimetype='application/json')


def query_ai_suggestion(content, think_mode, file_path, file_name, agent_config, 
                        request_uuid, user_name, dir_id, suggestion,
                        file_id=None, start_time=None, api_format=None):
    try:
        return create_ai_response(content, think_mode, file_path, file_name, agent_config,
                                  request_uuid, user_name, dir_id, suggestion,
                                  file_id=file_id, start_time=start_time, api_format=api_format)
    except requests.Timeout as timeout:
        suggestion = str(timeout)
        # 异常情况下，立即保存到数据库
        if file_id is not None and request_uuid is not None:
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)

        return create_response(to_line(AiDataStatus.TIMEOUT, suggestion))
    except Exception as e:
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        if file_id is not None and request_uuid is not None:
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user_name, dir_id, suggestion, request_uuid, run_time)
        return create_response(to_line(AiDataStatus.BACKEND_ERROR, suggestion))


def query_query_ai_suggestion_data(user_id, task_id, dir_id, file_id,
                                   change_id, dependence_id):
    LOGGER.info(f"Querying the ai suggestion data for user: {user_id}, "
                f"task_id: {task_id}, "
                f"dir_id: {dir_id}, "
                f"file_id: {file_id}, "
                f"change_id: {change_id}."
                f"dependence_id: {dependence_id}")
    if dependence_id:
        return FileDependenceSuggestion.get_ai_suggestion_data(
            user_id, task_id, dir_id, file_id, change_id, dependence_id
        )
    else:
        # 从主数据库获取任务名称
        task_name = CodemigTasks.get_task_name(user_id, task_id)
        if not task_name:
            return None

        # 获取 user_name
        user = UserManager.query_by_id(user_id)
        if not user:
            LOGGER.error(f"User not found: user_id={user_id}")
            return None
        user_name = user.user_name

        # 从用户特定数据库查询文件建议信息
        user_db_path = get_database_path(user_name, dir_id)
        if not user_db_path.exists():
            LOGGER.error(f"Database {user_db_path} not found")
            return None

        conn = None
        try:
            conn = get_conn(user_db_path)
            cursor = conn.cursor()
            cursor.execute(SELECT_CHANGE_SQL, (file_id, change_id))
            result = cursor.fetchone()
            if not result:
                return None
            return (task_name, *result)
        except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
            LOGGER.error("Database operation failed: %s", err)
            raise
        finally:
            if conn:
                conn.close()


def query_file_info(user_id, task_id, dir_id, file_id, dependence_id):
    """
    查询文件信息（不需要change_id，用于选中行号的情况）

    Returns:
        tuple: (task_name, file_path) 或 None
    """
    LOGGER.info(f"Querying file info for user: {user_id}, "
                f"task_id: {task_id}, "
                f"dir_id: {dir_id}, "
                f"file_id: {file_id}, "
                f"dependence_id: {dependence_id}")
    if dependence_id:
        return FileDependence.get_task_name_and_file_path(
            user_id, task_id, dir_id, file_id, dependence_id
        )
    else:
        # 从主数据库获取任务名称
        task_name = CodemigTasks.get_task_name(user_id, task_id)
        if not task_name:
            return None

        # 获取 user_name
        user = UserManager.query_by_id(user_id)
        if not user:
            LOGGER.error(f"User not found: user_id={user_id}")
            return None
        user_name = user.user_name

        # 从用户特定数据库查询文件信息
        user_db_path = get_database_path(user_name, dir_id)
        if not user_db_path.exists():
            LOGGER.error(f"Database {user_db_path} not found")
            return None

        conn = None
        try:
            conn = get_conn(user_db_path)
            cursor = conn.cursor()
            cursor.execute(SELECT_FILE_SQL, (dir_id, file_id))
            result = cursor.fetchone()
            if result:
                return (task_name, *result)
            return None
        except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
            LOGGER.error("Database operation failed: %s", err)
            raise
        finally:
            if conn:
                conn.close()


def query_ai_suggestion_data_for_agent(user_id, task_id, dir_id, file_id,
                                       dependence_id):
    LOGGER.info(f"Querying the ai suggestion data for user: {user_id}, "
                f"task_id: {task_id}, "
                f"dir_id: {dir_id}, "
                f"file_id: {file_id}, "
                f"dependence_id: {dependence_id}")
    if dependence_id:
        return FileDependenceSuggestion.get_all_ai_suggestion_data(
            user_id, task_id, dir_id, file_id, dependence_id
        )
    else:
        # 从主数据库获取任务名称
        task_name = CodemigTasks.get_task_name(user_id, task_id)
        if not task_name:
            return None

        # 获取 user_name
        user = UserManager.query_by_id(user_id)
        if not user:
            LOGGER.error(f"User not found: user_id={user_id}")
            return None
        user_name = user.user_name

        # 从用户特定数据库查询所有文件建议信息
        user_db_path = get_database_path(user_name, dir_id)
        if not user_db_path.exists():
            LOGGER.error(f"Database {user_db_path} not found")
            return None

        conn = None
        try:
            conn = get_conn(user_db_path)
            cursor = conn.cursor()
            SELECT_AGENT_CHANGE_SQL = SELECT_CHANGE_SQL.replace("AND Suggestion.change_id = ?", "")
            cursor.execute(SELECT_AGENT_CHANGE_SQL, (file_id,))
            result = cursor.fetchall()
            processed_result = [(task_name, *row) for row in result]
            return processed_result
        except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
            LOGGER.error("Database operation failed: %s", err)
            raise
        finally:
            if conn:
                conn.close()


prompt_templates = {
    "program_code_prompt": """
    [针对{solver_name}] 
    [运行环境为Linux，对其进行修改以适配自研 RISC-V 芯片]
    [要求：
    1. 先展示修改后的代码
    2. 逐行解析生成代码关键逻辑
    3. 说明与 x86 架构的差异及注意事项]
    [输出格式：
    ## 代码 
    {code}
    ## 分析 
    评估该参考建议，若正确基于此建议修改代码：{suggestion}]
    """,
    "common_prompt": """
    [运行平台：{platform}]
    [{requirement}]
    [检查并修改其中关键规则以适配自研 RISC-V 芯片的编译环境]
    [要求：
    1. 先展示修改后的完整代码
    2. 逐行解释生成代码关键逻辑
    3. 指出平台相关依赖项，说明与 x86 架构的差异及注意事项]
    [输出格式：
    ## 代码 
    {code}
    ## 分析 
    基于此建议修改代码：{suggestion}]
    """,

    "macro_prompt": """
    [Input]
    - {code}
    - 建议参考：{suggestion}（来自数据库的评估结果）  
    [运行平台：{platform}]
    [{requirement}]
    [输入为x86架构代码，检查并修改其中关键规则以适配自研 RISC-V 芯片的编译环境]
    [要求：
    1. 先展示原代码修改后的完整代码
    2. 逐行解释关键逻辑
    3. 指出平台相关依赖项]
    [Output Format]  
    ## 宏定义修改 
    - 修改后的代码
    ## 详细讲解  
    1. 逐行解释关键逻辑
    2. 指出平台相关依赖项
    """,

    "buildin_prompt": """
    [Input]
    - {code}
    - 建议参考：{suggestion}（来自数据库的评估结果）  
    [运行平台：{platform}]
    [{requirement}]
    [输入为x86架构代码，解释相关代码功能]
    [要求：
    1. 逐行解释关键逻辑
    2. 指出平台相关依赖项]
    [Output Format]  
    ## 详细讲解  
    1. 逐行解释关键逻辑
    2. 指出平台相关依赖项
    """,
    "agent_prompt": """
    你是一个经验丰富的软件工程师，精通x86、arm、risc-v架构的汇编、intrinsic编程，以及编译工程技术。

    【语言要求（最高优先级，先于一切任务指令）】
    你的所有输出必须全程使用简体中文，包括思考过程（thinking）与正文；禁止输出英文句子或英文段落，禁止 Let me... / I need to... 式英文思考；代码 / 命令 / 文件路径 / 寄存器名保持英文原样。派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」。
    以下任务指令均以此语言要求为前提，回答时不要省略中间过程。


    参考文件：{file_path}
    修改建议：{pending_changes}
    运行平台：{platform}
    
    你的任务是：
    1.参考已有的arm/x86文件以及修改建议，使用uttest技能创建riscv单元测试文件；
    2.然后使用migrate技能将arm/x86汇编迁移到riscv平台；
    3.使用asmrepair技能检查riscv和arm/x86的代码逻辑区别，并修复riscv代码。


    执行完成后，删除单元测试文件以及中间文件，仅保留最终的riscv代码文件，但禁止删除原有文件。
    禁止与用户交互：不要向用户提问、不要要求用户确认、不要要求用户提供额外信息。
    """,

    "agent_file_prompt": """
    你是一个RISC-V架构专家，下面文件可能缺少RISC-V架构的实现。请基于其他架构下的原始文件，补齐缺失的文件内容。

    【语言要求（最高优先级，先于一切任务指令）】
    你的所有输出必须全程使用简体中文，包括思考过程（thinking）与正文；禁止输出英文句子或英文段落，禁止 Let me... / I need to... 式英文思考；代码 / 命令 / 文件路径 / 寄存器名保持英文原样。派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」。
    以下任务指令均以此语言要求为前提，回答时不要省略中间过程。

    如果判断文件没有缺失，则输出"AI判断文件没有缺失"。
    可能缺失的文件路径：{file_name}。
    该文件在其他架构下的参考实现：{existing_file_paths_str}

    你的任务是：
    1.参考其他架构下的实现，使用uttest技能创建riscv单元测试文件；
    2.然后使用migrate技能将arm/x86汇编迁移到riscv平台，补齐缺失的riscv文件；
    3.使用asmrepair技能检查riscv和arm/x86的代码逻辑区别，并修复riscv代码。

    执行完成后，删除单元测试文件以及中间文件，仅保留最终的riscv代码文件，但禁止删除原有文件。
    禁止与用户交互：不要向用户提问、不要要求用户确认、不要要求用户提供额外信息。
    """,

    "agent_common_prompt": """
    你是一个经验丰富的软件工程师，精通x86、arm、risc-v架构的系统编程、构建系统及编译工程技术。

    【语言要求（最高优先级，先于一切任务指令）】
    你的所有输出必须全程使用简体中文，包括思考过程（thinking）与正文；禁止输出英文句子或英文段落，禁止 Let me... / I need to... 式英文思考；代码 / 命令 / 文件路径 / 寄存器名保持英文原样。派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」。
    以下任务指令均以此语言要求为前提，回答时不要省略中间过程。


    参考文件：{file_path}
    修改建议：{pending_changes}
    运行平台：{platform}

    你的任务是：
    1.仔细阅读每条修改建议中的【类型提示】和【原始代码】，理解其架构依赖；
    2.直接修改源代码文件，将架构相关的部分适配为 RISC-V 平台；
    3.修改完成后，确认所有变更均已正确应用。

    注意事项：
    - 对于宏定义，确保增加 RISC-V 对应的条件编译分支；
    - 对于 Makefile / 构建脚本，确保编译选项和链接参数兼容 RISC-V；
    - 对于 intrinsic / builtin，替换为 RISC-V RVV intrinsic 或等效实现；
    - 对于编程语言代码，检查条件编译、平台 API 调用等架构依赖。

    禁止与用户交互：不要向用户提问、不要要求用户确认、不要要求用户提供额外信息。
    """
}

change_template = """
<change>
    <line_num_range>
    {line_num_range}
    </line_num_range>
    <suggestion>
    {suggestion}
    </suggestion>
</change>
"""


def create_asm_question_content(code, suggestion):
    return "\n".join([suggestion + "然后，请讲解一下生成的代码。", "".join(code)])


def create_inline_asm_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, is_selected_lines = query_data
    with open(file_path, "r") as file:
        code = file.readlines()[start_lineno - 1:end_lineno]
        return create_asm_question_content(code, suggestion)


def create_asm_file_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, is_selected_lines = query_data
    with open(file_path, "r") as file:
        if (is_selected_lines == True):
            code = file.readlines()[start_lineno - 1:end_lineno]
        else:
            code = file.readlines()
        return create_asm_question_content(code, suggestion)


def create_program_language_content(query_data, solver_name):
    file_path, _, start_lineno, end_lineno, suggestion, _ = query_data
    with open(file_path, "r") as file:
        code_lines = file.readlines()[start_lineno - 1:end_lineno]
        code = "".join(code_lines)  # 将代码列表转换为字符串
        template = prompt_templates["program_code_prompt"].format(
            solver_name=solver_name,
            code=code,
            suggestion=suggestion)
        return template


def create_makefile_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, is_selected_lines = query_data
    with open(file_path, "r") as file:
        code = file.readlines()
        makefile_advice = "输入为完整makefile构建文件，检查其中x86架构相关且不能运行在riscv架构的代码"
        if len(code) > 100 or is_selected_lines == True:
            code = code[start_lineno - 1:end_lineno]
            makefile_advice = "输入代码位于makefile构建文件，关联规则块及依赖项, 检查其中x86架构相关内容且不能运行在riscv架构的内容"
        template = prompt_templates["common_prompt"].format(
            requirement=makefile_advice,
            platform="Linux",
            code=code,
            suggestion=suggestion)
        return template


def create_intrinsics_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, is_selected_lines = query_data

    with open(file_path, "r") as file:
        if (is_selected_lines == True):
            code = file.readlines()[start_lineno - 1:end_lineno]
        else:
            code = file.readlines()
    template = prompt_templates["common_prompt"].format(
        requirement="输入代码为内联汇编代码，包含x86 向量头文件引用语句及相关函数调用代码块",
        platform="Linux",
        code=code,
        suggestion=suggestion)
    return template


def create_macros_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, _ = query_data
    with open(file_path, "r") as file:
        code = file.readlines()[start_lineno - 1:end_lineno]
    template = prompt_templates["macro_prompt"].format(
        requirement="输入为X86相关宏定义相关代码，建议增加 RISC-V 对应的宏定义块，确保宏展开后代码逻辑在两种架构下均能正常运行",
        platform="Linux",
        code=code,
        suggestion=suggestion)
    return template


def create_buildin_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, _ = query_data
    with open(file_path, "r") as file:
        code = file.readlines()[start_lineno - 1:end_lineno]
    template = prompt_templates["buildin_prompt"].format(
        requirement="输入为内置函数相关代码，检查代码的架构依赖",
        platform="Linux",
        code=code,
        suggestion=suggestion)
    return template


def create_build_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, _ = query_data
    with open(file_path, "r") as file:
        code = file.readlines()[start_lineno - 1:end_lineno]
    template = prompt_templates["common_prompt"].format(
        requirement="输入为构建脚本相关代码，检查代码的架构依赖",
        platform="Linux",
        code=code,
        suggestion=suggestion)
    return template


def create_agent_content(query_data, file):
    """
    根据是否包含汇编生成 Agent 内容，只分两类：

    - 包含 ASM（INLINE_ASM / ASM_FILE）：使用 agent_prompt，
      走 migrate → asmrepair 技能流水线。
    - 不包含 ASM：使用 agent_common_prompt，
      引导 Agent 直接修改代码。

    Args:
        query_data: 列表，每个元素为 (task_name, file_path, suggestion_type,
                    start_line, end_line, suggestion) 的 6 元组。
                    suggestion_type 为 SolverType 枚举值（int），选中行号时为 None。
        file: 文件名（用于 prompt 中的参考文件字段）

    Returns:
        str: 拼接好的 Agent prompt 内容
    """

    # 汇编类型：走 agent_prompt（migrate/asmrepair 技能流水线）
    _ASM_TYPES = {SolverType.INLINE_ASM.value, SolverType.ASM_FILE.value}

    # 非汇编类型的领域提示
    _TYPE_HINTS = {
        SolverType.MAKEFILE.value:
            "该变更位于 Makefile 构建文件中，需检查架构相关的编译选项、"
            "链接参数、条件编译宏，并修改为 RISC-V 兼容配置。",
        SolverType.INTRINSICS.value:
            "该变更包含 x86 intrinsic 头文件引用及向量内联函数调用代码块，"
            "需将其替换为 RISC-V RVV intrinsic 或等效的纯 C 实现。",
        SolverType.BUILTIN.value:
            "该变更涉及编译器内置函数（builtin），需检查其架构依赖并替换为 "
            "RISC-V 平台支持的等价实现。",
        SolverType.MACROS.value:
            "该变更为宏定义相关代码，需增加 RISC-V 对应的宏定义块，"
            "确保宏展开后代码逻辑在 x86/ARM/RISC-V 三种架构下均能正常运行。",
        SolverType.BUILD_SCRIPT.value:
            "该变更位于构建脚本中，需检查架构相关的构建逻辑，"
            "修改为兼容 RISC-V 平台的构建配置。",
        SolverType.RUST_SOURCE_CODE.value:
            "该变更为 Rust 源代码，需检查其中架构相关的 unsafe 块、"
            "cfg 条件编译、内联汇编等，适配 RISC-V 平台。",
        SolverType.RUST_TOML_CODE.value:
            "该变更为 Rust Cargo.toml 配置文件，需检查架构相关的依赖项"
            "和特性标志，适配 RISC-V 平台。",
    }

    def _fallback_hint(type_val):
        """通用编程语言的默认提示"""
        if type_val is not None and type_val in {6, 7, 8, 9}:
            solver_type = SolverType(type_val)
            return (f"该变更为{solver_type.description}，"
                    f"需检查架构相关的条件编译、平台 API 调用等，适配 RISC-V 平台。")
        return "需检查代码中的架构依赖并适配 RISC-V 平台。"

    # ---- 第一轮：判断是否包含汇编 ----
    has_asm = any(data[2] in _ASM_TYPES for data in query_data)

    # ---- 收集变更内容 ----
    changes = ""

    for idx, data in enumerate(query_data):
        task_name, file_path, suggestion_type, start_lineno, end_lineno, suggestion = data

        code_snippet = ""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                code_snippet = "".join(lines[start_lineno - 1:end_lineno])
        except (OSError, IndexError):
            code_snippet = "（无法读取源代码片段）"

        if suggestion_type in _ASM_TYPES:
            # 汇编类：保持原有格式
            changes += change_template.format(
                line_num_range=f"{start_lineno}到{end_lineno}",
                suggestion=suggestion,
            )
        else:
            # 非汇编类：附带类型提示 + 原始代码
            type_hint = _TYPE_HINTS.get(suggestion_type) or _fallback_hint(suggestion_type)

            changes += change_template.format(
                line_num_range=f"{start_lineno}到{end_lineno}",
                suggestion=(
                    f"【类型提示】{type_hint}\n"
                    f"【原始代码】\n{code_snippet}\n"
                    f"【修改建议】{suggestion}"
                ),
            )

    # ---- 根据是否包含汇编选择 prompt ----
    if has_asm:
        result = prompt_templates["agent_prompt"].format(
            file_path=file,
            pending_changes=changes,
            platform="Linux")
    else:

        result = prompt_templates["agent_common_prompt"].format(
            file_path=file,
            pending_changes=changes,
            platform="Linux")

    return result

def truncate_path_to_subdir_of_dir_id(file_path, dir_id):
    """
    截取路径到指定ID的子目录
    如果路径中不包含该ID，则返回原路径的目录部分和文件名
    """
    path_parts = os.path.normpath(file_path).split(os.sep)
    dir_id_str = str(dir_id)

    try:
        dir_id_index = path_parts.index(dir_id_str)
        # 找到ID后，返回ID所在目录及其父目录，以及后续路径
        return os.sep.join(path_parts[:dir_id_index + 2]) + os.sep, os.sep.join(
            path_parts[dir_id_index + 2:])
    except ValueError:
        # 如果路径中不包含该ID，则使用原路径的目录部分和文件名
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        # 确保目录路径以分隔符结尾
        if dir_path and not dir_path.endswith(os.sep):
            dir_path += os.sep
        return dir_path, file_name


def create_rust_content(query_data):
    file_path, _, start_lineno, end_lineno, suggestion, _ = query_data
    with open(file_path, "r") as file:
        code = file.readlines()[start_lineno - 1:end_lineno]
    template = prompt_templates["common_prompt"].format(
        requirement="输入为Rust源代码相关代码，检查代码的架构依赖",
        platform="Linux",
        code=code,
        suggestion=suggestion)
    return template


def cancel_ai_suggestion_by_id(user_name, dir_id, request_uuid):
    """
    取消 / 中断 AI 任务。
    仅清理容器 + 命名卷 + 数据库 finished 标记，
    **不再自动 restore_workspace**（V7）：
      - 工作区保留 agent 半成品
      - generate_project_agent_response / ②③ skill handler 的 finally 块
        会通过 V6.1 中间态 commit 把半成品收进 git 历史
      - 用户可在历史下拉框选中间态前一个 commit 手动回退
    """

    container_name = f"docker_{request_uuid}"

    # rm -f 发 SIGKILL 会连带杀掉容器命令尾部的 chown 收尾语句，
    # 先借将死容器把 /app 属主刷回宿主机用户，再强杀（best-effort，
    # 容器已死则静默跳过，不影响下方 rm 的原有语义）。
    _chown_app_before_kill(container_name)

    # 强制删除容器 + 关联的匿名 volume (-v)
    command = ["docker", "rm", "-f", "-v", container_name]
    try:
        LOGGER.info(f"Executing: {' '.join(command)}")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            timeout=30  # 防止 hang 住
        )

        if result.returncode == 0:
            LOGGER.info(f"Container '{container_name}' deleted successfully.")
            return {"code": 0, "msg": "Container deleted", "output": result.stdout.strip()}
        else:
            # 容器不存在也算成功
            if "No such container" in result.stderr:
                LOGGER.warning(f"Container '{container_name}' not found (already deleted).")
                return {"code": 0, "msg": "Container not found (already deleted)", "output": ""}
            else:
                LOGGER.error(f"Failed to delete container: {result.stderr}")
                raise Exception(f"docker rm failed: {result.stderr.strip()}")

    except subprocess.TimeoutExpired:
        LOGGER.error(f"Timeout while deleting container '{container_name}'")
        raise Exception("Docker command timed out")
    except Exception as e:
        LOGGER.error(f"Unexpected error during container deletion: {e}", exc_info=True)
        raise


def _validate_user(user_id, user_name):
    """验证用户身份"""
    user = UserManager.query_by_id(user_id)
    if not user or user_name != user.user_name:
        return None
    return user


def _get_user_id_and_role(user_name):
    """通过 user_name 查找 user_id 和是否为 admin"""
    try:
        user = UserManager.query(user_name=user_name, nopw=True)
        if user:
            return user.user_id, (user.role == 'admin')
    except Exception as e:  # noqa
        LOGGER.warning(f"Failed to query user info for '{user_name}': {e}")
    return None, False


def _extract_request_params(parameters, request):
    """提取请求参数"""
    user_id = request.user_id
    is_admin = False
    user = UserManager.query_by_id(user_id)
    if user and user.role == 'admin':
        is_admin = True
    agent_model = parameters.get('agent_model')
    agent_config = ''
    if agent_model and agent_model != 'BASE_MODEL':
        agent_config = get_agent_config_from_db(agent_model, user_id=user_id, is_admin=is_admin)
    return {
        'user_id': user_id,
        'user_name': parameters.get("user_name"),
        'task_id': parameters.get("task_id"),
        'dir_id': parameters.get("dir_id"),
        'file_id': parameters.get("file_id"),
        'change_id': parameters.get("change_id"),
        'dependence_id': parameters.get("dependence_id"),
        'think_mode': parameters.get('think_mode', 'normal'),
        'selected_start_line': parameters.get("selected_start_line"),
        'selected_end_line': parameters.get("selected_end_line"),
        'user': UserManager.query_by_id(request.user_id),
        'agent_model': agent_model,
        'agent_config': agent_config,
        'api_format': parameters.get('api_format'),
        'request_uuid': parameters.get('request_uuid')
    }


def _build_log_info(task_name, file_id, change_id, selected_start_line, selected_end_line,
                    dependence_id, think_mode):
    """构建日志信息"""
    log_parts = [f'task:{task_name}', f'file_id:{file_id}']
    if change_id:
        log_parts.append(f'change_id:{change_id}')
    if selected_start_line and selected_end_line:
        log_parts.append(f'selected_lines:{selected_start_line}-{selected_end_line}')
    if dependence_id:
        log_parts.append(f'dependence_id:{dependence_id}')
    log_parts.append(f'think_mode:{think_mode}')
    return '; '.join(log_parts)


def query_ai_suggestion_for_change(parameters, request):
    """
    查询AI建议的主函数

    核心逻辑：
    1. 参数验证和提取
    2. 统一获取代码内容和修改建议（指定代码行和建议行使用相同逻辑）
    3. 生成AI查询内容
    4. 记录日志并执行AI查询

    Args:
        parameters: 请求参数
        request: Flask请求对象

    Returns:
        Response: AI查询结果
    """
    suggestion = ''
    start_time = time.time()
    
    # 1. 提取参数
    params = _extract_request_params(parameters, request)

    # 2. 验证用户
    user = _validate_user(params['user_id'], params['user_name'])
    if not user:
        return {"code": -1, "msg": "Unknown user."}

    try:
        # 3. 获取代码和建议数据
        code_data = _get_code_and_suggestion(
            params['user_id'], params['task_id'], params['dir_id'], params['file_id'],
            params['change_id'], params['dependence_id'],
            params['selected_start_line'], params['selected_end_line'],
            params['think_mode']
        )
        if not code_data:
            suggestion = "无法获取代码内容或建议信息"
            return create_response(
                to_line(AiDataStatus.UNKNOWN_ERROR, suggestion))

        # 4. 生成AI查询内容
        content, file_dir, file_name, task_name = _create_content(
            code_data, params['think_mode'], params['dir_id']
        )
        if not content:
            suggestion = "无法生成AI查询内容"
            return create_response(to_line(AiDataStatus.UNKNOWN_ERROR, suggestion))

        # 6. 执行AI查询
        return query_ai_suggestion(
            content, params['think_mode'], file_dir, file_name, params['agent_config'],
            params['request_uuid'], user.user_name, params['dir_id'], suggestion,
            file_id=params['file_id'], start_time=start_time, api_format=params['api_format']
        )

    except Exception as e:
        LOGGER.error(f"Querying the ai suggestion data failed: {e}", exc_info=True)
        suggestion = str(e)
        # 异常情况下，立即保存到数据库
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(params['user_name'], params['dir_id'], suggestion, params['request_uuid'], run_time)
        return create_response(to_line(AiDataStatus.BACKEND_ERROR, suggestion))


def _get_solver_type_from_file(file_path, file_name):
    """
    从文件中解析solver类型

    Args:
        file_path: 完整文件路径
        file_name: 文件名

    Returns:
        tuple: (solver_type值, solver_type对象)，如果未找到则返回默认值
    """
    from plugin.codemig.main.codemig_processor import CodemigProcessor
    from plugin.codemig.solver.solvers_mapping import SOLVERS_MAPPING

    file_solvers_result = CodemigProcessor.process_file(file_path)
    LOGGER.debug(f"解析文件类型: file_path={file_path}, file_name={file_name}")

    for solver, _ in file_solvers_result.items():
        if solver.matches_file(file_name):
            solver_class_name = solver.__name__
            if solver_class_name in SOLVERS_MAPPING:
                solver_type = SOLVERS_MAPPING[solver_class_name]
                solver_type_value = solver_type.value
                LOGGER.debug(f"找到匹配的solver: {solver_class_name}, type: {solver_type_value}")
                return solver_type_value, solver_type

    LOGGER.warning(f"未找到匹配的solver，使用默认类型: file_path={file_path}, file_name={file_name}")
    default_type = SolverType.JAVA_SOURCE_CODE
    return default_type.value, default_type


def _parse_file_path_info(file_path, dir_id):
    """
    解析文件路径信息

    Args:
        file_path: 完整文件路径
        dir_id: 目录ID

    Returns:
        tuple: (file_dir, file_name, full_file_path)
    """
    file_dir, file_name = truncate_path_to_subdir_of_dir_id(file_path, dir_id)
    full_file_path = os.path.join(file_dir, file_name)
    return file_dir, file_name, full_file_path


def _parse_file_path_tuple(file_path_tuple):
    """
    解析truncate_path_to_subdir_of_file_id的返回值

    Args:
        file_path_tuple: truncate_path_to_subdir_of_file_id的返回值（可能是tuple或str）

    Returns:
        tuple: (file_dir, file_name)
    """
    if isinstance(file_path_tuple, tuple):
        return file_path_tuple
    else:
        file_dir = file_path_tuple
        file_name = os.path.basename(file_path_tuple)
        return file_dir, file_name


def _build_query_data_dict(file_path, solver_type_value, start_line, end_line, suggestion,
                           is_selected_lines=False):
    """
    构建query_data字典（统一格式）

    Args:
        file_path: 文件路径
        solver_type_value: solver类型值
        start_line: 起始行号
        end_line: 结束行号
        suggestion: 建议内容
        is_selected_lines: 是否为选中代码行

    Returns:
        dict: query_data字典，包含所有必要信息
    """
    return {
        'file_path': file_path,
        'type': solver_type_value,
        'start_line': start_line,
        'end_line': end_line,
        'suggestion': suggestion,
        'is_selected_lines': is_selected_lines
    }


def _build_suggestion_result(task_name, file_path, file_dir, file_name, query_data, change_id):
    """
    构建建议结果字典

    Args:
        task_name: 任务名称
        file_path: 完整文件路径
        file_dir: 文件目录
        file_name: 文件名
        query_data: 查询数据（字典或列表）
        change_id: 变更ID

    Returns:
        dict: 结果字典
    """
    return {
        'type': 'suggestion',
        'task_name': task_name,
        'file_path': file_path,
        'file_dir': file_dir,
        'file_name': file_name,
        'query_data': query_data,
        'change_id': change_id
    }


def _get_selected_lines_data(user_id, task_id, dir_id, file_id, dependence_id,
                             selected_start_line, selected_end_line):
    """
    获取选中代码行的数据（从文件系统读取）

    Args:
        user_id: 用户ID
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        dependence_id: 依赖ID
        selected_start_line: 起始行号
        selected_end_line: 结束行号

    Returns:
        dict: 包含文件信息和query_data的字典，失败返回None
    """

    file_info = query_file_info(user_id, task_id, dir_id, file_id, dependence_id)
    if not file_info:
        LOGGER.error(f"文件不存在: file_id={file_id}, dir_id={dir_id}")
        return None

    task_name, file_path = file_info
    file_dir, file_name, full_file_path = _parse_file_path_info(file_path, dir_id)

    # 通过文件解析solver类型
    solver_type_value, _ = _get_solver_type_from_file(file_path, file_name)

    query_data = _build_query_data_dict(
        full_file_path, solver_type_value, selected_start_line, selected_end_line,
        "针对用户选定的代码片段（疑似不兼容 RISC-V 架构），请先从编程语言特性、核心函数调用、逻辑架构设计进行兼容性拆解分析，再完成代码重构与修改，确保最终代码完全适配 RISC-V 架构的指令集与运行环境。",
        is_selected_lines=True
    )

    return {
        'task_name': task_name,
        'file_path': file_path,
        'file_dir': file_dir,
        'file_name': file_name,
        'query_data': query_data
    }


def _get_suggestion_data(user_id, task_id, dir_id, file_id, change_id, dependence_id):
    """
    获取建议行的数据（从数据库查询）

    Args:
        user_id: 用户ID
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        change_id: 变更ID
        dependence_id: 依赖ID

    Returns:
        dict: 包含文件信息和query_data的字典，失败返回None
    """
    query_result = query_query_ai_suggestion_data(
        user_id, task_id, dir_id, file_id, change_id, dependence_id
    )
    if not query_result:
        LOGGER.error(f"未找到对应的建议信息: change_id={change_id}, file_id={file_id}")
        return None

    task_name, *query_data_list = query_result
    file_path_tuple = truncate_path_to_subdir_of_dir_id(query_data_list[0], dir_id)
    file_dir, file_name = _parse_file_path_tuple(file_path_tuple)

    # 转换为统一字典格式
    query_data = _build_query_data_dict(
        query_data_list[0], query_data_list[1], query_data_list[2],
        query_data_list[3], query_data_list[4], is_selected_lines=False
    )

    return {
        'task_name': task_name,
        'file_path': query_data_list[0],
        'file_dir': file_dir,
        'file_name': file_name,
        'query_data': query_data,
        'change_id': change_id
    }


def _convert_selected_data_to_agent_format(selected_data):
    """
    将选中数据转换为Agent模式要求的6元组格式

    Args:
        selected_data: 选中数据字典

    Returns:
        list: Agent模式query_data列表
    """
    query_data_dict = selected_data.get('query_data')
    return [
        (
            selected_data.get('task_name'),
            query_data_dict['file_path'],
            None,  # 占位符，原格式中的第三个参数
            query_data_dict['start_line'],
            query_data_dict['end_line'],
            query_data_dict['suggestion']
        )
    ]


def _build_agent_mode_result(selected_data, query_data_list, file_path, dir_id):
    """
    构建Agent模式的结果字典

    Args:
        selected_data: 选中数据（可选）
        query_data_list: 查询数据列表（可选）
        file_path: 文件路径
        dir_id: 目录ID

    Returns:
        dict: Agent模式结果字典
    """
    if selected_data:
        # 使用选中数据
        return {
            'type': 'agent',
            'task_name': selected_data.get('task_name'),
            'file_path': selected_data.get('file_path'),
            'file_dir': selected_data.get('file_dir'),
            'file_name': selected_data.get('file_name'),
            'query_data': _convert_selected_data_to_agent_format(selected_data),
            'change_id': None
        }
    else:
        # 使用查询数据列表
        file_path_tuple = truncate_path_to_subdir_of_dir_id(file_path, dir_id)
        file_dir, file_name = _parse_file_path_tuple(file_path_tuple)
        return {
            'type': 'agent',
            'task_name': None,
            'file_path': file_path,
            'file_dir': file_dir,
            'file_name': file_name,
            'query_data': query_data_list,
            'change_id': None
        }


def _handle_agent_mode_data(user_id, task_id, dir_id, file_id, dependence_id,
                            selected_data, is_valid_selected, change_id):
    """
    处理Agent模式的逻辑

    Args:
        user_id: 用户ID
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        dependence_id: 依赖ID
        selected_data: 选中数据（可选）
        is_valid_selected: 是否有效选中
        change_id: 变更ID（可选；前端选中某条已有建议时会带上，仍走 Agent 流水线）

    Returns:
        dict: Agent模式结果字典，失败返回None
    """
    if is_valid_selected and selected_data:
        return _build_agent_mode_result(selected_data, None, None, dir_id)

    if change_id:
        data = _get_suggestion_data(
            user_id, task_id, dir_id, file_id, change_id, dependence_id
        )
        if not data:
            LOGGER.error(f"变更数据查询失败：change_id={change_id}, file_id={file_id}")
            return None
        qd = data['query_data']
        query_data_list = [(
            data['task_name'],
            qd['file_path'],
            None,
            qd['start_line'],
            qd['end_line'],
            qd['suggestion'],
        )]
        return _build_agent_mode_result(None, query_data_list, data['file_path'], dir_id)

    # 查询AI建议列表
    query_data_list = query_ai_suggestion_data_for_agent(
        user_id, task_id, dir_id, file_id, dependence_id
    )

    if not query_data_list:
        LOGGER.error(f"没有需要修改的代码: file_id={file_id}")
        return None

    file_path = query_data_list[0][1]
    return _build_agent_mode_result(None, query_data_list, file_path, dir_id)


def _handle_suggestion_mode_data(user_id, task_id, dir_id, file_id, change_id, dependence_id,
                                 selected_data, is_valid_selected):
    """
    处理建议模式的逻辑（包括选中代码行和建议行）

    Args:
        user_id: 用户ID
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        change_id: 变更ID
        dependence_id: 依赖ID
        selected_data: 选中数据（可选）
        is_valid_selected: 是否有效选中

    Returns:
        dict: 建议模式结果字典，失败返回None
    """
    if is_valid_selected and selected_data:
        return _build_suggestion_result(
            selected_data['task_name'], selected_data['file_path'],
            selected_data['file_dir'], selected_data['file_name'],
            selected_data['query_data'], None
        )

    if change_id:
        data = _get_suggestion_data(
            user_id, task_id, dir_id, file_id, change_id, dependence_id
        )
        if not data:
            LOGGER.error(f"变更数据查询失败：change_id={change_id}, file_id={file_id}")
            return None
        return _build_suggestion_result(
            data['task_name'], data['file_path'], data['file_dir'],
            data['file_name'], data['query_data'], data.get('change_id')
        )

    return None


def _get_code_and_suggestion(user_id, task_id, dir_id, file_id, change_id, dependence_id,
                             selected_start_line, selected_end_line, think_mode):
    """
    统一获取代码内容和修改建议

    核心思想：
    - 优先处理选中行逻辑，提前生成统一的选中数据（selected_data）
    - think_mode 为 agent 时一律走 Agent 数据与提示词；带 change_id 时只拉取该条建议写入 agent 的 query_data
    - 非 agent 时按 change_id / 选中行走建议模式

    Args:
        user_id: 用户ID
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        change_id: 变更ID（可选）
        dependence_id: 依赖ID（可选）
        selected_start_line: 起始行号（可选，前端传递）
        selected_end_line: 结束行号（可选，前端传递）
        think_mode: 思考模式

    Returns:
        dict: 包含代码和建议信息的字典，失败返回None
    """
    # 第一步：处理选中行逻辑，提前生成选中数据
    is_valid_selected = (selected_start_line is not None and
                         selected_end_line is not None and
                         not change_id)

    selected_data = None
    if is_valid_selected:
        selected_data = _get_selected_lines_data(
            user_id, task_id, dir_id, file_id, dependence_id,
            selected_start_line, selected_end_line
        )
        if not selected_data:
            LOGGER.error(f"获取选中行数据失败: file_id={file_id}")
            return None

    # 第二步：根据模式分支处理
    if think_mode == "agent":
        return _handle_agent_mode_data(
            user_id, task_id, dir_id, file_id, dependence_id,
            selected_data, is_valid_selected, change_id
        )

    # 建议模式（包括选中代码行和建议行）
    result = _handle_suggestion_mode_data(
        user_id, task_id, dir_id, file_id, change_id, dependence_id,
        selected_data, is_valid_selected
    )

    if result:
        return result

    # 参数不合法
    LOGGER.error(
        "参数错误：请提供有效的 change_id 或 选中行号（selected_start_line/selected_end_line）参数")
    return None


def _convert_query_data_to_list(query_data_dict):
    """将query_data字典转换为列表格式（向后兼容）"""
    return [
        query_data_dict['file_path'],
        query_data_dict['type'],
        query_data_dict['start_line'],
        query_data_dict['end_line'],
        query_data_dict['suggestion'],
        query_data_dict['is_selected_lines']
    ]


def _create_suggestion_content(code_data):
    """
    创建建议内容的AI查询（指定代码行和建议行统一处理）

    Args:
        code_data: 代码数据字典

    Returns:
        tuple: (content, file_dir, file_name, task_name)
    """
    query_data_list = _convert_query_data_to_list(code_data['query_data'])

    content = _create_content_by_solver_type(query_data_list)
    if not content:
        LOGGER.error(f"_create_content_by_solver_type fail，获取的content内容为空!")
        return None, None, None, None

    return content


def _create_content(code_data, think_mode, dir_id):
    """
    根据获取的代码数据生成AI查询内容

    核心思想：
    - Agent模式单独处理
    - 指定代码行和建议行统一处理

    Args:
        code_data: 代码数据字典（由_get_code_and_suggestion返回）
        think_mode: 思考模式
        dir_id: 目录ID（未使用，保留以兼容）

    Returns:
        tuple: (content, file_dir, file_name, task_name)
    """
    if code_data['type'] == 'agent':
        content = create_agent_content(code_data['query_data'], code_data['file_name'])
        return content, code_data['file_dir'], code_data['file_name'], code_data['task_name']

    if code_data['type'] == 'suggestion':
        content = _create_suggestion_content(code_data)
        return content, code_data['file_dir'], code_data['file_name'], code_data['task_name']

    LOGGER.error(f"未知的代码数据类型: {code_data.get('type')}")
    return None, None, None, None


def _create_content_by_solver_type(query_data):
    """
    根据求解器类型创建AI查询内容

    Args:
        query_data: 查询数据列表，格式：[file_path, type, start_line_number, end_line_number, suggestion]

    Returns:
        str: AI查询内容，如果不支持则返回None
    """
    solver_type = SolverType(query_data[1])
    if solver_type == SolverType.INLINE_ASM:
        return create_inline_asm_content(query_data)
    elif solver_type == SolverType.ASM_FILE:
        return create_asm_file_content(query_data)
    elif solver_type == SolverType.MAKEFILE:
        return create_makefile_content(query_data)
    elif solver_type == SolverType.INTRINSICS:
        return create_intrinsics_content(query_data)
    elif solver_type == SolverType.BUILTIN:
        return create_buildin_content(query_data)
    elif solver_type == SolverType.MACROS:
        return create_macros_content(query_data)
    elif solver_type == SolverType.BUILD_SCRIPT:
        return create_build_content(query_data)
    elif solver_type == SolverType.RUST_SOURCE_CODE:
        return create_rust_content(query_data)
    elif solver_type == SolverType.RUST_TOML_CODE:
        return create_rust_content(query_data)
    elif solver_type.value in {6, 7, 8, 9}:
        solver_name = solver_type.description
        return create_program_language_content(query_data, solver_name)
    else:
        return None

def query_reopen_ai_suggestion(user_name, dir_id, file_id, ai_id):
    return query_ai_suggestion_from_database(user_name, dir_id, file_id, ai_id)

def set_ai_score(user_name, dir_id, file_id, ai_id, score):
    return set_ai_score_to_database(user_name, dir_id, file_id, ai_id, score)

def get_ai_score(user_name, dir_id, file_id, uuid):
    return query_ai_score_from_database(user_name, dir_id, file_id, uuid)


# ──────────────────────────────────────────────────────────────
# 项目级一键迁移
# ──────────────────────────────────────────────────────────────

# 查询全部有建议且未忽略的文件列表（复用 query_processor 中的 SQL 模式）
SELECT_ALL_FILES_WITH_SUGGESTIONS_SQL = """
    SELECT DISTINCT File.file_id AS file_id,
           File.file_path AS file_path
    FROM codemig_task_directory_file AS File
         JOIN codemig_task_directory_file_suggestion AS Suggestion
              ON File.file_id = Suggestion.file_id
    WHERE File.has_removed = 0
      AND File.type = 0
      AND File.file_source = 'changed'
      AND Suggestion.ignored = 0
    ORDER BY File.file_path ASC
"""

# 查询某个文件的全部建议（仅扫描器产出，不含 manual 选中段）
SELECT_ALL_SUGGESTIONS_FOR_FILE_SQL = """
    SELECT start_line_number,
           end_line_number,
           type,
           suggestion,
           is_manual
    FROM codemig_task_directory_file_suggestion
    WHERE file_id = ?
      AND ignored = 0
      AND is_manual = 0
    ORDER BY start_line_number ASC
"""

projectmigrate_skill_content = """---
name: projectmigrate
description: 将整个项目从x86/arm架构迁移到riscv架构平台，基于scan_result.json清单逐文件迁移
language: zh-CN
output_language: 简体中文（zh-CN）
tools:
  - riscv-doc-mcp
  - read_file
  - write_file
  - read_many_files
  - run_shell_command
---

# 项目级一键迁移技能

你是一个经验丰富的软件工程师，精通 x86、ARM、RISC-V 架构的汇编、intrinsic 编程，以及编译工程技术。

【语言要求（最高优先级，先于一切任务指令）】
你的所有输出必须全程使用简体中文，包括思考过程（thinking）与正文；禁止输出英文句子或英文段落，禁止 Let me... / I need to... 式英文思考；代码 / 命令 / 文件路径 / 寄存器名保持英文原样。派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」，子任务不继承本对话的语言约定。
以下任务指令均以此语言要求为前提，回答时不要省略中间过程。
项目根目录：/app
运行平台：{platform}

## 第一步：加载迁移清单（必须首先执行）

使用 read_file 工具读取文件 /app/scan_result.json，该文件包含项目中所有需要迁移到 RISC-V 平台的文件清单及对应的修改建议。
文件格式为 JSON，顶层字段说明：
- "suggestion_class_count"：迁移建议条目总数
- "suggestion_class"：迁移建议条目列表，每个条目包含：
  - "file_path"：文件在容器内的绝对路径（以 /app/ 开头）
  - "file_name"：文件名
  - "solver_type"：问题类型的数字编码（0=Makefile, 1=内联函数, 2=内置函数, 3=宏定义, 4=内联汇编, 5=汇编文件, 6-9=各语言源代码, 10=构建脚本, 11-13=配置文件）
  - "solver_description"：问题类型的中文描述
  - "start_line" / "end_line"：建议涉及的代码行号范围（1-based，闭区间）
  - "migration_suggestion"：具体的迁移建议文本

- "missing_class_count"：缺失的架构文件/目录条目总数（流水线维护，agent 不要改）
- "missing_class"：缺失的架构文件/目录条目列表（**顶层独立数组**，与 suggestion_class 同级、不互相包含；与 everything project_scan.md L66-76 1:1 对齐），每个条目 7 字段：
  - "class_type"：固定为 `"missing_class"`
  - "missing_path"：缺失的 riscv64 文件/目录路径（**容器内 /app/... 路径**，与 suggestion_class 的 file_path 路径空间一致）
  - "is_file"：bool（True=文件缺失，False=目录缺失；保守置 True）
  - "existing_arch_paths"：list[str]，容器内其他架构（x86/ARM 等）的兄弟文件/目录路径；为空 `[]` 表示 DB 中无兄弟架构可参考
  - "migration_suggestion"：建议文本（含参考路径或"暂无，需重写"）
  - "status"：三态 `TODO`/`START`/`DONE`
  - "marking"：DONE 时必填

## 迁移点状态字段规范（速查）

> **权威源在 `scan_result.json` 中，不在源码注释里**。每个条目（`suggestion_class[]` 与顶层 `missing_class[]`）携带两个结构化字段维护进度；不要向源码写 `// [MIGRATE-*]` 注释。

| 字段 | 类型 | 取值 | 说明 |
| ---- | ---- | ---- | ---- |
| `status` | string | `TODO` / `START` / `DONE`（三态**互斥**，同一时刻只能有一个） | 迁移状态 |
| `marking` | string | 备注文本（异常说明 / 性能影响 / TODO(后续) 等） | `status=DONE` 时**必填** |

`status` 三态含义：

- `TODO`（流水线默认值，阶段一扫描后即为此状态）：未处理
- `START`（agent 进入该条目后立即改写）：开始迁移
- `DONE`（agent 完成阶段 D 验证后改写）：迁移完成，必须伴随非空 `marking`

`marking` 常见 6 种内容（按场景选其一）：

- **无异常**：`无异常，性能与 x86/ARM 实现持平（或给出相对比例）`
- **语义差异**：`语义差异：<具体点>，已通过测试规避`
- **性能下降**：`性能低于原实现 N%，原因：<…>，建议后续人工性能调优`
- **需要后续修复**：`TODO(后续)：<具体项>`
- **误报**：`误报：<已核验的理由（已有 __riscv 分支 / 死代码 / 语义等价宏 / 扫描器误识别）>`
- **trivial 宏适配**：`trivial 宏适配：<具体宏/分支>（改动仅预处理指令行，免验证）`

**何时写 `DONE` 与 `marking`**：

- **误报条目**（必要性分析确认）：不改任何代码，直接 `DONE`，marking 写 `误报：<已核验的理由>`。
- **汇编类条目**（满足分流判定任一，含可向量化热点）：必须完成 **阶段 D（验证）通过** 后才能从 `START` 改 `DONE`，并填 `marking`。
- **非汇编 trivial 条目**（改动仅预处理指令行）：免阶段 D 验证，直接 `DONE`，marking 记 `trivial 宏适配：<具体宏/分支>`（可编译性由阶段三工程级编译兜底）。
- **非汇编类条目（非 trivial）**：完成 **阶段 D（交叉编译 + qemu 验证）通过** 后即可从 `START` 改 `DONE`。
- **missing_class[] 条目**（架构文件缺失）：agent 生成完整 RISC-V 文件并通过阶段 D 验证后改 `DONE`，marking 写"无异常：新增 riscv 实现"或"TODO(后续)：<后续工作>"。

**更新方式**：直接编辑 `scan_result.json`（用 `edit_file` / `write_file` 工具改对应条目）；写回时必须保持 schema 与缩进一致；不要改 `target` / `suggestion_class_count` / `missing_class_count` 这三个顶层字段——它们由流水线维护。

## 第二步：浏览项目结构

使用 glob 或 list_directory 工具浏览项目整体结构，理解项目架构和文件间的依赖关系。

## 第三步：逐条目迁移（必要性分析 → 分流 → 迁移闭环）

按照依赖顺序（先迁移底层库，再迁移上层调用），对 suggestion_class 中的每个条目，**先做必要性分析，再按以下标准分流**，进入对应链路。

### 前置必要性分析（每个条目动手前必须，防止误报空转）

修改任何代码前，先判断条目是否真的需要迁移。确认为扫描误报的，**不改任何代码**，直接把该条目 `status` 改 `DONE`，`marking` 写 `误报：<已核验的理由>`，跳过全部迁移与验证流程。判断要点（与 everything-riscv 阶段二 2.2 对齐）：

- 条目指向的代码是否已通过条件编译天然支持 RISC-V（如已有 `__riscv` 分支——x86/ARM 分支在 RV 构建下不参与编译）；
- 是否为死代码、注释掉的代码或不可达平台分支；
- 是否为跨平台兼容宏（如字节序、对齐处理）在 RV 上语义本就等价；
- 是否为扫描器对普通内置函数或非架构代码的误识别。

**疑义从重**：无法确定是否误报 → 按需要迁移处理，走正常分流。

### 分流判定（满足任一即为汇编类，走完整闭环）

1. solver_type 为 4（内联汇编）或 5（汇编文件）；
2. solver_type 为 1（内联函数），且源码含 x86 intrinsic（_mm_*/_mm256_*/_mm512_*）或 ARM NEON intrinsic（vld1q_*/vmlaq_*/vst1q_*）；
3. solver_type 为 2（内置函数），且源码含 __builtin_ia32_* 或 __builtin_neon_*；
4. 文件后缀为 .S / .s / .asm；
5. 源码含 __asm__ / __asm / asm volatile 且迁移点落在该段内；
6. **纯 C 可向量化热点**（AutoVecCandidate）：solver_type 为 6-9（源代码类）且命中静态启发——数据并行 for 循环（数组索引步进、无跨迭代依赖迹象）、memcpy/查表/字节处理密集、循环体无函数调用且分支较少。此类条目**不满足前 5 条也必须走完整闭环**：x86/ARM 上靠编译器自动向量化（SSE/AVX/NEON）获得性能的纯 C 循环，迁移后没有任何机制保证 RV 侧仍然向量化（GCC 对 RVV 的自动向量化成本模型保守，VLEN 编译期未知时经常拒绝），**禁止按轻量流程只做宏替换后放行**。

不满足以上任一条件的，为非汇编类（走轻量流程，进入前先做 trivial 判定，见下）。

**进度自检**：scan_result.json 已加载且可读；每个待迁移条目已完成必要性分析（误报条目已带依据置 DONE）；其余条目已按分流判定标记为汇编类 / 可向量化热点 / 非汇编类。

### 汇编类：完整闭环（B→C→D→E）

#### 阶段 B：迁移
1. 使用 uttest 技能，为原始 x86/arm 实现和即将编写的 RISC-V 实现创建同一套可对比输出的单元测试（测试先行，无测试不得宣称迁移完成）；
2. 使用 migrate 技能将 arm/x86 汇编迁移到 riscv 平台；
3. 使用 asmrepair 技能检查 riscv 和 arm/x86 的代码逻辑区别并修复 riscv 代码。

**可向量化热点（AutoVecCandidate）专用路径**——先试编译器自动向量化，失败再显式 RVV 化（与 everything-riscv 阶段二 AutoVecCandidate 子闭环对齐）：
1. 先尝试**编译器自动向量化**：`-O3` + 消除别名担忧（`__restrict`、`__builtin_assume_aligned`、`#pragma GCC ivdep`），用 `-fopt-info-vec` 检查向量化报告；
2. 向量化成功（报告无 missed/bad-value）→ 直接进入阶段 D 验证，marking 记录 `自动向量化成功（-fopt-info-vec 确认）`；
3. 向量化失败或被拒 → **改写为显式 RVV intrinsic**（同"汇编代码"路径走 migrate 技能），marking 记录 autovec 被拒原因（如 `GCC 拒绝向量化：<missed 原因>，已改写显式 RVV intrinsic`）；
4. **禁止只做宏替换后按"非汇编轻量流程"放行**——被误分流为轻量的数据并行热点必须回到完整闭环。

**进度自检**：单元测试已创建；migrate 技能已产出 RISC-V 实现；asmrepair 已完成逻辑对比修复；AutoVecCandidate 条目有 `-fopt-info-vec` 结论或显式 intrinsic 改写。

#### 阶段 C：知识库查证（贯穿阶段 B，禁止猜测）
迁移过程中遇到以下任一信号，必须使用 riscv-doc-mcp 工具查询后再下结论：
- 指令名（如 vadd.vv / clmul）；
- 扩展名（如 Zba / V / Zvbc）；
- intrinsic（如 __riscv_*）；
- ABI / CSR / 特权字段（如 mstatus）。
查询后必须在迁移说明中保留证据链：记录 MCP 返回的 file_path（文档路径）和 header_path（章节标题）。若返回未包含证据链字段，需让问题更具体（明确指令名/扩展名/SEW/LMUL）后重查。**重试 + 降级**：用更具体的查询条件重试 2 次；2 次仍失败则不阻塞迁移，把当前条目 marking 改为 `TODO(后续)：<指令/扩展名>未在 MCP 找到证据` 并继续下一条目。

#### 阶段 D：验证（阶段 B 每轮改动后主动触发，不等积攒）
1. **交叉编译 RISC-V 实现**：先用 `command -v riscv64-linux-gnu-gcc-14` 探测 RISC-V C 编译器；若不存在再探测 `riscv64-linux-gnu-gcc`（容器只装了不带版本后缀的同名包时常见）；C++ 用 `riscv64-linux-gnu-g++-14` → `riscv64-linux-gnu-g++` 同样回退。**只要探测到，就把探测结果记到 Makefile / 命令行，别在文档里硬编码 `gcc-14` 后缀**。编译参数固定 `-march=rv64gcv_zbb_zbc_zvbc_zvkb_zvksed -mabi=lp64d -static`。
   - **测试程序与产物落地位置（重要）**：所有本轮用到的 main.c / Makefile / run.sh / riscv64_test 都放在 `/app/.migrate_verify/<file_basename>/` 内（即仓库根下，不放 `/tmp`）。容器 `/tmp` 在 `pi --continue` 切换会话时会被清理，下次回来会丢光产物；落在仓库内会被 git 跟踪、跨会话稳定保留。**禁止写入 `/app/test/`**——那是阶段②功能验证的正式产物目录，会被前端文件树扫描展示。
2. 用 `qemu-riscv64 -cpu max <bin>` 执行 RISC-V 实现；
3. 将输出与原始 x86/arm 实现的输出对比（diff 或 checksum）；
4. 若不一致，回流阶段 B 修复 RISC-V 侧，直到输出完全一致；
5. **QEMU 比对阈值**（自主决策，不要问用户）：差异行 ≤ 3 自行修复；差异行 > 3 自行定位语义差异点（参考阶段 C 知识库查证）；**连续 5 轮比对仍不一致**（任意一轮 diff 有差异）**停下来汇报**，列出已尝试的修复路径与候选语义差异点，让用户判断。
6. 一致后该条目验证通过。

**进度自检**：交叉编译通过；qemu-riscv64 执行成功；RISC-V 输出与原始 x86/arm 输出逐字节一致（diff 无差异或 checksum 匹配）。

### 非汇编类：轻量迁移（先判 trivial；trivial 免验证，其余 B→C→D，一般不需要 E）

**第一步：trivial 判定（避免无意义的交叉编译验证开销）**

改动完成后，先判断本条目是否 trivial（与 everything-riscv 阶段二 2.1 轻量流程再细分对齐）：

- **判据（满足任一即 trivial）**：
  1. 迁移动作仅为**架构宏判定/宏分支**改动——`#ifdef __x86_64__`/`__ARM_ARCH` 加 `__riscv` 分支或调整条件编译逻辑，不改任何表达式与函数体；
  2. 仅**头文件包含调整**（增删 `#include`）或仅**类型/编译选项**适配，不引入新逻辑；
- **trivial 硬约束**：改动**仅在预处理指令行**（`#if*`/`#ifdef`/`#else`/`#elif`/`#endif`/`#define`/`#include`）。凡需要改动任何 C/C++ 语句行（表达式、函数体、类型定义、初始化器），一律不算 trivial，走下方普通轻量流程。
- **宏体内嵌架构相关表达式不算 trivial**：宏展开后是 intrinsic/asm 的，按汇编类完整闭环处理。
- **trivial 条目免阶段 D 验证**：不编译、不跑 QEMU、不写测试——改的只是预处理分支选择，静态语义可判定，可编译性由阶段三工程级编译整体兜底。直接置 `DONE`，marking 写 `trivial 宏适配：<具体宏/分支>`。
- **疑义从重**：无法确定改动是否仅预处理级 → 按普通轻量流程走（多花一次局部编译，好过漏验证）。

**第二步：普通轻量迁移（非 trivial 条目）**

1. 使用 read_file 读取文件内容，理解架构依赖；
2. 使用 write_file 修改源代码进行适配：
   - 宏定义：增加 RISC-V 对应的条件编译分支（如 #elif defined(__riscv) && __riscv_xlen == 64）；
   - Makefile / 构建脚本：确保编译选项和链接参数兼容 RISC-V；
   - 编程语言代码：检查条件编译、平台 API 调用、字节序/对齐/类型宽度在 RV64（小端、long=64-bit）下成立；
3. 若涉及 intrinsic / builtin，替换为 RISC-V RVV intrinsic 或等效实现；不确定的指令/扩展按阶段 C 查知识库取证；
4. **交叉编译验证**：用 `command -v riscv64-linux-gnu-gcc-14` 探测 RISC-V 编译器；若容器只装了不带版本后缀的同名包（`riscv64-linux-gnu-gcc`），改用该名。C++ 项目用 `riscv64-linux-gnu-g++-14` → `riscv64-linux-gnu-g++` 同理回退。**编译命令与产物全部落在 `/app/.migrate_verify/<file_basename>/`（仓库内），不要写 `/tmp`**，因为容器 `/tmp` 在 `pi --continue` 切会话时会被清理，跨会话跑测试会丢产；也**不要写 `/app/test/`**（那是阶段②功能验证的正式产物目录）；
5. **功能验证**：`qemu-riscv64 -cpu max <bin>` 执行，行为与原始一致；
6. 通过即完成。

**进度自检**：trivial 条目确认改动行均为预处理指令且已置 DONE（marking 含 trivial 宏适配）；非 trivial 条目代码适配完成、交叉编译通过、qemu-riscv64 执行行为与原始一致；被误分流为轻量的数据并行热点已回到完整闭环。

## 阶段三：工程级编译修复（交叉工具链编译整个工程）

> **本阶段与阶段二的"逐条目迁移"互补**：阶段二保证**单个迁移点**正确，阶段三保证**整个工程**可在 RISC-V 交叉工具链下构建并跑通。everything 强调"阶段二所有条目 DONE 后才进入阶段三"。

### 3.1 准备环境

- RISC-V 交叉工具链与 QEMU user-static 由本镜像已烘焙（`/usr/bin/riscv64-linux-gnu-gcc-14` 等，探测式使用，不要在文本里硬编码后缀）。
- `qemu-riscv64` / `qemu-riscv64-static` 直接可用；用 `qemu-riscv64 -cpu max <bin>` 跑产物。

### 3.2 编译整个工程

1. 在目标工程里用交叉工具链跑完整构建（如 `make` / `cmake --build`），前缀以 `*_TOOLCHAIN_ROOT/bin` 下实际文件为准。
2. **修编译错误**：
   - 缺什么装什么（系统包）。
   - `__x86_64__` / `__ARM_ARCH` 等宏残留未替换的，回阶段二补。
   - 头文件路径、链接库路径、ABI（`lp64d`）等，按工程实际调整。
3. **`-march` 覆盖所用扩展**；常见起点：`-march=rv64gcv_zbb_zbc_zvbc_zvkb_zvksed -mabi=lp64d`，**编译报错时自主追加**扩展（`Zfh`/`Zvfh`/`Zicclsm` 等），不询问。
4. 若工程要求静态链接，遵守之。
5. 若任务固定产物名（如 `riscv64_test`），遵守任务说明。

### 3.3 运行验证

- 用 `qemu-riscv64 -cpu max <bin>` 跑主流程/集成测试，至少确认主程序可启动、无立即崩溃、关键路径输出与 x86/ARM 侧一致。
- 与阶段二条目级 QEMU 验证互补：条目级验证保证**单个迁移点**正确；工程级验证保证**整体**可运行。

**阶段三进度自检**：工程完整构建无错误；RV 可执行程序可在 QEMU 中跑通主流程。

---

## 自主运行原则（零交互硬约束——与 everything SKILL.md L39-98 1:1 对齐）

> **目标**：技能被调用后，尽量不向用户提问，agent 直接自主推进到任务完成。下面的决策**默认由 agent 自行决定**；只有 B 节白名单里列出的 5 类场景才向用户问一次性输入。

### A. 自主默认（agent 直接采用，无需确认）

| # | 决策点 | 默认值 / 默认行为 | 升级触发（覆盖默认） |
| - | ------ | ------------------ | --------------------- |
| 1 | 目标工程根目录 | `/app`（本镜像约定） | 用户 prompt 显式指定则用指定值 |
| 2 | `scan_result.json` 输出路径 | `<目标工程根>/scan_result.json`，已存在则不重扫 | 用户主动说"重新扫描"才覆盖旧文件 |
| 3 | 汇编形式（RVV 汇编 vs RVV intrinsic） | 默认 **RVV 1.0 intrinsic**（可读性、可移植性更好） | 项目强制要求手写汇编或编译器不支持某些 intrinsic 时才用纯汇编 |
| 4 | 单元测试缺失 | **agent 自己补**：从原始 x86/ARM 源码静态推导算法，构造最小测试向量与断言（边界值 + 随机 + checksum）；不要问"测试怎么写" | 无 |
| 5 | `-mcpu`（编译） | `user prompt 显式指定 > 工程 Makefile/CMake 中已声明的 -march/-mcpu > 探测到的目标部署芯片 > sifive-p870（乱序基线，默认兜底）`。**不要用 `generic`/`generic-rv64`** | 无 |
| 6 | `-march` 起点 | `rv64gcv_zbb_zbc_zvbc_zvkb_zvksed`；编译报错时**自主追加**扩展，不询问 | 用户自定义 march 才覆盖 |
| 7 | `marking` 内容 | "无异常" = 测试一致 + 无编译告警；"性能 N%" = 跑 5 次取中位数，相对 x86/ARM 取 ±5%；"语义差异" = QEMU 对比有差异但被测试规避 | 无 |
| 9 | 优化终止 | IPC ≥ Dispatch × 0.7 **且** 连续两轮 Block RThroughput 差距 < 5% **且** 输出 `No resource or data dependency bottlenecks` | 无 |
| 10 | 编译错误处理 | 自主诊断（看错误码）→ 自主修复（装系统包、调 march、追加 include、`-mabi` 切换等）→ 不在中途汇报"修了一个错误要不要继续" | 连续 3 次同类型失败才向用户汇报 |
| 11 | QEMU 对比失败修复 | 差异行 ≤ 3：自主改 RISC-V 侧；> 3：自主定位 + 修复；修复后回到"对比 → 修复"循环直到一致 | 连续 5 轮不一致才向用户汇报 |
| 12 | 知识库查询失败 | 改为更具体的查询条件重试 2 次（补指令名/扩展名/SEW/LMUL）；仍失败 → 降级为参考 [code_migrate.md](referens/code_migrate.md) 默认映射 | 重试都失败再问 |
| 13 | JSON schema 不一致 | 自主修补：缺 `status`/`marking` 字段的条目补默认值 `TODO`/`""`，写回时保留缩进 | 无 |
| 14 | 工具链/QEMU 不存在 | 自主探测（`command -v`）；不要问"要不要装" | 探测失败再问 |
| 16 | 报告时机 | 只在**每个阶段结束时**输出一次结构化摘要（条目数 / 变更文件 / 产物路径 / 阻塞项）；不要逐条目汇报 | 用户要求"详细日志"才细化 |
| 17 | 错误汇报时机 | 真正的不可恢复错误（所有编译器都不支持 / JSON schema 无法修补 / 用户输入来源空）才向用户汇报；可恢复的一律自助修复 | 无 |

### B. 真正可以问用户的时机（白名单）

只有以下 5 类场景**可以**问用户一次，且应给出明确推荐选项：

1. 用户 prompt 完全没指明目标工程，**且** `/app` 目录无任何源码文件（找不到根，根目录探测失败）
2. 阶段二某条目 5 轮 QEMU 对比仍不一致（修复循环超出阈值）
3. 阶段三编译连续 3 个同类错误未能修复
4. 工具链/QEMU 都探测失败（且无离线制品包可装）
5. 用户主动问进度（每阶段结束后查询即可，agent 主动汇报）

### C. 不用问的"看起来该问"（反模式黑名单）

下列问题**永远不要问**，agent 自己决策：

- ❌ "用汇编还是 intrinsic 写 RVV？" → 默认 intrinsic（A #3）
- ❌ "测试怎么写？" → 自己补（A #4）
- ❌ "用什么 `-march`？" → 自己选起点，报错自主升级（A #6）
- ❌ "阶段一已完成，要进入阶段二吗？" → **默认自动进入**，禁止等待确认
- ❌ "要不要重扫？" → 默认不重扫（A #2）
- ❌ "调度模型用哪个 `-mcpu`？" → 自己按优先级选（A #5）
- ❌ "RVV 用什么 LMUL？" → 自己按数据宽度算，参考知识库
- ❌ "找不到 `scan_result.json`，怎么办？" → 自己跑扫描（A #2）
- ❌ "工程里同时有 x86 和 ARM 实现，迁哪个？" → 默认两个都迁，按文件路径一一处理

## 验证与质量纪律（必须遵守）

- 必要性分析先行：每个条目动手前先判误报；误报条目不改代码、不进验证流程，marking 写明可核验依据；
- 测试先行：阶段 B 迁移前，先为原始实现和 RISC-V 实现准备同一套可对比输出的单元测试（trivial 条目除外）；
- 验证主动触发：每完成一个条目的迁移改动，立即执行阶段 D 验证，不要积攒到最后统一验证；不一致时优先修复 RISC-V 侧；
- 证据链留痕：凡使用 riscv-doc-mcp 查询的指令/扩展/intrinsic，必须在迁移说明中记录 file_path 和 header_path，禁止在不查询的情况下凭记忆下指令结论。

执行完成后，删除单元测试文件以及中间文件（含 `/app/.migrate_verify/` 下的本轮验证产物），仅保留最终的 riscv 代码文件，但禁止删除原有文件；禁止删除或改动 `/app/test/` 下的任何内容（那是功能验证阶段的正式产物）。
禁止与用户交互：不要向用户提问、不要要求用户确认、不要要求用户提供额外信息。
"""

# 项目级迁移的触发 prompt：极简指令，由 projectmigrate skill 提供完整工作流
# 强调：
#   1. 必须用中文回答
#   2. 网络访问白名单：默认离线运行，仅当必要且缺失工具链/依赖时才允许走指定 URL 安装
projectmigrate_prompt_template = (
    "【语言要求（最高优先级，先于一切任务指令）】\n"
    "你的所有输出必须全程使用简体中文，包括思考过程（thinking）、迁移分析、进度自检、"
    "错误消息与最终总结。禁止输出英文句子或英文段落，"
    "禁止 Let me... / I need to... 式英文思考；"
    "代码 / 命令 / 文件路径 / 寄存器名保持英文原样。\n"
    "派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」，"
    "子任务不继承本对话的语言约定，漏写则子代理会用英文回复。\n"
    "以下任务指令均以此语言要求为前提：\n"
    "\n"
    "请使用 projectmigrate 技能，将 /app 目录下的整个项目迁移到 RISC-V 平台。\n"
    "生成过程中请合理使用subagent和fork功能，防止上下文溢出。\n"
    "切记，一定要完全按照 projectmigrate 这个skill的每个步骤依次进行，不能跳步或忽略。\n"
    "【网络使用要求（必须遵守）】\n"
    "1. 默认离线运行：本镜像已预装 RISC-V 交叉工具链（riscv64-linux-gnu-gcc-14 / g++-14）、"
    "qemu-riscv64、cmake、gcov/lcov 等。任何阶段先 `command -v <tool>` 探测，"
    "能直接用就不要联网。\n"
    "2. 仅在「镜像内没有且确实必要」时才允许联网：例如编译/运行时缺少某个系统库（libfoo-dev）、"
    "或 RISC-V 新扩展编译器不支持需要从源更新工具链。禁止为以下情况联网：\n"
    "   - 仅为了「确认一下 / 看看最新版本 / 查文档复述」 → 优先用 riscv-doc-mcp 离线文档\n"
    "   - 已经失败可以靠改源码/换 -march/改 Makefile 解决的 → 自助修复不联网\n"
    "   - 用户未明确要求联网拉取额外数据（如 apt-key、第三方源）\n"
    "3. 允许联网时的执行要求：缺什么装什么；联网前在中文总结里说明「为什么需要联网 + 准备装什么」。\n"
    "4. 失败阈值：联网拉取失败 2 次仍不通，降级为离线修复（改源码/降版本/换扩展），"
    "并在中文总结里记录「已离线降级」，不要无限制重试。\n"
)


# ──────────────────────────────────────────────────────────────
# 项目级一键迁移 · 阶段技能 ②功能验证 / ③性能优化
# ──────────────────────────────────────────────────────────────
#
# v4.x.0-RUN-FLOW 设计要点（**总是贴皮覆盖式**）：
#
#   - uttest / migrate / asmrepair 都是项目维护的真实 SKILL.md，
#     源码在 server/assets/ai-agent/{x86,arm}/.pi/agent/skills/<name>/SKILL.md。
#     容器镜像 codemig-agent-base:1.0.0 的 Dockerfile.template 步骤 7 (COPY .pi) 可能
#     已把它们烘焙进 /root/.pi/，但**不论镜像里有没有**，我们都走统一流程：
#
#     1) _write_skill_to_repo → 从 assets 把 SKILL.md 复制到 <repo>/.skills/<name>/SKILL.md
#        并在末尾强制注入中文守则
#     2) _create_project_agent_process → cp -r /app/.skills/<name> /root/.pi/agent/skills/
#        （覆盖式 cp，无论镜像是否含 skill，最终以 /app/.skills/ 为准）
#
#   - 这种「总是贴皮」的好处：
#       · 老镜像（没烘焙）：cp 把 skill 注入容器，agent 看得到
#       · 新镜像（已烘焙）：cp 是覆盖式，使用本项目维护的版本，更可控
#       · 单一来源真理：server/assets/ai-agent/<arch>/.pi/agent/skills/
#       · 改 SKILL.md 不用重新 build docker image

# 阶段 ② 的触发 prompt：极简指令
# v4.x：按用户偏好走方案 B —— 即便容器内没有名为 uttest 的独立 SKILL.md，
# 也按 projectmigrate 阶段二 2.4 验证流程（对应 everything-riscv 阶段二 2.4）执行，
# 并追加 gcov / lcov 覆盖率分析（本项目独有扩展）。
#
# ★ v4.1.9 补 status/marking 闭环：与 everything 阶段二 2.4 步骤 4"更新 JSON 字段"对齐。
# 之前漏抽了 status START→DONE + marking 必填的强闭环——本轮补上。
uttest_prompt_template = (
    "【语言要求（最高优先级，先于一切任务指令）】\n"
    "你的所有输出必须全程使用简体中文，包括思考过程（thinking）、过程说明、错误消息、"
    "覆盖率报告与最终总结。禁止输出英文句子或英文段落，"
    "禁止 Let me... / I need to... 式英文思考；"
    "代码 / 命令 / 文件路径 / 寄存器名 / 覆盖率报告里纯数字表格保持英文原样不动；"
    "中文标点用全角（，。、；？！）。\n"
    "派发给 subagent/fork 的每条指令都必须写明「用简体中文汇报」，"
    "子任务不继承本对话的语言约定，漏写则子代理会用英文回复。\n"
    "以下任务指令均以此语言要求为前提：\n"
    "\n"
    "请对 /app 目录下已有的 RISC-V 迁移产物执行功能验证。\n"
    "\n"
    "【产物落位总则（benchmark 路径与兜底路径都必须遵守）】\n"
    "所有编译验证产物必须统一落在 /app/test/<验证目标名>/ 目录下"
    "（验证目标名 = benchmark/测试套件名，或兜底路径的源文件 basename），"
    "禁止在仓库根目录新留构建目录（如 build/、build-riscv64/）；"
    "也不要写 /tmp（容器 /tmp 在 pi --continue 切会话时会被清理，跨会话稳定保留的关键就是落地在仓库内）。\n"
    "每个验证目标目录的最终形态（清理中间产物后）至少包含：\n"
    "  - report.md：验证报告（必生成，规范见下）；\n"
    "  - coverage.txt：覆盖率报告（必生成）；\n"
    "  - expected.out / actual.out 或 run.log：运行输出与基线；\n"
    "  - build.log / run.log：编译与运行日志（推荐保留）；\n"
    "  - 驱动源文件（兜底路径的 main.c / Makefile / run.sh 等）。\n"
    "report.md 内容规范：①工程与验证目标概况（benchmark 名称或被测源文件）；"
    "②实际使用的工具链与完整编译命令（CC/CXX、-march/-mabi、构建目录）；"
    "③用例统计（总数/通过/失败/跳过）；④失败用例分析（迁移缺陷须修复后重跑，环境问题说明理由）；"
    "⑤覆盖率摘要（行/分支覆盖率数字，与 coverage.txt 对应）；⑥结论与遗留 TODO。\n"
    "编译中间产物（build/ 子目录、*.o / *.gcda / *.gcno / 可执行文件等）"
    "在覆盖率报告生成之后统一清理（原地构建的工程用 make clean 或按扩展名删除本次新增中间文件），"
    "只保留上述文件，避免污染仓库与前端文件树。\n"
    "\n"
    "【工作流来源】\n"
    "如果你的容器内已经存在名为 `uttest` 的独立 SKILL.md（路径 /root/.pi/agent/skills/uttest/SKILL.md），"
    "请直接按该 SKILL.md 内的工作流执行；\n"
    "**否则**按以下流程执行（这是 projectmigrate skill 阶段二 2.4 验证流程的执行版，"
    "对应 everything-riscv 阶段二 2.4 验证步骤的抽取）：\n"
    "\n"
    "【工作流步骤】\n"
    "1. **识别 RISC-V 迁移产物**：用 run_shell_command 扫 /app 下的 .S / .s / .c / .h / .cpp / Makefile，"
    "筛出含 RISC-V 关键字（riscv / rv64 / __riscv / riscv_vector.h）的文件作为验证目标。\n"
    "2. **★ 优先探测原工程自带 benchmark（首选路径）**：先确认原工程是否本身带有对应的 benchmark / "
    "测试套件，有则直接复用，不要自建单元测试。探测清单（逐项检查 /app 与其子目录）：\n"
    "   - test / tests / benchmark / benchmarks / bench / unit_test / unittest 等目录；\n"
    "   - CMakeLists.txt / Makefile 中的 test / check / benchmark 目标（`grep -rn -E "
    "'(add_test|enable_testing|benchmark|gtest|catch2|ctest|check:)' --include='CMakeLists.txt' --include='Makefile*' /app`）；\n"
    "   - 第三方基准套件特征：CTest、Google Test（libgtest）、Catch2、benchmark（google/benchmark）、"
    "nbench、SPEC 子目录等；\n"
    "   - README / docs 里声明的测试运行方式（`grep -rn -iE '(make (test|check)|ctest|run.?tests?|benchmark)' /app/README* /app/docs 2>/dev/null`）。\n"
    "   **命中时的执行要求**：\n"
    "   a. 按原工程自带的构建方式编译（CMake 用 `cmake -S . -B build && cmake --build build`，"
    "Makefile 用 `make test` / `make check` / 对应目标），只把工具链/编译参数换成 RISC-V 交叉链"
    "（-march/-mabi/-static 参数取值与兜底路径 Makefile 的要求一致，见步骤 3.b；CTest 场景给 ctest 传 qemu 包装）。"
    "**构建目录必须指向 /app/test/<benchmark名>/build/**"
    "（如 `cmake -S . -B /app/test/<benchmark名>/build`），不要在仓库根目录留 build/；"
    "若 benchmark 自身强制要求源内构建（CMakeLists 限制或源内生成文件），构建后把测试可执行文件与日志"
    "复制到 /app/test/<benchmark名>/ 下留档，并 make clean 清掉源内构建目录。\n"
    "   b. 在 qemu-riscv64 下运行测试程序，逐条记录用例通过情况"
    "（CTest 场景：先写一个 qemu 包装脚本 test/qemu_wrapper.sh ——"
    "`#!/bin/sh\\nexec qemu-riscv64 \"$@\"\\n`，"
    "再 `ctest -T test --overwrite ...` 或逐个 `qemu-riscv64 <test_binary>` 运行）；"
    "运行输出完整重定向到 /app/test/<benchmark名>/run.log；"
    "失败用例定位是「迁移缺陷」还是「环境/工具链问题」，迁移缺陷必须修复后重跑直至全过；\n"
    "   c. 覆盖率与 status/marking 闭环（步骤 5、6）同样适用：benchmark 跑通后仍需用 --coverage "
    "重编一份生成覆盖率报告（构建目录 /app/test/<benchmark名>/build-cov/）；\n"
    "   d. 按产物落位总则在 /app/test/<benchmark名>/report.md 写验证报告，"
    "并在最终中文总结里写明「使用了原工程自带 benchmark：<名称/目标>，共 N 条用例，通过 M 条」。\n"
    "   **未命中**（工程无任何自带测试）才走步骤 3 自建单元测试的兜底逻辑。\n"
    "3. **测试先行（兜底路径，仅当步骤 2 未命中时）**：为每个目标文件，在 /app/test/<file_basename>/ 下生成：\n"
    "   - main.c：用同一份输入驱动原始 x86/arm 实现与 RISC-V 实现，让两者输出对齐到 stdout 或固定文件；\n"
    "   - Makefile：\n"
    "        a. **工具链探测（必做，避免硬编码失败）**：先 `command -v riscv64-linux-gnu-gcc-14` 探测 RISC-V C 编译器；不存在再探测 `riscv64-linux-gnu-gcc`（容器只装不带版本后缀的包时常见）。C++ 项目用 `riscv64-linux-gnu-g++-14` → `riscv64-linux-gnu-g++` 同样回退。**探测结果直接写进 Makefile 的 CC / CXX 变量**，别在文本里硬编码后缀。\n"
    "        b. 编译参数：RISC-V 用 `-march=rv64gcv_zbb_zbc_zvbc_zvkb_zvksed -mabi=lp64d -static`；\n"
    "        c. **原始版本探测**：用 `command -v x86_64-linux-gnu-gcc-14 / x86_64-linux-gnu-gcc` 与 `aarch64-linux-gnu-gcc-14 / aarch64-linux-gnu-gcc` 探测原生 / ARM 交叉编译器；**哪个找不到就跳过对应版本**，不要强行编；至少要把 RISC-V 版本编出来跑 qemu。\n"
    "        d. **找不到 cmake 时**：不要因为原工程用 CMake 而整轮卡住。直接在本目录下写一个最小 Makefile，把目标源文件 + RISC-V 实现串起来编；这是验证产物，CMake 集成是阶段三的事。\n"
    "   - run.sh：先跑原实现把输出写到 expected.out，再跑 RISC-V 版本到 actual.out，diff 二者。\n"
    "4. **执行 + 回归（兜底路径）**：cd /app/test/<file_basename> && make 2>&1 | tee build.log && bash run.sh 2>&1 | tee run.log；"
    "若 diff 有差异，定位修复并重跑 run.sh 直至完全一致。所有产物都在 /app/test/<basename>/ 下（不要写 /tmp，理由见产物落位总则）。\n"
    "5. **覆盖率分析（必须，本项目独有扩展；benchmark 路径与兜底路径都做）**：用 gcov 配合 --coverage 选项编译 RISC-V 版本，"
    "跑测试/benchmark 后用 gcov / lcov 生成行 / 分支覆盖率报告，输出到 /app/test/<验证目标名>/coverage.txt。\n"
    "6. **status/marking 闭环更新（必做，与 everything 阶段二 2.4 步骤 4 一致——之前漏抽）**：\n"
    "   验证通过后，**必须**直接编辑 `scan_result.json`（用 `edit_file` / `write_file` 工具）：\n"
    "   - 把对应条目的 `status` 从 `START` 改为 `DONE`\n"
    "   - 同时填写 `marking`（3 种内容选其一）：\n"
    "     - 正常：`无异常，性能与 x86/ARM 实现持平（或给出相对比例）`\n"
    "     - 语义差异：`语义差异：<具体点>，已通过测试规避`\n"
    "     - 需要后续修复：`TODO(后续)：<具体项>`\n"
    "   - 写回时必须保持 schema 与缩进一致；不要改 `target` / `suggestion_class_count` / `missing_class_count` 这三个顶层字段。\n"
    "7. **进度自检（必做）**：所有目标条目 `status=DONE`；每个 `DONE` 条目 `marking` 非空；"
    "汇编类条目经过知识库查证证据；非汇编条目完成架构宏替换并通过 QEMU 验证；"
    "自带 benchmark 的工程在总结中写明 benchmark 名称与用例通过数；"
    "每个验证目标都有 /app/test/<验证目标名>/report.md 与 coverage.txt，"
    "且仓库根目录没有遗留本次验证产生的构建目录（build/ 等已清理）；"
    "覆盖率报告已生成且行覆盖 ≥ 70%（与 everything 阶段二 2.4 进度自检段对齐）。\n"
    "\n"
    "【网络使用要求（必须遵守）】\n"
    "1. 默认离线运行：本镜像已预装 riscv64-linux-gnu-gcc-14 / g++-14、qemu-riscv64、cmake、gcov、lcov。"
    "在写 Makefile / 跑 lcov 之前，先 `command -v <tool>` 探测，能直接用就不要联网。\n"
    "2. 仅在「镜像内确实缺少、且是验证/覆盖率链路必需」时才允许联网，例如：\n"
    "   - lcov 在镜像内探测不到，而你需要生成 branch coverage；\n"
    "   - gcov 与所用编译器版本不兼容，需要装对应版本 libgcov-dev；\n"
    "   - 原工程的被测代码强依赖某个系统库（libfoo-dev），未装则无法链编。\n"
    "3. 禁止为以下情况联网：仅为了查看/复述文档、确认版本号、改 -march 即可解决、能靠改 Makefile/-static/-l 参数规避的依赖问题。\n"
    "4. 联网时执行要求：缺什么 `apt-get install` 装什么，联网前在中文总结里写明「为什么需要联网 + 准备装什么」。\n"
    "5. 失败阈值：联网拉取失败 2 次仍不通，降级为离线修复（减少非必要覆盖率项、用 --coverage 替代 lcov、"
    "接受行覆盖低于 70% 并在 marking 里说明），不要无限制重试。\n"
    "\n"
    "【收尾】\n"
    "最终把每个验证目标的 report.md / coverage.txt 等产物路径列出来"
    "（统一在 /app/test/<验证目标名>/ 下），告诉用户哪些目标已完成、哪些仍需修复。"
)



def _query_all_files_with_suggestions(user_name, dir_id):
    """查询全部有建议且未忽略的文件列表"""
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_FILES_WITH_SUGGESTIONS_SQL)
        rows = cursor.fetchall()
        return True, rows
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()


def _query_suggestions_for_file(user_name, dir_id, file_id):
    """查询某个文件的全部建议"""
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_SUGGESTIONS_FOR_FILE_SQL, (file_id,))
        rows = cursor.fetchall()
        return True, rows
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────────────────────────────
#  一键迁移用户手动选中的代码段（v4.0：从 _file_suggestion 表 is_manual=1 取）
#  替代原 codemig_manual_selection 表，SELECT_MANUAL_SUGGESTIONS_BY_DIR_SQL 是核心 SQL。
#  返回格式：(file_id, file_path, start_line, end_line) —— 与原 list_manual_selections_for_projectmigrate 一致。
# ─────────────────────────────────────────────────────────────────────
SELECT_MANUAL_SUGGESTIONS_BY_DIR_SQL = """
    SELECT DISTINCT File.file_id AS file_id,
           File.file_path AS file_path,
           Suggestion.start_line_number AS start_line,
           Suggestion.end_line_number AS end_line
    FROM codemig_task_directory_file_suggestion AS Suggestion
    JOIN codemig_task_directory_file AS File
      ON File.file_id = Suggestion.file_id
    WHERE Suggestion.is_manual = 1
      AND Suggestion.ignored = 0
      AND File.has_removed = 0
      AND File.type = 0
      AND File.dir_id = ?
    ORDER BY File.file_path ASC, Suggestion.start_line_number ASC
"""


def _query_manual_suggestions_for_projectmigrate(user_name, dir_id):
    """查询某 dir 下所有 manual 选中（is_manual=1）的建议，替代原 codemig_manual_selection 表

    Returns:
        list[(file_id, file_path, start_line, end_line)]
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_MANUAL_SUGGESTIONS_BY_DIR_SQL, (dir_id,))
        return cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("[一键迁移] manual_suggestions 查询失败: %s", err)
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _query_existing_arch_for_missing_file(user_name, dir_id, file_id):
    """查询某缺失文件对应的现有架构文件/目录路径列表。

    用于 _build_projectmigrate_prompt 中组装 scan_result.json 顶层
    `missing_class[]` 条目时填充 `existing_arch_paths` 字段
    （对齐 everything-riscv/skills/riscv-migrate/referens/project_scan.md 的 schema）。

    数据源：codemig_task_directory_existing_architecture 表，关联到 file_id。
    SQL 与 query_processor.query_missing_file_from_database 用的完全一致；这里
    为了避免在模块顶部新增 import 行，函数内局部 import 该常量（与
    _build_projectmigrate_prompt 中 query_missing_files_sql 的局部 import 模式
    保持一致）。

    Args:
        user_name: 用户名
        dir_id: 目录 ID
        file_id: 缺失文件的 file_id

    Returns:
        tuple: (status, rows)
            status: True=成功（rows 可能为空），False=查询失败
            rows: list[(architecture_path, type)]，type=0=文件，type=1=目录
                  失败时返回 []
    """
    from plugin.codemig.codemig_task_manager.query_processor import (
        SELECT_EXIST_ARCH_BY_MISSING_FILE_ID_SQL,
    )
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_EXIST_ARCH_BY_MISSING_FILE_ID_SQL, (file_id,))
        rows = cursor.fetchall()
        return True, rows
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.warning(
            "[一键迁移] existing_arch 查询失败: file_id=%s err=%s",
            file_id, err,
        )
        return False, []
    except ImportError as _imp_err:
        LOGGER.warning(
            "[一键迁移] existing_arch SQL 常量 import 失败（已忽略）: %s",
            _imp_err,
        )
        return False, []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _build_projectmigrate_prompt(user_name, dir_id, manual_items=None, task_id=None,
                                  prompt_to_write=None):
    """
    构建项目级迁移的 prompt，并将迁移清单写入 scan_result.json。

    从数据库查询所有有建议的文件及其建议，组装成与 everything 工程对齐的
    scan_result.json 格式，写入仓库根目录（即 Docker 容器内的 /app）。
    prompt 本身只包含固定指令（让 Agent 自行 read_file 读取 JSON），不嵌入
    任何清单内容，从而彻底消除文件数过多时的上下文溢出风险。

    Args:
        user_name: 用户名
        dir_id: 目录 ID
        manual_items: 用户手动选中的代码段列表，格式为：
                     [{"file_path": str, "start_line": int, "end_line": int}, ...]
                     传 None 或 [] 时，自动从 DB 兜底读取（阶段 13.x-MANUAL-ITEMS-TO-JSON）。
        prompt_to_write: 是否同时把 prompt 写到 <repo>/.prompt.txt。
                       - None（默认）：不写；_create_project_agent_process 会自己写
                         各自的 prompt（uttest 等）
                       - 显式传入字符串：把这段 prompt 写到 .prompt.txt，与 .skills/
                         同级一起产出，保证 commit_git_repo(stage:before) 的 git add -A
                         能把它收进 commit，避免被 restore_workspace / reset_to_commit
                         的 `git clean -fd` 杀掉。**只在一键迁移路径使用**。

    Returns:
        tuple: (content, file_list) — prompt 内容和文件信息列表（含 file_id/file_path）
    """
    status, file_rows = _query_all_files_with_suggestions(user_name, dir_id)
    if not status or not file_rows:
        return None, []

    # ────── 阶段 13.x-MANUAL-ITEMS-TO-JSON：manual_items 兜底分支 ──────
    # 设计动机：前端 check() 应当把 manualMigrateItemsMap 序列化为 manual_items
    # 传进来；但万一忘了/失败（重构、断网、版本不对），后端要兜底从 DB 拿，保证
    # 用户手动添加的代码段永远能进 scan_result.json，让 AI 真正处理它。
    # v4.0 改用 _query_manual_suggestions_for_projectmigrate 直接读
    # codemig_task_directory_file_suggestion 表 is_manual=1 的行（不再走 codemig_manual_selection 表）。
    if not manual_items:
        try:
            db_rows = _query_manual_suggestions_for_projectmigrate(user_name, dir_id)
            manual_items = [
                {
                    "file_id": fid,
                    "file_path": fpath,
                    "start_line": sl,
                    "end_line": el,
                }
                for fid, fpath, sl, el in db_rows
                if fpath and sl and el
            ]
            LOGGER.info(
                "[一键迁移] manual_items 兜底从 DB 读取: user=%s dir_id=%s "
                "task_id=%s 取到 %d 条",
                user_name, dir_id, task_id, len(manual_items),
            )
        except Exception as _fb_err:
            LOGGER.error(
                "[一键迁移] manual_items 兜底异常（已忽略）: %s", _fb_err,
                exc_info=True,
            )
            manual_items = []  # 出错兜空，绝不阻塞拼装流程

    repo_path = get_repo_path(user_name, dir_id)
    file_list = []
    suggestion_class = []

    # 处理 changed files
    for file_id, file_path in file_rows:
        file_list.append({"file_id": file_id, "file_path": file_path})

        # 将绝对路径转为容器内路径（/app/ 开头）
        try:
            rel_path = os.path.relpath(file_path, repo_path)
            container_path = "/app/" + rel_path
        except ValueError:
            container_path = file_path

        file_name = os.path.basename(file_path)

        # 查询该文件的全部建议
        status_sug, suggestions = _query_suggestions_for_file(user_name, dir_id, file_id)
        if not status_sug or not suggestions:
            continue

        for start_line, end_line, solver_type, suggestion_text, _ in suggestions:
            try:
                type_desc = SolverType(solver_type).description
            except (ValueError, KeyError):
                type_desc = "未知"
            suggestion_class.append({
                "class_type": "suggestion_class",
                "file_name": file_name,
                "file_path": container_path,
                "solver_type": solver_type,
                "solver_description": type_desc,
                "start_line": start_line,
                "end_line": end_line,
                "migration_suggestion": suggestion_text,
                # ────── 与 everything-riscv/skills/riscv-migrate SKILL.md 对齐 ──────
                # status / marking 是迁移进度权威源（不再向源码写 MIGRATE-* 注释）。
                # 三态互斥（TODO/START/DONE）；DONE 时 marking 必填。
                # 这里默认 TODO / ""；agent 在 projectmigrate skill 阶段 E 通过后改 DONE + 填 marking。
                "status": "TODO",
                "marking": "",
            })

    # 处理 missing files
    from plugin.codemig.codemig_task_manager.query_processor import query_missing_files_sql
    
    # 查询缺失文件（dir_id就是task_id）
    status, missing_files_rows = query_missing_files_sql(user_name, dir_id)
    if not status:
        missing_files_rows = []
    
    missing_files = []
    for row in missing_files_rows:
        # row格式: (file_id, file_path, miss_type)
        file_id = row[0]
        file_path = row[1]
        file_name = os.path.basename(file_path)
        miss_type = row[2] if len(row) > 2 else None

        # ★ 关键修复（v4.1.6）：缺失文件路径也要做容器内路径转换（/app/{rel_path}），
        # 与 suggestion_class（changed files）和 manual_selection 保持一致。
        # 顶层 missing_class 数组（scan_result.json 输出）依赖此处的 file_path，
        # 否则 AI 拿到的就是宿主机的绝对路径，无法定位容器内仓库目录。
        try:
            rel_path = os.path.relpath(file_path, repo_path)
            container_path = "/app/" + rel_path
        except ValueError:
            container_path = file_path

        # ────── 与 everything-riscv/skills/riscv-migrate/referens/project_scan.md 对齐 ──────
        # missing_class[] 条目 schema（顶层数组，与 suggestion_class[] 同级）：
        #   class_type="missing_class"
        #   missing_path：缺失的 riscv64 文件/目录绝对路径（容器内 /app/...）
        #   is_file：bool（True=文件缺失，False=目录缺失）
        #   existing_arch_paths：list[str]，已存在的其他架构文件/目录路径
        #   migration_suggestion：建议文本
        #   status：三态 TODO/START/DONE
        #   marking：DONE 时必填
        # is_file 用 miss_type 推断（miss_type==0 通常为文件，==1 为目录；保守置 True）
        is_file_flag = (miss_type == 0) if miss_type is not None else True

        # existing_arch_paths：从 DB 现有架构表拉兄弟架构路径（如果有）
        # 注意：保持 0/[] 兜底，绝不阻塞拼装流程（缺失时下游 agent 仍可继续）。
        # ★ 关键修复（v4.1.8）：existing_arch_paths 必须与 missing_path 路径空间一致
        # ——都是容器内 /app/... 路径。DB 里存的是宿主机绝对路径，必须用
        # os.path.relpath(p_str, repo_path) 转换后再 /app/{rel}。否则容器内 agent
        # 拿到宿主机路径无法定位兄弟架构文件，migration_suggestion 的"参考路径"形同虚设。
        existing_arch_paths = []
        try:
            status_arch, arch_rows = _query_existing_arch_for_missing_file(
                user_name, dir_id, file_id,
            )
            if status_arch and arch_rows:
                container_arch_paths = []
                for p in arch_rows:
                    p_str = p if isinstance(p, str) else (p[0] if p else "")
                    if not p_str:
                        continue
                    try:
                        rel = os.path.relpath(p_str, repo_path)
                        container_arch_paths.append("/app/" + rel)
                    except ValueError:
                        # ValueError 通常意味着 p_str 在 repo_path 之外（DB 脏数据兜底）
                        container_arch_paths.append(p_str)
                existing_arch_paths = container_arch_paths
        except Exception as _arch_err:
            LOGGER.warning(
                "[一键迁移] missing_class existing_arch_paths 查询失败（已忽略）: %s",
                _arch_err,
            )

        # ────── 与 everything-riscv/skills/riscv-migrate/referens/project_scan.md 对齐 ──────
        # missing_class[] 条目 schema（顶层数组，7 字段；与 everything project_scan.md L66-76 1:1）：
        #   class_type="missing_class"
        #   missing_path：缺失的 riscv64 文件/目录路径（容器内 /app/...）
        #   is_file：bool（True=文件缺失，False=目录缺失）
        #   existing_arch_paths：list[str]，容器内其他架构文件/目录路径
        #   migration_suggestion：建议文本
        #   status：三态 TODO/START/DONE
        #   marking：DONE 时必填
        # **不写 file_id / file_name / file_path**：everything schema 中没有这三个字段；
        # `missing_path` 已经是权威路径，再写 file_path 语义重复并会让 agent 困惑该用哪个。
        # is_file 用 miss_type 推断（miss_type==0 通常为文件，==1 为目录；保守置 True）
        is_file_flag = (miss_type == 0) if miss_type is not None else True

        missing_files.append({
            'class_type': 'missing_class',
            'missing_path': container_path,   # 容器内 /app/... 路径
            'is_file': bool(is_file_flag),
            'existing_arch_paths': existing_arch_paths,
            'migration_suggestion': (
                f"参考现有架构文件/目录为该架构补充 RISC-V 实现；"
                f"参考路径：{existing_arch_paths if existing_arch_paths else '（暂无，需重写）'}"
            ),
            'status': 'TODO',
            'marking': '',
        })

    # ────── 与 everything project_scan.md L48 对齐 ──────
    # everything 的 missing_class[] 是顶层独立数组，与 suggestion_class[] 同级、不互相包含。
    # 删除「missing → suggestion_class 双重写入」块：同一份缺失文件不再同时塞进两个数组，
    # 避免 agent 看到重复条目（之前 L3039-3051 的 code_migrate-style 副本会被 agent 误判为
    # 真实迁移建议）。missing_class[] 已是权威源，file_list 不再混入缺失文件。
    # file_list 与 missing_files 各自独立；agent 通过顶层 missing_class[] 数组处理缺失条目。

    # 处理用户手动选中的代码段
    if manual_items:
        for item in manual_items:
            file_path = item.get('file_path')
            start_line = item.get('start_line')
            end_line = item.get('end_line')
            
            if not file_path or not start_line or not end_line:
                continue
            
            file_name = os.path.basename(file_path)

            # ★ 关键修复（v4.1.7）：前端传来 manual_selection 的 file_path 是相对路径
            # （USE_ABSOLUTE_PATH=False 时后端 list_files 返回的就是相对路径
            #  ./Admin/1/changed/vectorscan-develop/xxx），os.path.relpath 不能处理相对路径
            # （会按 CWD 解析产生大量 ../../，例如 /app/../../../../../server/plugin/codemig/...），
            # 所以这里要先把相对路径基于 get_codemig_data_path() 转成绝对路径，再 relpath。
            if not os.path.isabs(file_path):
                abs_file_path = os.path.join(
                    get_codemig_data_path(),
                    file_path.lstrip("./").lstrip("/")
                )
            else:
                abs_file_path = file_path

            # 将绝对路径转为容器内路径
            try:
                rel_path = os.path.relpath(abs_file_path, repo_path)
                container_path = "/app/" + rel_path
            except ValueError:
                container_path = file_path
            
            # 添加到 suggestion_class
            suggestion_class.append({
                "class_type": "manual_selection",
                "file_name": file_name,
                "file_path": container_path,
                "solver_type": 6,  # 6 表示用户手动选中
                "solver_description": "用户选中",
                "start_line": start_line,
                "end_line": end_line,
                "migration_suggestion": "用户手动选中的代码段",
                # ────── 与 everything-riscv/skills/riscv-migrate SKILL.md 对齐 ──────
                "status": "TODO",
                "marking": "",
            })

    # ────── 阶段 13.x-MANUAL-ITEMS-TO-JSON：拼装完成日志 ──────
    # 让用户在后端日志里能直观看到 scan_result.json 里写进去了多少条 manual_selection。
    manual_count = sum(
        1 for it in suggestion_class
        if it.get("class_type") == "manual_selection"
    )
    LOGGER.info(
        "[一键迁移] manual_selection → scan_result 拼装完成: user=%s dir_id=%s "
        "task_id=%s 共 %d 条 manual_selection (total suggestion_class=%d)",
        user_name, dir_id, task_id, manual_count, len(suggestion_class),
    )

    if not suggestion_class:
        return None, []

    # 组装 scan_result.json 并写入仓库根目录
    scan_result = {
        "target": "/app",
        "suggestion_class_count": len(suggestion_class),
        "missing_class_count": len(missing_files),
        "suggestion_class": suggestion_class,
        "missing_class": missing_files,
    }
    scan_result_path = os.path.join(str(repo_path), "scan_result.json")
    try:
        with open(scan_result_path, 'w', encoding='utf-8') as f:
            json.dump(scan_result, f, ensure_ascii=False, indent=2)
    except OSError as e:
        LOGGER.error(f"Failed to write scan_result.json: {e}")
        return None, []

    # 写入 projectmigrate skill 到仓库目录（容器启动时复制到 skills 目录）
    skill_text = projectmigrate_skill_content.format(platform="Linux")
    skill_dir = os.path.join(str(repo_path), ".skills", "projectmigrate")
    skill_file_path = os.path.join(skill_dir, "SKILL.md")
    try:
        os.makedirs(skill_dir, exist_ok=True)
        with open(skill_file_path, 'w', encoding='utf-8') as f:
            f.write(skill_text)
    except OSError as e:
        LOGGER.error(f"Failed to write projectmigrate SKILL.md: {e}")
        return None, []

    content = projectmigrate_prompt_template

    # 仅当调用方显式传入 prompt_to_write 时，紧挨着 .skills/ 写 .prompt.txt
    # （容器内路径 /app/.prompt.txt）。必须放在 commit_git_repo(stage:before)
    # **之前**，让 `git add -A` 把它一起收进 commit 成为已跟踪文件，避免后续
    # restore_workspace / reset_to_commit 的 `git clean -fd` 把它当未跟踪文件
    # 干掉（.skills/ 之所以能留下，正是因为它在 commit 之前写、git add -A 已收录）。
    #
    # 两阶段共享同一个 helper：
    #   - 一键迁移（query_project_migrate）→ 传 projectmigrate_prompt_template
    #   - 功能验证（run_ut_test）           → 传 uttest_prompt_template
    # 其它阶段不传 prompt_to_write，跳过。
    if prompt_to_write is not None:
        if not _write_prompt_to_repo_for_commit(
            str(repo_path), prompt_to_write,
            request_uuid='', stage_label='pre-commit',
        ):
            return None, []

    return content, file_list


def _write_prompt_to_repo_for_commit(repo_path: str, content: str,
                                    request_uuid: str, stage_label: str) -> bool:
    """
    把 prompt 写到 <repo>/.prompt.txt（容器内路径 /app/.prompt.txt），用于
    commit_git_repo(stage:before) **之前**的写入场景。

    两个共享阶段都通过本函数：
      - 一键迁移（query_project_migrate）
      - 功能验证（run_ut_test via _build_skill_runner）

    设计动机：在 commit 之前写入，使后续 commit_git_repo 的 `git add -A`
    把 .prompt.txt 一并收进 commit，成为已跟踪文件，restore_workspace /
    reset_to_commit 的 `git clean -fd` 不会杀它。

    Args:
        repo_path: 仓库根目录绝对路径
        content: 完整 prompt 文本
        request_uuid: 请求 uuid（用于日志关联）
        stage_label: 阶段标识（"一键迁移" / "功能验证" / "性能优化"），用于日志

    Returns:
        bool: True=成功，False=失败（调用方应走错误兜底）
    """
    prompt_file = os.path.join(repo_path, '.prompt.txt')
    try:
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        LOGGER.info(
            f"[{stage_label}] 写入 {prompt_file} ({len(content)} chars), "
            f"request_uuid={request_uuid}，与 .skills/ 同级，供 commit_git_repo 一并 add"
        )
        return True
    except OSError as e:
        LOGGER.error(f"[{stage_label}] 写入 {prompt_file} 失败: {e}")
        return False


def _create_project_agent_process(content: str, file_path: str, agent_config,
                                  request_uuid, cmd_list, api_format,
                                  skill_name: str = 'projectmigrate',
                                  inject_skill: bool = True,
                                  resume: bool = False,
                                  named_volume: Optional[str] = None) -> subprocess.Popen:
    """
    创建项目级迁移 / 阶段技能的 Agent 进程。

    与 create_agent_process 的区别：在容器启动后、agent 命令执行前，
    若 inject_skill=True，先将 /app/.skills/{skill_name} 复制到 pi 和 cursor
    的 skills 目录，使对应 skill 对 Agent 可见。

    inject_skill=False 时（v4.x 推荐用于 uttest）：
      不做 cp，不依赖容器内是否有烘焙 skill，agent 完全靠 prompt 内容工作。

    skill_name 可选值：
      - 'projectmigrate'（默认，向后兼容一键迁移）
      - 'uttest'（② 功能验证）

    resume 与 named_volume（v4.x.0-RESUME，一键迁移中断恢复）：
      - 默认 resume=False / named_volume=None 时函数行为与改前完全一致
      - resume=True：跳过 .prompt.txt 写入、agent_cmd 切到 `pi --continue ...`、
        inject_skill 强制禁用（不 cp skill，避免被命名卷里的同名 .pi 覆盖）。
        用于容器异常中断后从 pi 会话存档继续推进。
      - named_volume：非 None 时将 docker 命名卷额外挂到容器内的 /root/.pi，
        以持久化 pi 会话存档。默认 None 表示不挂载，对旧路径零影响。
    """
    creds, err = _resolve_agent_credentials(agent_config)
    if err:
        return err

    proxy = _load_proxy_settings()

    # v4.x.0-RUN-FLOW prompt 注入：把多行 prompt 写入 <repo>/.prompt.txt（容器内路径 /app/.prompt.txt），
    # agent 通过读取文件获取完整内容，**避免把多行 / 中文括号 / ** / 反引号**塞进
    # shell 单引号字符串导致的 sh 解析失败（之前 pi -p '...' 被 sh 当成多行命令解释，
    # 报 "sh: 3: 【工作流来源】: not found"）。
    #
    # 【v4.x.0-PROMPT-PRE-COMMIT】两个阶段（一键迁移 / uttest）
    # 都已经在 commit_git_repo(stage:before) **之前** 由各自的 _handler /
    # _build_projectmigrate_prompt 把 .prompt.txt 写到了 .skills/ 同级，
    # 让 git add -A 把它一起收进 commit 成为已跟踪文件，避免 restore_workspace /
    # reset_to_commit 的 `git clean -fd` 把它当未跟踪文件杀掉。这里只在
    # .prompt.txt 不存在时补写，防御未来新增阶段忘了自己写。
    prompt_file = os.path.join(str(file_path), '.prompt.txt')
    if resume:
        # v4.x.0-RESUME：恢复路径不再写 .prompt.txt，让 pi 从 /root/.pi/sessions/ 恢复上下文。
        LOGGER.info(f"[resume] 跳过 .prompt.txt 写入，使用命名卷里的 pi 会话存档")
    elif not os.path.exists(prompt_file):
        try:
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            LOGGER.info(f"[prompt] 写入 {prompt_file} ({len(content)} chars)")
        except OSError as e:
            LOGGER.error(f"[prompt] 写入 {prompt_file} 失败: {e}")
            return {"code": -1, "msg": f"写入 prompt 文件失败: {e}"}
    else:
        LOGGER.info(f"[prompt] {prompt_file} 已存在（由 _build_projectmigrate_prompt 写），跳过重复写入")

    # agent 通过管道从文件读取 prompt（sh 不参与 prompt 内容解析，绝对安全）
    agent_cmd, env, err = _build_agent_cmd_and_env(
        api_format, creds["api_key"], creds["base_url"], creds["model"],
        use_prompt_file=True, resume=resume,
    )
    if err:
        return err

    # 将当前阶段对应的 skill 注入到容器。
    # 当 inject_skill=False 时（v4.x 推荐对 uttest 启用）：
    #   不做任何 cp，完全靠 prompt_template 自带完整工作流驱动 agent。
    if inject_skill and not resume:
        setup_skill_cmd = (
            f"cp -r /app/.skills/{skill_name} /root/.pi/agent/skills/ 2>/dev/null; "
            f"cp -r /app/.skills/{skill_name} /root/.cursor/skills/ 2>/dev/null; "
        )
    else:
        # inject_skill=False 或 resume=True：跳过 cp，避免覆盖命名卷里 pi 缓存的 .pi/agent/skills/。
        # 末尾必须有 `;`，否则 `true` 紧接 `(` 会被 sh 当成 `true` 的位置参数报语法错。
        setup_skill_cmd = "true;"

    # 注意：这里不再调 _build_chown_tail —— _assemble_docker_run_cmd 内部已统一追加
    # chown 收尾。之前这里先拼一次、公共函数里再拼一次，导致每次容器运行对整个
    # /app 挂载卷做两次递归 chown -R（大工程下每个迁移阶段收尾时间翻倍）。
    shell_cmd = f"{setup_skill_cmd} ({agent_cmd})"

    # v4.x.0-RESUME：仅当调用方传 named_volume 时才挂载命名卷（默认 None = 不挂，保持旧行为）
    extra_mounts = (
        [] if not named_volume
        else ["-v", f"{named_volume}:/root/.pi"]
    )

    command = _assemble_docker_run_cmd(
        request_uuid=request_uuid,
        file_path=file_path,
        api_format=api_format,
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        model=creds["model"],
        https_proxy=proxy["https_proxy"],
        http_proxy=proxy["http_proxy"],
        no_proxy=proxy["no_proxy"],
        shell_cmd=shell_cmd,
        extra_mounts=extra_mounts,
    )

    return _spawn_docker_agent(command, env, cmd_list)


# =============================================================================
# v4.x.0-RESUME 一键迁移中断恢复 helpers
# =============================================================================
# 设计原则：
#   1. 命名卷只允许 [a-zA-Z0-9][a-zA-Z0-9_.-]（docker 强约束），故对 user_name
#      做 `re.sub(r'[^a-zA-Z0-9_.-]', '_', ...)` 并截断到 32 字符。
#   2. 取消按钮调 `cancel_ai_suggestion_by_id`，只删 docker_<uuid> 匿名 volume，
#      永远不删命名卷。命名卷的生命周期由 helper 控制。
#   3. 所有 helper 都是无副作用的 pure-function（除 _ensure_named_volume 与
#      _remove_named_volume 会真实 docker 调用），可被多次安全调用。

_VOLUME_STAGE_PREFIX = {
    'projectmigrate': 'codemig_migrate_pm',
    'uttest': 'codemig_migrate_ut',
}


def _migrate_named_volume_name(user_name: str, dir_id, stage: str) -> str:
    """
    命名卷规范：`codemig_migrate_<stage>_<safe_user>_<dir_id>`。

    docker volume 名约束：
      - 只允许 [a-zA-Z0-9][a-zA-Z0-9_.-]
      - 总长 255 字符以内
    故 `safe_user_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', user_name)[:32]`。
    """
    safe_user = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(user_name))[:32] or 'u'
    return f"{_VOLUME_STAGE_PREFIX.get(stage, 'codemig_migrate')}_{safe_user}_{dir_id}"


def _ensure_named_volume(volume_name: str) -> str:
    """
    确保命名卷存在（不存在则 docker volume create）。

    返回 volume_name（无异常即视为可用；调用方负责在失败时给出友好提示）。
    """
    try:
        subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        LOGGER.info(f"[resume] 命名卷 {volume_name} 已存在，复用")
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                ["docker", "volume", "create", volume_name],
                check=True,
                capture_output=True,
                text=True,
            )
            LOGGER.info(f"[resume] 已创建命名卷 {volume_name}")
        except Exception as e:
            LOGGER.error(f"[resume] docker volume create {volume_name} 失败: {e}")
            raise
    return volume_name


def _remove_named_volume(volume_name: str) -> None:
    """主动删除命名卷（仅在 helper 语义上叫出"完成清理"或"放弃恢复"时调用）。"""
    try:
        subprocess.run(
            ["docker", "volume", "rm", volume_name],
            capture_output=True,
            text=True,
        )
        LOGGER.info(f"[resume] 已删除命名卷 {volume_name}")
    except Exception as e:
        LOGGER.warning(f"[resume] 删除命名卷 {volume_name} 失败（忽略）: {e}")


def _resumable_status_for_volume(volume_name: str) -> dict:
    """
    判定命名卷是否含可恢复会话。

    仅调一次 `docker volume inspect <name>`（毫秒级）：
      - 卷不存在 → available=False
      - 卷存在   → available=True（卷由本模块 _create_project_agent_process 创建，
                   存在即代表至少写过 1 个 pi session，无需再 ls 内部文件）

    返回 `{available: bool}`。
    失败/无卷时 `available=False`，调用方据此决定是否显示"继续"按钮。
    """
    try:
        inspect = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if inspect.returncode != 0:
            LOGGER.info(f"[resume] 命名卷 {volume_name} 不存在，跳过探测")
            return {'available': False}
        return {'available': True}
    except subprocess.TimeoutExpired:
        LOGGER.warning(f"[resume] docker volume inspect {volume_name} 超时（3s）")
        return {'available': False}
    except FileNotFoundError:
        LOGGER.warning("[resume] docker 命令不存在，无法探测命名卷")
        return {'available': False}
    except Exception as e:
        LOGGER.warning(f"[resume] docker volume inspect {volume_name} 失败: {e}")
        return {'available': False}


def _resumable_status_all_stages(user_name: str, dir_id) -> dict:
    """
    返回各阶段可恢复状态：
        {
          'projectmigrate': {...},
          'uttest': {...},
        }
    """
    out = {}
    for stage in _VOLUME_STAGE_PREFIX.keys():
        vol = _migrate_named_volume_name(user_name, dir_id, stage)
        out[stage] = _resumable_status_for_volume(vol)
    return out


def _maybe_prepare_resume(user_name: str, dir_id, stage: str, vol: str) -> bool:
    """
    恢复路径的前置准备（v3.2 改造产物）：
      1. 探测命名卷是否有可用 pi 会话（卷由发起方在启动前已 _ensure_named_volume）。
      2. 【v3.2 关键改造】不再调 restore_workspace 丢弃工作区。
         理由：
           - pi --continue 恢复的是 prompt 对话上下文（命名卷 /root/.pi/sessions/），
             与工作区状态无关
           - 工作区里的 agent 半成品已经在 intermediate-user-stop / stage-end-cancel
             commit 里留痕，用户随时可回溯
           - v3.2 铁律 5：唯一可触发 reset 的入口是用户显式点"回退迁移"
      3. 不在此处真正启动容器，仅做副作用最小化的探测。

    返回 True 表示命名卷可用（available=True）；False 表示不可恢复。
    """
    status = _resumable_status_for_volume(vol)
    if not status.get('available'):
        LOGGER.warning(f"[resume] 命名卷 {vol} 无可用 pi 会话，放弃恢复")
        return False
    LOGGER.info(
        f"[resume] 命名卷 {vol} 可用（available=True），"
        f"跳过工作区清理（v3.2：用户动作边界外不动 git 工作区）"
    )
    return True


# agent 静态资产根（skills/mcp.json/pipi 等随仓库分发，曾位于 tools_src/ai-agent-docker）
_AGENT_ASSETS_ROOT = os.path.realpath(os.path.join(MODULE_PATH, 'assets', 'ai-agent')) if MODULE_PATH else None


def _list_agent_mcp_servers() -> list:
    """读取 agent 镜像 mcp.json（server/assets/ai-agent/<arch>/.pi/agent/mcp.json）
    的 mcpServers 名单，供开头运行摘要展示。

    与 _resolve_skill_source_path 同样的 arch 候选顺序；文件缺失 / 解析失败
    返回空列表（摘要里显示「未配置」，不影响主流程）。
    """
    if not _AGENT_ASSETS_ROOT:
        return []
    host_arch = platform.machine().lower()
    candidates = []
    if host_arch in ('x86_64', 'amd64'):
        candidates.append('x86')
    elif host_arch in ('aarch64', 'arm64'):
        candidates.append('arm')
    for fallback in ('x86', 'arm'):
        if fallback not in candidates:
            candidates.append(fallback)
    for arch in candidates:
        mcp_path = os.path.join(
            _AGENT_ASSETS_ROOT, arch,
            '.pi', 'agent', 'mcp.json',
        )
        try:
            with open(mcp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            servers = (data.get("mcpServers") or {})
            if isinstance(servers, dict):
                return list(servers.keys())
        except (OSError, ValueError) as e:
            LOGGER.debug("读取 mcp.json 失败（arch=%s）: %s", arch, e)
    return []


def _build_env_summary(agent_model: Optional[str], key_prefix: Optional[str]) -> dict:
    """构造 parse_agent_output 的 env_summary（开头运行信息摘要上下文）。"""
    return {
        "model": agent_model or "",
        "key_prefix": key_prefix or "",
        "mcp_servers": _list_agent_mcp_servers(),
    }


def _resolve_skill_source_path(skill_name: str) -> Optional[str]:
    """
    在 server/assets/ai-agent/{x86,arm}/.pi/agent/skills/<skill_name>/SKILL.md
    里寻找 SKILL.md 的源文件绝对路径，优先匹配 host 架构。

    找不到返回 None（assets 资产树缺失或 arch 不对）。

    注意：MODULE_PATH 指向 <root>/server/，资产在其下的 assets/ai-agent。
    """
    if not _AGENT_ASSETS_ROOT:
        return None
    candidates: list[str] = []
    # 优先 host arch
    host_arch = platform.machine().lower()
    if host_arch in ('x86_64', 'amd64'):
        candidates.append('x86')
    elif host_arch in ('aarch64', 'arm64'):
        candidates.append('arm')
    # 兜底顺序（一般不会到这里）
    for fallback in ('x86', 'arm'):
        if fallback not in candidates:
            candidates.append(fallback)

    for arch in candidates:
        skill_src = os.path.join(
            _AGENT_ASSETS_ROOT, arch,
            '.pi', 'agent', 'skills', skill_name, 'SKILL.md',
        )
        if os.path.isfile(skill_src):
            return skill_src
    return None


def _ensure_skill_in_repo(user_name, dir_id, skill_name: str) -> bool:
    """
    总是贴皮覆盖式：把 SKILL.md 从 server/assets/ai-agent/<arch>/.pi/agent/skills
    复制到 <repo>/.skills/<skill_name>/SKILL.md，确保：

      1. 老镜像（codemig-agent-base:1.0.0 没烘焙 skills）：cp 之后 agent 看到 skill
      2. 新镜像（已经烘焙 skills）：cp 是覆盖式，容器内 ~/.pi/skills/<name>/
         最终以 /app/.skills/ 里的版本为准，保证单一来源真理可控
      3. 无论镜像状态如何，按下按钮都能稳定工作

    返回 True 表示 SKILL.md 已落到仓库；False 表示资产树的 SKILL.md 缺失或落盘失败。
    """
    skill_src = _resolve_skill_source_path(skill_name)
    if not skill_src:
        LOGGER.error(
            f"[{skill_name}] 找不到源 SKILL.md："
            f"server/assets/ai-agent/<arch>/.pi/agent/skills/{skill_name}/SKILL.md 不存在。"
            f"host_arch={platform.machine()}。请确认项目 assets/ 已就绪，"
            f"或重建 codemig-agent-base 镜像：bash server/assets/ai-agent/build_docker.sh <x86|arm>"
        )
        return False

    try:
        repo_path = get_repo_path(user_name, dir_id)
    except Exception as e:
        LOGGER.error(f"[{skill_name}] get_repo_path failed: {e}")
        return False

    skill_dir = os.path.join(str(repo_path), ".skills", skill_name)
    skill_file_path = os.path.join(skill_dir, "SKILL.md")
    try:
        # 分步创建：先 mkdir -p repo_path（用户工作目录可能不存在），
        # 再 mkdir -p .skills/<name>。并各自 log 一次状态。
        if not os.path.isdir(str(repo_path)):
            try:
                os.makedirs(str(repo_path), exist_ok=True)
                LOGGER.info(f"[{skill_name}] 创建 repo 目录：{repo_path}")
            except OSError as e:
                LOGGER.error(f"[{skill_name}] 无法创建 repo_path={repo_path}: {e}")
                return False
        try:
            os.makedirs(skill_dir, exist_ok=True)
        except OSError as e:
            LOGGER.error(
                f"[{skill_name}] 无法创建 skill_dir={skill_dir}（repo_path 存在={os.path.isdir(str(repo_path))}, "
                f"可写={os.access(str(repo_path), os.W_OK)}, 当前权限={oct(os.stat(str(repo_path)).st_mode)[-3:]}): {e}"
            )
            return False

        if not os.path.isdir(skill_dir):
            LOGGER.error(
                f"[{skill_name}] skill_dir 创建后仍不存在：{skill_dir}"
            )
            return False

        # 复制 + 中间嵌入中文守则（user-facing 输出强制简体中文，避免 SKILL.md 走样）
        with open(skill_src, 'r', encoding='utf-8') as src_f:
            original = src_f.read()
        enforced = _enforce_chinese_output(skill_name, original)
        with open(skill_file_path, 'w', encoding='utf-8') as dst_f:
            dst_f.write(enforced)
        LOGGER.info(
            f"[{skill_name}] SKILL.md 落盘（贴皮覆盖式）：{skill_src} → {skill_file_path}"
        )
        return True
    except OSError as e:
        LOGGER.error(
            f"[{skill_name}] Failed to write SKILL.md: {e} "
            f"(skill_dir 存在={os.path.isdir(skill_dir)}, "
            f"skill_dir 可写={os.access(skill_dir, os.W_OK) if os.path.isdir(skill_dir) else 'N/A'})"
        )
        return False


def _enforce_chinese_output(skill_name: str, original: str) -> str:
    """
    在从 assets 复制过来的 SKILL.md 顶部追加一段「⚠️ 语言守则」，
    强制该 skill 的所有面向用户的输出使用简体中文。
    即使原 SKILL.md 没有强调，最终落到 /app/.skills/ 的版本也会补上。
    """
    policy = """
> **⚠️ 语言守则（最高优先级，先于本 SKILL.md 的一切工作流指令，不可被覆盖）**
> 1. 你的所有输出必须全程使用简体中文（说明 / 报告 / 总结 / 错误消息 / 进度自检 / 瓶颈分析）。
> 2. **思考过程（thinking）同样必须用简体中文** —— 思考内容会原样展示给用户，禁止 "Let me ..." / "I need to ..." 式英文思考。
> 3. 任何工具（riscv-doc-mcp / 编译器输出）返回的英文片段可原样引用，但解读与落结论必须用中文。
> 4. 代码 / 命令 / 文件名 / 路径 / 汇编指令 / 寄存器名保持英文原样不动。
> 5. 禁止输出任何英文句子或英文段落（包括 "Here is ..." / "Summary:" 等开头）。中文标点用全角（，。、；：？！）。
> 6. 技术专有名词（IPC / Block RThroughput / LMUL / SEW / RVV / Zvbc 等）允许保留英文原词，但前后必须用中文叙述。
> 7. **subagent / fork 派发子任务时，指令里必须包含"用简体中文汇报"** —— 子任务不继承本对话的语言约定，英文指令会导致子代理用英文回复。
> 8. 本 SKILL.md 后文的一切工作流指令均以本守则为前提。

"""
    # 简单实现：找到 YAML frontmatter 末尾（'---' + 换行）或全文最前，把 policy 接在它之后
    # 这样不会破坏 YAML frontmatter 解析
    lines = original.split('\n')
    in_yaml = False
    yaml_close = -1
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if not in_yaml:
                in_yaml = True
            else:
                yaml_close = i
                break
    if yaml_close > 0:
        new_lines = lines[:yaml_close + 1] + ['', ''] + policy.strip().split('\n') + lines[yaml_close + 1:]
    else:
        new_lines = [policy.strip(), ''] + lines
    return '\n'.join(new_lines)


def _write_skill_to_repo(user_name, dir_id, skill_name: str, skill_content: str) -> bool:
    """
    把 skill 写到仓库 <repo>/.skills/<skill_name>/SKILL.md，agent 启动时会 cp 到容器。

    v4.x.0-RUN-FLOW：走「总是贴皮覆盖式」策略：
      - 优先从 server/assets/ai-agent/<arch>/.pi/agent/skills/<name>/SKILL.md 复制
        （这是项目维护的真实 SKILL.md 源），并自动注入中文守则
      - 找不到源时才回退到调用方传进来的 skill_content（用于 projectmigrate 等
        动态合成 skill）

    返回 True 表示 SKILL.md 已落盘（无论是哪种来源）。
    """
    # 1) 优先从 assets 复制（覆盖式 cp 之前先归一化源）
    if _ensure_skill_in_repo(user_name, dir_id, skill_name):
        return True

    # 2) 兜底：用调用方传的 skill_content（projectmigrate 等）
    if not skill_content:
        LOGGER.error(f"[{skill_name}] SKILL.md 源缺失且未传入 skill_content")
        return False
    try:
        repo_path = get_repo_path(user_name, dir_id)
    except Exception as e:
        LOGGER.error(f"[{skill_name}] get_repo_path failed: {e}")
        return False

    skill_text = skill_content.format(platform="Linux")
    skill_dir = os.path.join(str(repo_path), ".skills", skill_name)
    skill_file_path = os.path.join(skill_dir, "SKILL.md")
    try:
        os.makedirs(skill_dir, exist_ok=True)
        with open(skill_file_path, 'w', encoding='utf-8') as f:
            f.write(skill_text)
        return True
    except OSError as e:
        LOGGER.error(f"[{skill_name}] Failed to write SKILL.md: {e}")
        return False


def _build_skill_runner(skill_name: str, prompt_template: str, stage_label_cn: str,
                        skill_content: Optional[str] = None,
                        inject_skill_via_repo: bool = True):
    """
    通用阶段执行器：被 ② 功能验证（uttest）复用。

    参数：
      - skill_content：动态合成 skill 的内容（如 projectmigrate）；None 表示
        「使用已存在 / 已烘焙」的 skill（uttest / migrate /
        asmrepair）。详见 _write_skill_to_repo 的注释。
      - inject_skill_via_repo：是否走 SKILL.md 落盘 + cp 流程。
          True  （默认，projectmigrate）：
              _write_skill_to_repo 写 /app/.skills/<name>/SKILL.md，
              _create_project_agent_process 用 cp -r 注入容器。
          False （v4.x 推荐用于 uttest）：
              **完全跳过 SKILL.md 写入和 cp**，agent 在 prompt 里已经自带完整工作流。
              适用：触发 prompt 本身已经详细到工作流级别（agent 可独立完成）。
              好处：消除「写盘失败」「目录权限」「assets 找不到」等一系列失败点。

    共同步骤：
      - 启动一个项目 Agent 进程，跑对应的 skill 工作流
      - 流式返回 Agent 输出
      - 完成后对全部迁移文件 rescan + commit（与一键迁移一致）
    """
    def _handler(parameters, request):
        suggestion = ''
        start_time = time.time()

        user_id = getattr(request, 'user_id', None)
        user_name = parameters.get("user_name")
        task_id = parameters.get("task_id")
        dir_id = parameters.get("dir_id")
        model = parameters.get("agent_model")
        api_format = parameters.get("api_format")
        request_uuid = parameters.get("request_uuid")

        if request_uuid is None or len(request_uuid) < 1:
            return Response(
                to_line(AiDataStatus.NO_REQUEST_UUID, "There is no request uuid"),
                mimetype='application/json')

        user = _validate_user(user_id, user_name)
        if not user:
            return Response(
                to_line(AiDataStatus.BACKEND_ERROR, "Unknown user."),
                mimetype='application/json')

        try:
            # 1. 注入阶段 skill
            #    v4.x：默认走「贴皮覆盖式」—— _write_skill_to_repo 把 SKILL.md 写
            #    到 <repo>/.skills/<name>/SKILL.md（优先从 assets 复制，兜底
            #    用 skill_content），_create_project_agent_process 再 cp 进容器。
            #    当 inject_skill_via_repo=False 时（uttest）：
            #      - 完全跳过 _write_skill_to_repo（避免目录权限 / assets 缺失问题）
            #      - _create_project_agent_process 也不会 cp
            #      - agent 触发 prompt 已经自带完整工作流（见 uttest_prompt_template
            #        各自的 prompt_template），不再依赖容器内独立 SKILL.md
            if inject_skill_via_repo:
                skill_md_target = os.path.join(
                    str(get_repo_path(user.user_name, dir_id)),
                    '.skills', skill_name, 'SKILL.md',
                )
                write_ok = _write_skill_to_repo(
                    user.user_name, dir_id, skill_name,
                    skill_content or '',
                )
                if not write_ok:
                    arch_hint = platform.machine().lower()
                    # 完整上下文（skill 名 / 落盘路径 / 架构）只进服务端日志，
                    # 不回传前端，避免泄露仓库路径等敏感信息
                    LOGGER.error(
                        f"[{stage_label_cn}] 注入 skill 失败：{skill_name} SKILL.md 无法落到 {skill_md_target}。\n"
                        f"可能原因：assets/ai-agent/ 缺失 / 目录权限 / 后端未重启。\n"
                        f"host_arch={arch_hint}。"
                    )
                    return Response(
                        to_line(AiDataStatus.BACKEND_ERROR,
                                f"[{stage_label_cn}] 注入运行环境失败，"
                                "可能原因：assets/ai-agent/ 缺失 / 目录权限 / 后端未重启，"
                                "请联系管理员查看服务端日志。"),
                        mimetype='application/json')

                if not os.path.isfile(skill_md_target):
                    LOGGER.error(
                        f"[{stage_label_cn}] {skill_name} SKILL.md 写入返回成功但磁盘上不存在：{skill_md_target}。"
                        f"请检查目录权限或重启 server。"
                    )
                    return Response(
                        to_line(AiDataStatus.BACKEND_ERROR,
                                f"[{stage_label_cn}] 运行环境写入异常，"
                                "请检查目录权限或重启 server，"
                                "详情请联系管理员查看服务端日志。"),
                        mimetype='application/json')
            else:
                # 不做 SKILL.md 写入 / cp；完全靠 prompt 驱动 agent。
                LOGGER.info(
                    f"[{stage_label_cn}] inject_skill_via_repo=False，跳过 SKILL.md 落盘与 cp；"
                    f"agent 用 prompt_template 自带的工作流执行"
                )

            # 2. 校验 file_list（必须有产物才能跑 ②③）
            # 不传 prompt_to_write：.prompt.txt 留给 _create_project_agent_process 按
            # prompt_template（uttest 等）补写，避免这里把
            # projectmigrate_prompt_template 错误地写进 .prompt.txt。
            _, file_list = _build_projectmigrate_prompt(
                user.user_name, dir_id, manual_items=None, task_id=task_id)
            if not file_list:
                suggestion = (
                    f"[{stage_label_cn}] 当前目录没有可用迁移产物。"
                    "请先完成「代码生成」阶段。"
                )
                return Response(
                    to_line(AiDataStatus.UNKNOWN_ERROR, suggestion),
                    mimetype='application/json')

            # 3. 取 Agent 配置
            is_admin = user.role == 'admin'
            agent_config = get_agent_config_from_db(
                model, user_id=user_id, is_admin=is_admin) if model else None
            if not agent_config or not isinstance(agent_config, dict) or not agent_config.get("api_key"):
                suggestion = (agent_config.get("msg")
                              if isinstance(agent_config, dict)
                              else "未找到可用的 API Key 配置")
                return Response(
                    to_line(AiDataStatus.BACKEND_ERROR, suggestion or "未找到可用的 API Key 配置"),
                    mimetype='application/json')

            # 3.5 【v4.x.0-PROMPT-PRE-COMMIT】在 commit 之前把 prompt 写到
            #      <repo>/.prompt.txt，让后续 commit_git_repo(stage:before) 的
            #      git add -A 把它收进 commit，避免 restore_workspace /
            #      reset_to_commit 的 `git clean -fd` 把它当未跟踪文件干掉。
            #      一键迁移路径走的是 _build_projectmigrate_prompt 的
            #      prompt_to_write 通道（同样目标）；uttest
            #      这里走自己的 prompt_template。
            repo_path_for_prompt = get_repo_path(user.user_name, dir_id)
            if not _write_prompt_to_repo_for_commit(
                str(repo_path_for_prompt), prompt_template,
                request_uuid=request_uuid, stage_label=stage_label_cn,
            ):
                suggestion = (
                    f"[{stage_label_cn}] 写入 .prompt.txt 失败，无法启动 agent"
                )
                LOGGER.error(suggestion)
                return Response(
                    to_line(AiDataStatus.BACKEND_ERROR, suggestion),
                    mimetype='application/json')

            # 4. v3.2 改造：移除 agent-start-{skill_name} commit，
            #    由前端 _preBoundaryCommit('user-click-run-{stage}') 替代。
            #    理由字符串仍保留在 COMMIT_REASON_WHITELIST 内以便向后兼容
            #    解析旧的 commit message；前端 label 已迁移到 boundary 系列。
            # before_status, before_result = commit_git_repo(
            #     user.user_name, dir_id,
            #     "ai", "before",
            #     src="codemig-agent",
            #     reason=f"agent-start-{skill_name}",
            # )
            before_status = True
            before_result = None
            before_hash = None  # v3.2：不再产生 before_hash，interrupted 分支不再依赖它

            # 5. 拉起项目 Agent，注入对应 skill
            repo_path = get_repo_path(user.user_name, dir_id)
            cmd_list = []
            # v4.x.0-RESUME：所有路径都先 ensure 命名卷，让 pi 把 session 写到卷里，
            # 中断后卷仍在，下次"继续"可被挂回。
            named_volume = _migrate_named_volume_name(
                user.user_name, dir_id, skill_name,
            )
            try:
                _ensure_named_volume(named_volume)
            except Exception as e:
                LOGGER.error(f"[resume] 命名卷 {named_volume} 创建失败（继续）: {e}")
            resume_flag = bool(parameters.get('_resume', False))
            if resume_flag:
                if not _maybe_prepare_resume(
                    user.user_name, dir_id, skill_name, named_volume,
                ):
                    suggestion = (
                        f"[{stage_label_cn}] 当前阶段无 pi 会话存档可继续，"
                        "请直接点击「运行」重新启动"
                    )
                    return Response(
                        to_line(AiDataStatus.BACKEND_ERROR, suggestion),
                        mimetype='application/json')
            process = _create_project_agent_process(
                prompt_template, str(repo_path), agent_config,
                request_uuid, cmd_list, api_format,
                skill_name=skill_name,
                inject_skill=inject_skill_via_repo,
                resume=resume_flag,
                named_volume=named_volume,)
            cmd = " ".join(cmd_list) if cmd_list else ""
            # v4.x：写入阶段标记，前端刷新恢复/历史切换按阶段过滤。
            # skill_name → 规范阶段 id（与前端 flowNodes id 一致）：
            #   uttest → ut_test
            stage_id = {'uttest': 'ut_test'}.get(skill_name, skill_name)
            create_ai_info_to_database(
                user.user_name, dir_id, 0, request_uuid, str(repo_path), model, cmd,
                stage=stage_id)

            _key_prefix = (agent_config.get("api_key") or "")[:3] if agent_config else ""

            # 6. 流式返回（完成后对全部迁移文件 rescan + commit）
            return Response(
                generate_project_agent_response(
                    process, user.user_name, dir_id, file_list, request_uuid, start_time,
                    agent_model=model, key_prefix=_key_prefix, before_hash=before_hash,
                ),
                mimetype='application/json')

        except FileNotFoundError as e:
            save_intermediate_state_on_failure(user.user_name, dir_id, reason='intermediate-error')
            suggestion = str(e)
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user.user_name, dir_id, suggestion, request_uuid, run_time)
            return Response(
                to_line(AiDataStatus.BACKEND_ERROR, suggestion),
                mimetype='application/json')
        except Exception as e:
            save_intermediate_state_on_failure(user.user_name, dir_id, reason='intermediate-error')
            LOGGER.error(f"[{skill_name}] error: {e}", exc_info=True)
            suggestion = str(e)
            end_time = time.time()
            run_time = end_time - start_time if start_time else 0
            update_ai_exception(user.user_name, dir_id, suggestion, request_uuid, run_time)
            return Response(
                to_line(AiDataStatus.BACKEND_ERROR, suggestion),
                mimetype='application/json')

    return _handler


# ② 功能验证（uttest skill — 来源 server/assets/ai-agent/<arch>/.pi/agent/skills/uttest/SKILL.md）
run_ut_test = _build_skill_runner(
    skill_name='uttest',
    prompt_template=uttest_prompt_template,
    stage_label_cn='功能验证',
    # v4.x：inject_skill_via_repo=False 完全跳过 SKILL.md 落盘与 cp，
    # agent 直接靠 prompt_template 自带的工作流执行，不依赖容器内是否有独立 skill。
    # 消除「写盘失败」「目录权限」「assets 找不到」等失败点。
    inject_skill_via_repo=False,
)


def _rescan_all_files(user_name, dir_id, file_list):
    """Agent 完成后，对所有被迁移的文件执行 rescan"""
    for file_info in file_list:
        file_id = file_info["file_id"]
        try:
            rescan_file(user_name, dir_id, file_id)
        except Exception as e:
            LOGGER.error(f"Rescan file failed: file_id={file_id}, error={e}")


def generate_project_agent_response(process: subprocess.Popen, user_name: str,
                                   dir_id: int, file_list: list, request_uuid=None,
                                   start_time=None, agent_model=None, key_prefix=None,
                                   before_hash=None):
    """生成项目级 Agent 响应流（复用 parse_agent_output，finally 中对全部文件 rescan）

    与 generate_agent_response 的区别：
    - file_id 为 None 时 generate_agent_response 不执行 git commit / rescan
    - 本函数在 finally 中对所有 file_list 中的文件执行 rescan + git commit
    - interrupted 时使用 before_hash 自动回滚工作区到迁移前状态
    """
    log_path = os.path.join(get_codemig_data_path(), user_name, str(dir_id), "agent_"+request_uuid+".log")
    if os.path.exists(log_path):
        os.remove(log_path)
    suggestion = ''
    interrupted = False
    # ★ 失败标记：parse_agent_output 在流内 yield 的 BACKEND_ERROR / TIMEOUT /
    #   UNKNOWN_ERROR（如 pi 启动即死 Unknown provider、agent 崩溃无 result）。
    #   不捕获的话 finally 只认 interrupted，会把失败也写成 stage-end-success
    #   marker，前端刷新后误显示「已完成」。
    agent_failed = False
    try:
        if agent_model is not None:
            key_info = json.dumps({"model": agent_model, "key_prefix": key_prefix or ''},
                                  ensure_ascii=False)
            yield to_line(AiDataStatus.AGENT_KEY_INFO, key_info)
        yield to_line(AiDataStatus.RECEIVING_RESULT, "</think>")
        info = parse_agent_output(process, container_name=f"docker_{request_uuid}",
                                  env_summary=_build_env_summary(agent_model, key_prefix))
        with open(log_path, 'a', encoding='utf-8') as f:
            for chunk in info:
                try:
                    data = json.loads(chunk.decode('utf-8').strip())
                    # 流内错误状态行（负值）：agent 未正常结束的权威信号
                    if isinstance(data.get('status'), int) and data['status'] < 0:
                        agent_failed = True
                    value = data.get('value', '')
                    if value:
                        f.write(value)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                yield chunk
    except (OSError, UnicodeDecodeError, subprocess.SubprocessError) as e:
        suggestion = str(e)
        raise
    except GeneratorExit:
        interrupted = True
    finally:
        try:
            cleanup_process(process, container_name=f"docker_{request_uuid}")
        except Exception:
            pass
        finished_status = "interrupted" if interrupted else (
            "abnormal" if agent_failed else "completed")

        if interrupted:
            LOGGER.info(f"Project agent stream interrupted (user={user_name}, dir_id={dir_id})")
            # 用户手动停止：把 Agent 半成品作为"中间态"留痕到 git 历史，工作区不 reset，
            # 让用户在 IDE/历史下拉框里能看到 Agent 当前写到的状态。
            # 历史下拉框可手动跳到此 commit 之前的 before commit 以彻底回退。
            # v3.2 改造：统一调 force_commit_marker 工厂（reason='stage-end-cancel'），
            # 不再行内 _repo.index.commit，避免重复 GitPython try/except 模板。
            # v6.0.0-ROLLBACK-NONCE：删掉 v5 的 frontier_nonce 透传，强制写
            # stage-end-cancel marker（与前端的 stage-end-cancel 区分靠 src）。
            force_commit_marker(
                user_name, dir_id,
                reason='stage-end-cancel',
                src='codemig-agent', stage='end', type='marker',
            )
        elif agent_failed:
            # ★ 失败路径：parse_agent_output 在流内 yield 过错误状态（agent 崩溃 /
            #   pi 启动即死 Unknown provider / 无 result 行）。写 stage-end-error
            #   marker，让前端刷新后如实显示「失败」而非「已完成」。
            #   半成品仍由 force_commit_marker 收进 git 历史留痕。
            LOGGER.warning(
                f"Project agent failed (user={user_name}, dir_id={dir_id}): "
                f"error status seen in stream")
            force_commit_marker(
                user_name, dir_id,
                reason='stage-end-error',
                src='codemig-agent', stage='end', type='marker',
            )
        else:
            # 插入新增文件（使用 file_list 中第一个 file_id 作为 source_file_id）
            if file_list:
                source_file_id = file_list[0]["file_id"]
                status, msg = insert_generated_files_to_database(user_name, dir_id, source_file_id)
                if status:
                    LOGGER.info(f"Inserted new files after project agent completion")
                else:
                    LOGGER.warning(f"Failed to insert new files: {msg}")

            # v3.2 改造：调 force_commit_marker（force=True）强制 commit，
            # 不依赖 is_dirty 守卫。即使 working tree 完全 clean，也会留一条
            # 'stage-end-success' marker，让 git log 形成完整闭环。
            # v6.0.0-ROLLBACK-NONCE：删掉 v5 的 frontier_nonce 透传，无条件写
            # stage-end-success marker（与前端的 stage-end-success 区分靠 src）。
            force_commit_marker(
                user_name, dir_id,
                reason='stage-end-success',
                src='codemig-agent', stage='end', type='marker',
            )
            # 旧代码（保留注释，便于回滚）：
            # status, msg = commit_git_repo(
            #     user_name, dir_id,
            #     "ai", "after",
            #     src="codemig-agent",
            #     reason="agent-finish",
            # )
            # if status:
            #     LOGGER.info(f"Saved git state after project agent completion")
            # else:
            #     LOGGER.warning(f"Failed to save git state: {msg}")

            # 对所有文件执行 rescan
            _rescan_all_files(user_name, dir_id, file_list)

        # 更新 AI 结果到数据库
        end_time = time.time()
        if interrupted:
            # 用户手动停止：保留 AI 在被中断前已流出的内容（log 中 value 拼接），
            # 末尾追加 "用户已停止" 标识本次任务未完成。
            # 注：log 里可能含未闭合的 <details>（GeneratorExit 后 parse_agent_output
            # 不能再 yield 补闭合标签），由下方 truncate_suggestion_for_db 入库前统一清洗。
            if len(suggestion) == 0 and os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        suggestion = f.read()
                except Exception as e:
                    LOGGER.error(f"Failed to read log file: {e}")
                    suggestion = ''
            if not suggestion.endswith('\n\n'):
                suggestion = suggestion.rstrip('\n') + '\n\n'
            suggestion += '用户已停止'
        elif len(suggestion) == 0 and os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    suggestion = f.read()
            except Exception as e:
                LOGGER.error(f"Failed to read log file: {e}")
                suggestion = f"Failed to read log file: {str(e)}"

        run_time = end_time - start_time if start_time else 0
        update_ai_result(user_name, dir_id, request_uuid, run_time,
                         truncate_suggestion_for_db(suggestion), finished_status)
        if os.path.exists(log_path):
            # suggestion 已存到数据库，可以删除记录文件
            os.remove(log_path)


def query_project_migrate(parameters, request):
    """
    项目级一键迁移入口函数。

    复用现有 Agent 流程，区别在于：
    1. 挂载整个项目仓库到 Docker（而非单文件目录）
    2. 迁移清单写入 scan_result.json，迁移工作流写入 projectmigrate skill
    3. prompt 极简化为一句话触发 skill，Agent 通过 skill + JSON 自主完成迁移
    4. Agent 完成后对所有文件执行 rescan

    Args:
        parameters: 请求参数
        request: Flask 请求对象

    Returns:
        Response: 流式 AI 响应
    """
    suggestion = ''
    start_time = time.time()

    user_id = request.user_id
    user_name = parameters.get("user_name")
    task_id = parameters.get("task_id")
    dir_id = parameters.get("dir_id")
    model = parameters.get("agent_model")
    api_format = parameters.get("api_format")
    request_uuid = parameters.get("request_uuid")

    if request_uuid is None or len(request_uuid) < 1:
        return Response(
            to_line(AiDataStatus.NO_REQUEST_UUID, "There is no request uuid"),
            mimetype='application/json')

    user = _validate_user(user_id, user_name)
    if not user:
        return Response(
            to_line(AiDataStatus.BACKEND_ERROR, "Unknown user."),
            mimetype='application/json')

    try:
        # 1. 构建项目级 prompt
        # 从请求参数中获取用户手动选中的代码段
        manual_items = parameters.get("manual_items", [])
        # 一键迁移路径：显式传 projectmigrate_prompt_template，让 .prompt.txt
        # 与 .skills/projectmigrate/SKILL.md 在同一阶段产出，被后续
        # commit_git_repo(stage:before) 的 git add -A 一并收进 commit，
        # 避免 restore_workspace / reset_to_commit 的 `git clean -fd` 杀掉。
        content, file_list = _build_projectmigrate_prompt(
            user.user_name, dir_id, manual_items, task_id=task_id,
            prompt_to_write=projectmigrate_prompt_template)
        if not content or not file_list:
            suggestion = "无法获取项目迁移文件清单，可能没有需要迁移的文件"
            return Response(
                to_line(AiDataStatus.UNKNOWN_ERROR, suggestion),
                mimetype='application/json')

        # 2. 获取 Agent 配置
        is_admin = user.role == 'admin'
        agent_config = get_agent_config_from_db(
            model, user_id=user_id, is_admin=is_admin) if model else None
        if not agent_config or not isinstance(agent_config, dict) or not agent_config.get("api_key"):
            suggestion = (agent_config.get("msg")
                          if isinstance(agent_config, dict)
                          else "未找到可用的 API Key 配置")
            return Response(
                to_line(AiDataStatus.BACKEND_ERROR, suggestion or "未找到可用的 API Key 配置"),
                mimetype='application/json')

        # 3. v3.2 改造：删除 commit_git_repo('agent-start')——前端 _preBoundaryCommit
        #    ('user-click-run-migrate') 已经产生等价的锚点（src=codemig-boundary），
        #    再产生 'agent-start' 会同语义双 commit。before_hash 保留为 None 是
        #    为了维持 generate_project_agent_response(..., before_hash=before_hash)
        #    接口兼容。
        #    v6.0.0-ROLLBACK-NONCE：彻底删掉 v5 的 nonce 透传。
        before_hash = None

        # 4. 挂载整个项目仓库（而非单文件目录）
        repo_path = get_repo_path(user.user_name, dir_id)

        # 5. 创建 Agent 进程（使用项目级专用函数，先注入 skill 再启动 agent）
        cmd_list = []
        # v4.x.0-RESUME：所有路径都先 ensure 命名卷，让 pi 把 session 写到卷里，
        # 中断后卷仍在，下次"继续"可被挂回。
        named_volume = _migrate_named_volume_name(
            user.user_name, dir_id, 'projectmigrate',
        )
        try:
            _ensure_named_volume(named_volume)
        except Exception as e:
            LOGGER.error(f"[resume] 命名卷 {named_volume} 创建失败（继续）: {e}")
        resume_flag = bool(parameters.get('_resume', False))
        if resume_flag:
            if not _maybe_prepare_resume(
                user.user_name, dir_id, 'projectmigrate', named_volume,
            ):
                suggestion = (
                    "当前一键迁移无 pi 会话存档可继续，请直接点击「运行」重新启动"
                )
                return Response(
                    to_line(AiDataStatus.BACKEND_ERROR, suggestion),
                    mimetype='application/json')
        process = _create_project_agent_process(
            content, str(repo_path), agent_config, request_uuid, cmd_list, api_format,
            skill_name='projectmigrate',
            resume=resume_flag,
            named_volume=named_volume,)
        cmd = " ".join(cmd_list) if cmd_list else ""
        # file_id=0 作为项目级迁移的固定标记，满足 NOT NULL 约束且不与真实文件冲突（真实 file_id >= 1）
        # v4.x：stage='project_migrate' 阶段标记，前端刷新恢复/历史切换按阶段过滤
        create_ai_info_to_database(
            user.user_name, dir_id, 0, request_uuid, str(repo_path), model, cmd,
            stage='project_migrate')

        _key_prefix = (agent_config.get("api_key") or "")[:3] if agent_config else ""

        # 6. 流式返回 Agent 响应（使用项目级专用流式生成器，完成后 rescan 全部文件）
        return Response(
            generate_project_agent_response(
                process, user.user_name, dir_id, file_list, request_uuid, start_time,
                agent_model=model, key_prefix=_key_prefix, before_hash=before_hash,
            ),
            mimetype='application/json')

    except FileNotFoundError as e:
        save_intermediate_state_on_failure(user.user_name, dir_id, reason='intermediate-error')
        suggestion = str(e)
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user.user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(
            to_line(AiDataStatus.BACKEND_ERROR, suggestion),
            mimetype='application/json')
    except Exception as e:
        save_intermediate_state_on_failure(user.user_name, dir_id, reason='intermediate-error')
        LOGGER.error(f"Project migrate error: {e}", exc_info=True)
        suggestion = str(e)
        end_time = time.time()
        run_time = end_time - start_time if start_time else 0
        update_ai_exception(user.user_name, dir_id, suggestion, request_uuid, run_time)
        return Response(
            to_line(AiDataStatus.BACKEND_ERROR, suggestion),
            mimetype='application/json')


def rescan_file(user_name, dir_id, file_id):
    status, info = query_file_info_from_database(user_name, dir_id, file_id)
    if not status:
        LOGGER.error(f"Can't find file {file_id} in database")
        return False
    file_path, source, bremoved, isfile = info
    if not os.path.exists(file_path):
        LOGGER.error(f"File {file_path} not exists.")
        return False
    if os.path.isdir(file_path):
        LOGGER.warning(f"This is a directory!!! [{file_path}]")
        return False
    if source != FileSource.CHANGED.value:
        return False

    my_changes = process_updated_file(file_id, file_path)
    status = update_file_suggestion_to_database(user_name, dir_id,
                                                file_id, my_changes)
    if not status:
        LOGGER.error("Update suggestion failed when rolling back file.")
        return False

    return True


def save_intermediate_state_on_failure(user_name, dir_id, reason='intermediate-error'):
    """异常路径下的中间态留痕（V7 改造）

    与 generate_project_agent_response / ②③ skill handler 的 finally 块共用的
    强制 commit 路径同源：
      - 不调 restore_workspace（异常 / 取消时保留 agent 半成品）
      - 即使 working tree clean，也产生一条 reflog 节点 commit
      - 用 add -A 把 dirty 全部收进去（不依赖 is_dirty guard）

    Args:
        user_name, dir_id: 用户与目录
        reason: commit reason（必须在 common_git.COMMIT_REASON_WHITELIST 内），
                caller 可显式传入如 'intermediate-error'（默认）。
    """
    try:
        from git import Repo as _Repo
        from git.exc import InvalidGitRepositoryError as _InvalidErr
        _code_path = get_repo_path(user_name, dir_id)
        _repo = _Repo(str(_code_path))
        _repo.git.add(all=True)
        _sha = _repo.index.commit(
            message=f"Save type:ai stage:before src:codemig-agent reason:{reason}",
            author=_repo.head.commit.author,
        ).hexsha
        LOGGER.info(f"Saved intermediate state on failure (reason={reason}, hash={_sha[:8]})")
        try:
            _diff = _repo.git.execute(
                ['git', 'diff', '--name-only', '--diff-filter=ACMRT', 'HEAD~1', 'HEAD']
            ).strip()
            LOGGER.info(f"Intermediate commit file list: {_diff or '(no changed files)'}")
        except Exception:
            pass
    except ImportError:
        LOGGER.warning("GitPython not installed; skipped intermediate commit")
    except _InvalidErr:
        LOGGER.warning(f"Repo at {get_repo_path(user_name, dir_id)} is not a git repo; skipped")
    except Exception as e:
        LOGGER.warning(f"Failed to save intermediate state on failure: {e}")


def force_commit_marker(user_name, dir_id, reason, *,
                        src='codemig-agent', stage='marker', type='marker'):
    """硬边界 commit 工厂（v3.2 改造产物 + v6.0.0-ROLLBACK-NONCE）

    智能分流 add 策略：
      - src='codemig-boundary'（前端用户动作触发）：
          用 git add -u（只 add 已跟踪文件）
          避免"用户点了个按钮，神秘保存了我的草稿"的心理错乱
      - 其他 src（后端兜底 / agent-finish / interrupted）：
          用 git add -A（全量 add）
          保护 .skills/ / .prompt.txt 等关键文件不被 clean -fd 删掉

    无论工作区 dirty 与否，都产生一条 commit（allow_empty=True）。

    ★ v6.0.0-ROLLBACK-NONCE：删掉 v5.0.0-DEDUP 的 nonce 去重机制。
       v5 设计的"用 #nonce=<x> 后缀 + git log -1 检测去重"在续行场景下会
       错误跳过 step-5 后端 finally 的 success marker（pre-resume 写 N2 后，
       backend finally 也用 N2 查 HEAD 含 N2 → SKIP → 失败）。
       改为：pre / post / finally 三次 commit 全靠 reason 区分（都是不同语义，
       本来就该共存），历史多 1 条 commit 不影响任何业务逻辑。

    Args:
        user_name, dir_id: 用户与目录
        reason: 语义 reason，必须在 common_git.COMMIT_REASON_WHITELIST 内
        src: 触发来源（默认 'codemig-agent' 后端；前端传 'codemig-boundary'）
        stage: 'marker' / 'before' / 'after' / 'end'
        type: 'marker' / 'ai' / 'manual'

    Returns:
        str | None: commit hexsha（失败返回 None，不抛异常）
    """
    try:
        from git import Repo as _Repo
        from git.exc import InvalidGitRepositoryError as _InvalidErr
        _code_path = get_repo_path(user_name, dir_id)
        _repo = _Repo(str(_code_path))

        # ★ v3.2 核心：add 策略分流
        # 注：GitPython 的 repo.git.add(*args, **kwargs) 会把所有 kwargs 转成
        #     "--{key}" 长选项，所以 _repo.git.add('-u', all=True) 实际展开为
        #     "git add --all -u"，git 会报 'fatal: -A and -u are mutually
        #     incompatible'。只能用位置参数 '-u'（即 git add --update）。
        if src == 'codemig-boundary':
            # 前端用户动作触发：只 add 已跟踪文件的修改/删除
            # （-u = --update；不 add 新文件 → 不"神秘保存"草稿）
            _repo.git.add('-u')
        else:
            # 后端兜底：全量 add（保护 .skills/、.prompt.txt 等关键文件）
            _repo.git.add(all=True)

        # 拼接 message（不带 nonce 后缀——v6 彻底回滚）
        _message = f"Save type:{type} stage:{stage} src:{src} reason:{reason}"

        # ★ 走 git CLI 才能传 --allow-empty；IndexFile.commit 是 GitPython
        #   的 Python 层 commit，没有 allow_empty 参数，会 TypeError。
        _repo.git.commit(
            m=_message,
            author=_repo.head.commit.author,
            allow_empty=True,
        )
        # commit 成功后 head 已指向新 commit，直接读 hexsha 最可靠
        # （避免解析 _repo.git.commit() 返回的 stdout——形如 "[branch hash] message\n stats"）
        _sha = _repo.head.commit.hexsha
        add_strategy = 'git add -u' if src == 'codemig-boundary' else 'git add -A'
        LOGGER.info(
            f"Force-committed marker: reason={reason} src={src} "
            f"add_strategy={add_strategy} hash={_sha[:8]}"
        )
        return _sha
    except ImportError:
        LOGGER.warning("GitPython not installed; skipped force commit")
    except _InvalidErr:
        LOGGER.warning(f"Repo at {get_repo_path(user_name, dir_id)} is not a git repo; skipped")
    except Exception as e:
        LOGGER.warning(f"Failed to force-commit marker (reason={reason}): {e}")
    return None


def rollback_project_migrate_handler(user_name, dir_id, target_hash=None):
    """
    项目级迁移手动回退：reset --hard 回退整个仓库。
    - target_hash=None：自动从 git log 找最近的 "type:ai stage:before" commit 作为回退点
    - target_hash 指定：直接回退到该 commit（支持 reflog 历史点回跳，即可逆回退）
    与单文件的 file_rollback_handler（调用 revert_to_last_commit 逐文件回滚）完全隔离。

    Returns:
        dict: {"code": 0/1, "msg": "..."}
    """
    try:
        from git import Repo as _Repo
        from git.exc import InvalidGitRepositoryError as _InvalidErr
    except ImportError:
        return {"code": -1, "msg": "GitPython not installed"}

    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return {"code": 1, "msg": "代码路径不存在"}

    try:
        repo = _Repo(code_path)
    except _InvalidErr:
        return {"code": 1, "msg": "Git 仓库未初始化"}
    except Exception as e:
        return {"code": 1, "msg": f"打开 Git 仓库失败: {str(e)}"}

    # 指定目标 commit：直接回跳（可逆，基于 reflog 历史点）
    if target_hash:
        target_final = target_hash
    else:
        # 未指定：遍历 commit 历史，找最近一条 type:ai stage:before
        target_final = None
        try:
            for commit in repo.iter_commits():
                msg = (commit.message or "").strip()
                if "type:ai" in msg and "stage:before" in msg:
                    target_final = commit.hexsha
                    break
        except Exception as e:
            return {"code": 1, "msg": f"遍历 Git 历史失败: {str(e)}"}

        if not target_final:
            return {"code": 1, "msg": "未找到迁移前的保存点，无法回退"}

    status, result = reset_to_commit(user_name, dir_id, target_final)
    if status:
        LOGGER.info(f"Manual rollback to {target_final[:8]} for user={user_name} dir_id={dir_id}")
        return {"code": 0, "msg": f"已回退到迁移前状态 (commit {target_final[:8]})"}
    return {"code": 1, "msg": f"回退失败: {result}"}


def list_project_migrate_history_handler(user_name, dir_id):
    """
    列出项目迁移的所有历史快照点（基于 reflog，保证回退后仍可回跳）。
    仅供一键迁移使用，与单文件迁移隔离。

    Returns:
        dict: {"code": 0, "data": [...]} 或 {"code": 1, "msg": "..."}
    """
    # 上限 200：覆盖超长任务的增量起点选择（默认 50 会截断老版本）
    status, result = list_project_history(user_name, dir_id, max_count=200)
    if status:
        return {"code": 0, "data": result}
    return {"code": 1, "msg": result}


def generate_project_patch_handler(user_name, dir_id, from_hash, to_hash=None):
    """
    生成两个 commit 之间的增量 patch（供一键迁移增量补丁导出）。
    to_hash=None 时使用当前 HEAD。与单文件迁移的全量 patch 导出隔离。

    Returns:
        dict: {"code": 0, "data": patch_string} 或 {"code": 1, "msg": "..."}
    """
    if not from_hash:
        return {"code": 1, "msg": "from_hash 不能为空"}
    status, result = generate_patch_between(user_name, dir_id, from_hash, to_hash)
    if status:
        return {"code": 0, "data": result}
    return {"code": 1, "msg": result}


# ─────────────────────────────────────────────────────────────────────
#  一键迁移：用户手动选中的代码段（v4.0）
#  - 数据源：codemig_task_directory_file_suggestion 表 is_manual=1 的行
#  - 与单文件迁移扫描器产出的建议（is_manual=0）通过 is_manual 字段正交解耦
#  - 持久化策略：单条 INSERT OR IGNORE / DELETE 由前端点击实时驱动，无需覆盖式 save
#  - rescan 由 REMOVE_SUGGESTION_OF_FILE_SQL 的 "AND is_manual=0" 天然豁免 manual 行
# ─────────────────────────────────────────────────────────────────────

# 单条插入 manual 选中段（与前端 addSelectionToManualOptions 对称）：
# is_manual=1 标识来源，type=2 表示用户手动，append_or_replace=2 表示默认占位策略。
# v4.1 扩展：列定义追加 code_too_long, code，使 DB 行格式与扫描器产出完全一致。
# 幂等实现：WHERE NOT EXISTS 按 (file_id, is_manual=1, start_line, end_line) 查重 ——
# 表上唯一约束只有自增主键 change_id 和 (file_id, change_id) 索引，INSERT OR IGNORE
# 在这条语句上永远碰不到冲突（v4.0 注释声称的幂等实际不成立），重试会插重复行。
INSERT_MANUAL_SUGGESTION_SQL = (
    "INSERT INTO codemig_task_directory_file_suggestion "
    "(file_id, type, is_manual, append_or_replace, "
    "start_line_number, end_line_number, suggestion, code_too_long, code, ignored) "
    "SELECT ?, 2, 1, ?, ?, ?, ?, ?, ?, 0 "
    "WHERE NOT EXISTS ("
    "  SELECT 1 FROM codemig_task_directory_file_suggestion "
    "  WHERE file_id = ? AND is_manual = 1 "
    "    AND start_line_number = ? AND end_line_number = ?"
    ")"
)

# 按 (file_id, start_line, end_line) 精确删除 manual 选中段
DELETE_MANUAL_SUGGESTION_BY_KEY_SQL = (
    "DELETE FROM codemig_task_directory_file_suggestion "
    "WHERE file_id = ? AND is_manual = 1 "
    "AND start_line_number = ? AND end_line_number = ?"
)


def _query_file_path_by_file_id(user_name, dir_id, file_id):
    """查 file_id → 绝对路径 file_path（用于读 manual 行原文）。"""
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path FROM codemig_task_directory_file WHERE file_id = ?",
            (file_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.warning("[manual_suggestion] file_path 查询失败: file_id=%s err=%s", file_id, err)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _read_code_range(file_path, start_line, end_line):
    """读 file_path 的 L{start}-L{end} 原始代码片段，与扫描器 extract_code() 完全一致：

        number_lines = end_line - start_line + 1
        code_too_long = (number_lines > NUMBER_LINES_TOO_LONG)

    超出 50 行时存 None（与扫描器 DB 行为完全一致）。

    Returns:
        tuple: (code_text: str|None, code_too_long: int)
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        number_lines = end_line - start_line + 1
        if number_lines > NUMBER_LINES_TOO_LONG:
            return None, CodeTooLong.CODE_TOO_LONG.value
        snippet = "".join(lines[start_line - 1:end_line])
        return snippet, CodeTooLong.HAS_SOURCE_CODE.value
    except (OSError, IOError, UnicodeDecodeError) as e:
        LOGGER.warning("[manual_suggestion] 读源码失败: file=%s L%s-%s err=%s",
                       file_path, start_line, end_line, e)
        return "", CodeTooLong.CODE_TOO_LONG.value


def insert_manual_suggestion_handler(user_name, dir_id, file_id, start_line,
                                     end_line, suggestion, append_or_replace):
    """单条插入 manual 选中段到 codemig_task_directory_file_suggestion（is_manual=1）。

    v4.1 改造：根据 file_id 自动读 L{start}-L{end} 原文并写入 code/code_too_long，
    使 DB 行格式与扫描器产出完全一致（不再依赖前端传入 code）。

    Returns:
        dict: {"code": 0, "inserted": 1/0} 或 {"code": -1, "msg": "..."}
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return {"code": -1, "msg": f"Database {db_path} not found"}

    file_path = _query_file_path_by_file_id(user_name, dir_id, file_id) or ""
    code_text, code_too_long = _read_code_range(file_path, start_line, end_line)

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(
            INSERT_MANUAL_SUGGESTION_SQL,
            # 前 7 个 ? 对应 INSERT 列；后 3 个 ? 对应 NOT EXISTS 查重条件
            (file_id, append_or_replace, start_line, end_line,
             suggestion, code_too_long, code_text,
             file_id, start_line, end_line),
        )
        inserted = cursor.rowcount
        conn.commit()
        LOGGER.info(
            "[manual_suggestion] 单条插入: user=%s dir_id=%s file_id=%s "
            "L%s-%s inserted=%s ctl=%s",
            user_name, dir_id, file_id, start_line, end_line, inserted, code_too_long,
        )
        return {"code": 0, "inserted": inserted}
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("[manual_suggestion] 单条插入失败: %s", err)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"code": -1, "msg": str(err)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def delete_manual_suggestion_handler(user_name, dir_id, file_id,
                                     start_line, end_line):
    """删除一条 manual 选中段（按 file_id + start_line + end_line 定位）。

    Returns:
        dict: {"code": 0, "deleted": N} 或 {"code": -1, "msg": "..."}
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return {"code": -1, "msg": f"Database {db_path} not found"}

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(
            DELETE_MANUAL_SUGGESTION_BY_KEY_SQL,
            (file_id, start_line, end_line),
        )
        deleted = cursor.rowcount
        conn.commit()
        LOGGER.info(
            "[manual_suggestion] 删除: user=%s dir_id=%s file_id=%s "
            "L%s-%s deleted=%s",
            user_name, dir_id, file_id, start_line, end_line, deleted,
        )
        return {"code": 0, "deleted": deleted}
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("[manual_suggestion] 删除失败: %s", err)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"code": -1, "msg": str(err)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def list_manual_suggestions_by_dir_handler(user_name, dir_id):
    """查询某 dir 下所有 manual 选中段（is_manual=1）。

    替代原 codemig_manual_selection 表的 list_manual_selections_for_projectmigrate。
    返回格式与原接口完全兼容：{"code": 0, "selections": [{"file_id", "file_path",
    "start_line", "end_line"}, ...]}，前端无需修改解析逻辑。

    Returns:
        dict: {"code": 0, "selections": [...]} 或 {"code": -1, "msg": "..."}
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return {"code": -1, "msg": f"Database {db_path} not found"}

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_MANUAL_SUGGESTIONS_BY_DIR_SQL, (dir_id,))
        rows = cursor.fetchall()
        selections = [
            {
                "file_id": r[0],
                "file_path": r[1],
                "start_line": r[2],
                "end_line": r[3],
            }
            for r in rows
        ]
        return {"code": 0, "selections": selections}
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("[manual_suggestion] 列表查询失败: %s", err)
        return {"code": -1, "msg": str(err)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
