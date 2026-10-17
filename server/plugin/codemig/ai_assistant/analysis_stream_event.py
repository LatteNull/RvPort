import os
import sys
import json

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import re
from plugin.codemig.ai_assistant.ai_data_status import AiDataStatus


def to_line(status: AiDataStatus, value: str = "") -> bytes:
    """将状态和数据转换为JSON格式的字节流"""
    data = {"status": status.value, "value": value}
    json_data = json.dumps(data, ensure_ascii=False) + "\n"
    return json_data.encode('utf-8')


def _get_action_map():
    """获取工具动作映射表"""
    return {
        "read_file": "📖 读取文件",
        "write_file": "💾 写入文件",
        "edit": "📝 编辑文件",
        "list_directory": "📂 查看目录",
        "save_memory": "🧠 保存记忆",
        "web_fetch": "🌐 访问网页",
        "glob": "🌐 全局匹配"
    }


def _handle_system_message(data):
    """处理系统初始化消息"""
    tools = data.get("tools", [])
    model = data.get("model", "")
    mcp_servers = data.get("mcp_servers") or []
    permission_mode = data.get("permission_mode", "")
    yield to_line(AiDataStatus.RECEIVING_RESULT, "🚀 **系统初始化完成**，\n")
    if model:
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"**核心模型为**{model}，\n")
    if permission_mode:
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"**权限模式为**{permission_mode}。\n\n")
    if tools:
        tools_str = ", ".join(tools)
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"🛠️ **加载工具**: {tools_str}\n")

    if isinstance(mcp_servers, list) and mcp_servers:
        lines = []
        for item in mcp_servers:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or "?"
            status = item.get("status") or "?"
            # 说明：前端展示通常是 HTML/Markdown 渲染，行首普通空格会被折叠；
            # 用不换行空格（NBSP）做缩进，确保可见。
            lines.append(f"\u00A0\u00A0\u00A0\u00A0• *{name}*：{status}")
        if lines:
            yield to_line(
                AiDataStatus.RECEIVING_RESULT,
                "\n🧩 **MCP 服务**:\n\n" + "\n".join(lines) + "\n",
            )

    # 系统初始化块结束：与后续输出分隔
    yield to_line(AiDataStatus.RECEIVING_RESULT, "\n---\n\n")

def _extract_single_path_tool_param(json_buffer, active_tool_name, action_map):
    """提取单路径类工具参数"""
    match = re.search(r'"(path|absolute_path|url|file_path)"\s*:\s*"([^"]*)', json_buffer)
    if match:
        value = match.group(2)
        action = action_map.get(active_tool_name, "操作")
        return f"{action}: {value}"
    return ""


def _extract_edit_tool_param(json_buffer, active_tool_name, action_map):
    action = action_map.get(active_tool_name, "📝 编辑文件")
    # 提取路径
    inner_data = json.loads(json_buffer)
    file_path = inner_data.get("file_path")
    old_string = inner_data.get("old_string")
    new_string = inner_data.get("new_string")
    display_content = f"{action}路径: {file_path}\n\n"
    if old_string:
        display_content += f"----原始代码----\n    ```makefile\n{old_string}\n    ```\n"
    if new_string:
        display_content += f"++++修改代码++++\n    ```makefile\n{new_string}\n    ```\n"
    return display_content


def _extract_write_file_tool_param(json_buffer, active_tool_name, action_map):
    """处理写入write_file工具，增加代码块"""
    action = action_map.get(active_tool_name, "操作")
    inner_data = json.loads(json_buffer)
    file_path = inner_data.get("file_path") or inner_data.get("path")
    content = inner_data.get("content")
    if file_path and content:
        return f"{action}路径{file_path}\n\n    ```makefile\n{content}"
    return ""


def _extract_glob_tool_param(json_buffer, active_tool_name, action_map):
    """提取glob全局匹配工具参数"""
    # 提取 path 和 pattern
    path_match = re.search(r'"path"\s*:\s*"([^"]*)', json_buffer)
    pattern_match = re.search(r'"pattern"\s*:\s*"([^"]*)', json_buffer)

    path_str = path_match.group(1) if path_match else "?"
    pattern_str = pattern_match.group(1) if pattern_match else ""
    action = action_map.get(active_tool_name, "操作")
    if pattern_str:
        if path_str == "?":
            display_content = f"{action}: 查找 '{pattern_str}'"
        else:
            display_content = f"{action}: 在 {path_str} 查找 '{pattern_str}'"
    else:
        display_content = f"{action}: 扫描目录 {path_str}..."
    return display_content


def _extract_read_many_files_param(json_buffer):
    """提取批量读取文件工具参数"""
    match_paths = re.findall(r'"([^"]+)"', json_buffer.split('[')[-1])
    if match_paths:
        paths = [p for p in match_paths if p != "paths"]
        if paths:
            display_str = ", ".join(paths)
            return f"📖 批量读取文件: {display_str}"
    return ""


def _extract_todo_write_param(json_buffer, sent_tasks):
    """提取todo_write工具参数并生成任务列表"""
    step_status = {
        "completed": {"icon": "✅", "prefix": "已完成"},
        "in_progress": {"icon": "🔄", "prefix": "进行中"},
        "pending": {"icon": "⬜", "prefix": "待办"},
        "failed": {"icon": "❌", "prefix": "失败"},
        "skipped": {"icon": "⏭️", "prefix": "跳过"},
    }
    pattern = r'\{\s*.*?"content"\s*:\s*"([^"]+)".*?"status"\s*:\s*"([^"]+)".*?\}'
    # 这里的 matches 会是一个列表，每个元素是 (content, status) 的元组
    matches = re.findall(pattern, json_buffer, re.DOTALL)
    task_counter = 1
    results = []
    for content, status in matches:
        unique_key = f"{content}_{status}"
        if unique_key not in sent_tasks:
            config = step_status.get(status, "")
            icon = config["icon"]
            results.append((f"•{icon} 步骤 {task_counter}: {content}\n\n", content))
            task_counter += 1
            sent_tasks.add(unique_key)
    return results


def _extract_grep_search_param(json_buffer):
    """提取grep_search工具参数"""
    path_match = re.search(r'"path"\s*:\s*"([^"]*)', json_buffer)
    pattern_match = re.search(r'"pattern"\s*:\s*"([^"]*)', json_buffer)
    path_str = path_match.group(1) if path_match else "?"
    pattern_str = pattern_match.group(1) if pattern_match else ""
    if pattern_str:
        return f"🔍 搜索内容: 在 {path_str} 中搜索 '{pattern_str}'"
    elif path_str:
        return f"🔍 搜索范围: {path_str}..."
    return ""


def _extract_run_shell_command_param(json_buffer):
    """提取run_shell_command工具参数"""
    inner_data = json.loads(json_buffer)
    command = inner_data.get("command")
    description = inner_data.get("description")
    if command and description:
        return f"💻 执行命令{command}, {description}"
    return ""


def _extract_resolve_library_id_param(json_buffer):
    inner_data = json.loads(json_buffer)
    query = inner_data.get("query")
    libraryName = inner_data.get("libraryName")
    if query and libraryName:
        return f"📚 从目标文档库{libraryName}中查询{query}命令"
    return ""


def _extract_query_tool_param(json_buffer):
    """提取查询类工具参数（resolve-library-id, query-docs等）"""
    match = re.search(r':\s*"([^"]*)', json_buffer)
    if match:
        value = match.group(1)
        return f"📚 查询: {value}"
    return ""


def _handle_input_json_delta(json_buffer, active_tool_name, action_map, sent_tasks):
    """处理工具参数生成片段（input_json_delta）"""
    display_content = ""
    # 单路径类工具
    if active_tool_name in ["read_file", "list_directory", "save_memory", "web_fetch"]:
        display_content = _extract_single_path_tool_param(json_buffer, active_tool_name, action_map)
    # edit编辑工具
    elif active_tool_name == "edit":
        display_content = _extract_edit_tool_param(json_buffer, active_tool_name, action_map)
    # 写入文件工具
    elif active_tool_name == "write_file":
        display_content = _extract_write_file_tool_param(json_buffer, active_tool_name, action_map)
    # 全局匹配工具
    elif active_tool_name == "glob":
        display_content = _extract_glob_tool_param(json_buffer, active_tool_name, action_map)
    # 批量读取文件
    elif active_tool_name == "read_many_files":
        display_content = _extract_read_many_files_param(json_buffer)
    # todo_write工具
    elif active_tool_name == "todo_write":
        todo_results = _extract_todo_write_param(json_buffer, sent_tasks)
        return todo_results  # 返回特殊格式，需要单独处理
    # grep_search工具
    elif active_tool_name == "grep_search":
        display_content = _extract_grep_search_param(json_buffer)
    # run_shell_command工具
    elif active_tool_name == "run_shell_command":
        display_content = _extract_run_shell_command_param(json_buffer)
    # resolve-library-id查询工具
    elif active_tool_name == "resolve-library-id":
        display_content = _extract_resolve_library_id_param(json_buffer)
    # 查询类工具
    elif active_tool_name in ["query-docs", "task"]:
        display_content = _extract_query_tool_param(json_buffer)
    # exit_plan_mode
    elif active_tool_name == "exit_plan_mode":
        display_content = "准备退出规划模式..."
    # pi 协议 MCP 工具调用：arguments 通常形如
    #   mcp({"server": "<name>"})                 -> 列出该 server 下的工具
    #   mcp({"tool": "<tool_name>",
    #        "args": "<json string of params>"})   -> 调用具体工具
    elif active_tool_name == "mcp":
        display_content = _extract_mcp_tool_param(json_buffer)
    # pi 协议 subagent / subagent_wait 工具调用：
    #   subagent({"action":"list"})                       -> 列出可委派的 agent
    #   subagent({"agent":"worker","task":"..."})         -> 单次委派
    #   subagent({"workflowScript":"<JS>"})               -> 编排脚本（可能很长）
    #   subagent({"action":"status","id":"<runId>"})      -> 查 run 状态
    #   subagent_wait({"all":true,"timeoutMs":180000})    -> 等待完成
    elif active_tool_name in ("subagent", "subagent_wait"):
        display_content = _extract_subagent_param(json_buffer, active_tool_name)
    else:
        display_content = json_buffer

    return display_content


def _extract_mcp_tool_param(json_buffer):
    """提取 pi 协议下 mcp 工具调用参数。

    pi 的 mcp tool arguments 形如：
        mcp({"server":"<name>"})
        mcp({"tool":"<tool_name>","args":"<json string>"})
    """
    try:
        params = json.loads(json_buffer) if json_buffer else {}
    except (json.JSONDecodeError, ValueError):
        # 增量 JSON 还不完整；保留原文以便下一轮 delta 拼接
        return f"🧩 调用 MCP 工具（参数生成中…）"

    if not isinstance(params, dict):
        return f"🧩 调用 MCP 工具：{json_buffer}"

    if "server" in params and "tool" not in params:
        return f"🧩 MCP：列出服务器 `{params.get('server')}` 的工具"
    if "tool" in params:
        tool_name = params.get("tool") or ""
        args_raw = params.get("args") or ""
        try:
            args_obj = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        except (json.JSONDecodeError, ValueError):
            args_obj = args_raw
        if args_obj:
            return f"🧩 调用 MCP 工具 `{tool_name}`（参数：{args_obj}）"
        return f"🧩 调用 MCP 工具 `{tool_name}`"
    return f"🧩 调用 MCP 工具（参数：{params}）"


def _extract_subagent_param(json_buffer, tool_name):
    """提取 pi 协议下 subagent / subagent_wait 工具调用参数。

    subagent arguments 形态：
        {"action":"list"}                       -> 列出可委派的 agent
        {"agent":"worker","task":"..."}         -> 单次委派
        {"workflowScript":"<JS string>"}        -> 编排脚本（可能很长，截断展示）
        {"action":"status","id":"<runId>"}      -> 查 run 状态
    subagent_wait arguments 形态：
        {"all":true,"timeoutMs":180000}         -> 等待所有
        {"id":"<runId>","timeoutMs":60000}      -> 等待单个
    """
    try:
        params = json.loads(json_buffer) if json_buffer else {}
    except (json.JSONDecodeError, ValueError):
        # 增量 JSON 还不完整；保留原文以便下一轮 delta 拼接
        return f"🧑‍🤝‍🧑 调用 {tool_name}（参数生成中…）"

    if not isinstance(params, dict):
        return f"🧑‍🤝‍🧑 调用 {tool_name}：{json_buffer}"

    if tool_name == "subagent_wait":
        if params.get("all") is True:
            tm = params.get("timeoutMs")
            suffix = f"，timeoutMs={tm}" if tm else ""
            return f"⏳ 等待所有当前会话的 subagent 异步任务完成{suffix}"
        run_id = params.get("id") or "?"
        tm = params.get("timeoutMs")
        suffix = f"，timeoutMs={tm}" if tm else ""
        return f"⏳ 等待 subagent 异步任务 `{run_id}` 完成{suffix}"

    # tool_name == "subagent"
    action = params.get("action")
    if action == "list":
        return "📋 列出可用的 subagent"
    if action == "status":
        run_id = params.get("id") or "?"
        return f"🔍 查询 subagent 运行状态：`{run_id}`"
    # 单次委派：{ agent, task }
    if "agent" in params and "workflowScript" not in params:
        agent = params.get("agent") or "?"
        task = (params.get("task") or "").strip()
        if task:
            short = task if len(task) <= 200 else task[:200] + "…"
            return f"🧑‍🤝‍🧑 委派任务给 `{agent}`：{short}"
        return f"🧑‍🤝‍🧑 委派任务给 `{agent}`"
    # 工作流编排脚本：{ workflowScript }
    if "workflowScript" in params:
        script = params.get("workflowScript") or ""
        short = script if len(script) <= 800 else script[:800] + "\n…（workflowScript 已截断）"
        # 围栏必须 4 空格缩进：本展示串固定嵌在 <details> 工具折叠块内，
        # 裸 ``` 会被 marked 当合法围栏、与块外正文围栏失配，把块后所有
        # 内容吞进一个巨型代码块（"正文全包进思考块"的根因之一）。
        return f"🧑‍🤝‍🧑 编排 subagent 工作流脚本：\n    ```js\n{short}\n    ```"
    # 兜底
    return f"🧑‍🤝‍🧑 调用 subagent（参数：{params}）"


def _handle_content_block_delta(event, json_buffer_ref, active_tool_name, action_map, sent_tasks):
    """处理内容块增量事件

    Args:
        event: 事件数据
        json_buffer_ref: json_buffer的列表引用，用于更新值 [json_buffer]
        active_tool_name: 当前工具名
        action_map: 动作映射表
        sent_tasks: 已发送任务集合

    Yields:
        bytes: 流式响应数据
    """
    delta = event.get("delta", {})
    display_content = ""

    if delta.get("type") == "text_delta":
        text = delta.get("text", "")
        if text:
            yield to_line(AiDataStatus.RECEIVING_RESULT, text)
    elif delta.get("type") == "input_json_delta":
        partial_json = delta.get("partial_json", "")
        json_buffer_ref[0] += partial_json  # 更新引用

        # todo_write 是唯一需要"逐 delta 输出"的工具（靠 sent_tasks 去重渐进产出任务列表）。
        # 其余工具若在每个 delta 上无条件重算 _handle_input_json_delta，会把"到目前为止的
        # 完整参数"重复输出 N 次（O(n²) 爆炸），因此按参数形态分组处理：
        #   - write_file：只发一次头部摘要（路径 + 围栏开头），内容体不再流里重复；
        #   - JSON 完整才可解析组（edit 等）：解析成功时全量展示一次；
        #   - 正则提取组（read_file 等）：短摘要做增量去重；
        #   - 未知工具：delta 阶段静默（content_block_start 已展示工具名）。
        if active_tool_name == "todo_write":
            result = _handle_input_json_delta(json_buffer_ref[0], active_tool_name, action_map, sent_tasks)
            if isinstance(result, list):
                # todo_write返回的是列表，需要逐个yield
                for msg, _ in result:
                    yield to_line(AiDataStatus.RECEIVING_RESULT, msg)
        elif active_tool_name == "write_file":
            # json_buffer_ref[2] 标记头部是否已发送；路径未拼全时返回空串，留待后续 delta。
            header_sent = json_buffer_ref[2] if len(json_buffer_ref) > 2 else False
            if not header_sent:
                display_content = _extract_write_file_header(
                    json_buffer_ref[0], active_tool_name, action_map)
                if display_content and len(json_buffer_ref) > 2:
                    json_buffer_ref[2] = True
        elif active_tool_name in _JSON_COMPLETE_ONCE_TOOLS:
            # 参数 JSON 闭合后才展示一次全量摘要；未闭合时静默等待后续 delta。
            # （mcp/subagent 的提取函数对残缺 JSON 会返回占位符而非抛错，
            #   故先显式 json.loads 校验完整性，不能只依赖异常。）
            once_sent = json_buffer_ref[2] if len(json_buffer_ref) > 2 else False
            if not once_sent:
                try:
                    json.loads(json_buffer_ref[0])
                    display_content = _handle_input_json_delta(
                        json_buffer_ref[0], active_tool_name, action_map, sent_tasks)
                except (json.JSONDecodeError, ValueError):
                    display_content = ""
                if display_content and len(json_buffer_ref) > 2:
                    json_buffer_ref[2] = True
        elif active_tool_name in _SINGLE_PATH_PROGRESS_TOOLS:
            # 单路径类工具：参数很短且天然增量（regex 从累积 buffer 提取路径），
            # 仅当提取结果与上次不同才输出，避免同一路径重复刷屏。
            # json_buffer_ref[1] 缓存上次已展示摘要；旧调用方只传 [buffer] 时不做去重（只输出一次也无妨）。
            display_content = _handle_input_json_delta(
                json_buffer_ref[0], active_tool_name, action_map, sent_tasks)
            last_shown = json_buffer_ref[1] if len(json_buffer_ref) > 1 else None
            if display_content == last_shown:
                display_content = ""
            elif len(json_buffer_ref) > 1:
                json_buffer_ref[1] = display_content

    if display_content:
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"{display_content}\n")


# 单路径类工具集合：参数以 path/url 等短字符串为主，可安全做增量去重展示
_SINGLE_PATH_PROGRESS_TOOLS = frozenset([
    "read_file", "list_directory", "save_memory", "web_fetch",
    "glob", "read_many_files", "grep_search",
    "resolve-library-id", "query-docs", "task",
])

# 参数 JSON 必须完整闭合才能解析展示的工具集合：解析成功即全量展示一次
_JSON_COMPLETE_ONCE_TOOLS = frozenset([
    "edit", "run_shell_command", "mcp", "subagent", "subagent_wait",
])


def _extract_write_file_header(json_buffer, active_tool_name, action_map):
    """write_file 的流式头部摘要：只报路径与围栏开头，不携带文件内容体。

    路径值必须已带闭合引号才输出（增量 JSON 可能只写到一半），
    否则返回空串、等待后续 delta 拼全。
    """
    action = action_map.get(active_tool_name, "操作")
    match = re.search(r'"(?:path|file_path)"\s*:\s*"([^"]*)"', json_buffer)
    file_path = match.group(1) if match else ""
    if file_path:
        # 围栏 4 空格缩进：本头部固定嵌在 <details> 工具折叠块内（对齐
        # _extract_write_file_tool_param），避免裸 ``` 与块外围栏失配。
        return f"{action}路径: {file_path}\n\n    ```makefile\n"
    return ""


def _handle_content_block_start(event):
    """处理内容块开始事件"""
    block = event.get("content_block", {})
    if block.get("type") == "tool_use":
        active_tool_name = block.get("name")
        init_msg = f"\n<details>\n<summary>🤖 [Agent动作] 调用{active_tool_name}工具</summary>\n"
        return active_tool_name, init_msg
    return None, None


def _extract_assistant_text(data) -> str:
    """从 assistant 汇总消息中提取纯文本（不做去重判断）"""
    message = data.get("message", {}) or {}
    contents = message.get("content", []) or []

    if isinstance(contents, str):
        return contents

    parts = []
    for item in contents:
        if item.get("type") == "text":
            text = item.get("text", "")
            if text:
                parts.append(text)
    return "".join(parts)


def _handle_assistant_message(data, saw_stream_event: bool = True, stream_text_accum: str = ""):
    """处理助手汇总消息

    说明：
    - 某些模型会同时输出 stream_event（增量）+ assistant（汇总），也可能只输出其中之一。
    - 为避免“汇总里才有的尾段内容被丢弃”这类问题，这里会在已收到 stream_event 的前提下做一次轻量去重：
      - 如果 assistant 文本完全等于已流式输出的累计文本，则跳过。
      - 如果 assistant 文本以累计文本为前缀，仅输出尾部增量，避免重复同时不丢尾段。
      - 其它情况（例如只输出 assistant、或 assistant 与流式不一致）则原样透传，优先保证不丢内容。
    """
    message = data.get("message", {}) or {}
    contents = message.get("content", []) or []

    # 兼容 content 为单段文本的极端情况
    if isinstance(contents, str):
        assistant_text = contents or ""
    else:
        assistant_text = _extract_assistant_text(data)

    if not assistant_text:
        return

    if saw_stream_event and stream_text_accum:
        # 完全重复：跳过
        if assistant_text == stream_text_accum:
            return
        # assistant 是“流式全文 + 少量尾巴”：只补尾巴
        if assistant_text.startswith(stream_text_accum):
            tail = assistant_text[len(stream_text_accum):]
            if tail:
                yield to_line(AiDataStatus.RECEIVING_RESULT, tail)
            return
        # assistant 被包含在已流式文本中：跳过（避免重复插入）
        if assistant_text in stream_text_accum:
            return

    yield to_line(AiDataStatus.RECEIVING_RESULT, assistant_text)
    return


def _handle_user_message(data, is_in_details):
    """处理用户消息（工具执行结果）"""
    message = data.get("message", {})
    contents = message.get("content", [])

    for item in contents:
        if item.get("type") == "tool_result":
            is_error = item.get("is_error", False)
            tool_use_id = item.get("tool_use_id")
            if is_error:
                yield to_line(AiDataStatus.RECEIVING_RESULT,
                              f"[错误：<strong>[工具执行失败]</strong> ID:{tool_use_id}]\n")


def _handle_error_message(data):
    """处理错误消息"""
    error_obj = data.get("error", {})
    error_msg = error_obj.get("message", "未知执行错误")
    yield to_line(AiDataStatus.BACKEND_ERROR, f"Agent Error: {error_msg}")


_TOOL_CALL_NAME_MAP = {
    "globToolCall": "glob",
    "readToolCall": "read_file",
    "editToolCall": "write_file",
    "updateTodosToolCall": "todo_write",
    "deleteToolCall": "delete_file",
    "listDirectoryToolCall": "list_directory",
    "shellToolCall": "run_shell_command",
    "grepToolCall": "grep_search",
}

_TODO_STATUS_MAP = {
    "TODO_STATUS_IN_PROGRESS": "in_progress",
    "TODO_STATUS_PENDING": "pending",
    "TODO_STATUS_COMPLETED": "completed",
    "TODO_STATUS_FAILED": "failed",
    "TODO_STATUS_SKIPPED": "skipped",
}


def _convert_tool_call_args(tool_call_key, args):
    """将tool_call格式的参数转换为_handle_input_json_delta兼容的JSON格式"""
    if tool_call_key == "globToolCall":
        converted = {}
        if "globPattern" in args:
            converted["pattern"] = args["globPattern"]
        if "targetDirectory" in args:
            converted["path"] = args["targetDirectory"]
        return json.dumps(converted, ensure_ascii=False)

    if tool_call_key == "editToolCall":
        converted = {}
        if "path" in args:
            converted["file_path"] = args["path"]
        if "streamContent" in args:
            converted["content"] = args["streamContent"]
        return json.dumps(converted, ensure_ascii=False)

    if tool_call_key == "updateTodosToolCall":
        json_str = json.dumps(args, ensure_ascii=False)
        for old_status, new_status in _TODO_STATUS_MAP.items():
            json_str = json_str.replace(old_status, new_status)
        return json_str

    return json.dumps(args, ensure_ascii=False)


def _handle_tool_call_message(data, action_map, sent_tasks):
    """处理tool_call类型的消息（Cursor API格式），复用_handle_input_json_delta逻辑

    Args:
        data: 完整的JSON数据
        action_map: 工具动作映射表
        sent_tasks: 已发送任务集合（用于todo_write去重）

    Yields:
        bytes: 流式响应数据
    """
    subtype = data.get("subtype")
    if subtype != "started":
        return

    tool_call_data = data.get("tool_call", {})
    tool_call_key = next(iter(tool_call_data), None)
    if not tool_call_key:
        return

    tool_call_info = tool_call_data[tool_call_key]
    args = tool_call_info.get("args", {})
    internal_name = _TOOL_CALL_NAME_MAP.get(tool_call_key, tool_call_key)

    yield to_line(AiDataStatus.RECEIVING_RESULT,
                  f"\n<details>\n<summary>🤖 [Agent动作] 调用{internal_name}工具</summary>\n")

    if tool_call_key == "deleteToolCall":
        path = args.get("path", "")
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"🗑️ 删除文件: {path}\n")
    else:
        json_buffer = _convert_tool_call_args(tool_call_key, args)
        result = _handle_input_json_delta(json_buffer, internal_name, action_map, sent_tasks)
        if isinstance(result, list):
            for msg, _ in result:
                yield to_line(AiDataStatus.RECEIVING_RESULT, msg)
        elif result:
            yield to_line(AiDataStatus.RECEIVING_RESULT, f"{result}\n")

    if internal_name == "write_file":
        # 与 _extract_write_file_header 的开场围栏配对：同样 4 空格缩进
        yield to_line(AiDataStatus.RECEIVING_RESULT, "    ```\n")
    yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")


# =============================================================================
# pi agent stream-json 协议适配
#
# pi --mode json 在 stdout 上输出的是逐行 JSONL（每行一个完整 JSON 对象），
# 不是单 JSON 文档。顶层 type 取值：
#   session | agent_start | turn_start | message_start | message_update
#   message_end | turn_end | agent_end | agent_settled
#
# 流式增量嵌在 message_update.assistantMessageEvent 里：
#   {"type": "thinking_start"|"thinking_delta"|"thinking_end"|"text_start"|"text_delta"|"text_end"}
#   + contentIndex（同一 message 内可能有多个 segment，0 通常是 thinking、1 是正文）
#
# message_end 时定型一次，message.content[] 是最终结构（含 type=thinking/text 等）。
# agent_settled 是协议结束信号，等价于 cursor 协议的 {"type": "result", ...}。
#
# 工具调用在 message.content[] 里以 {"type": "tool_use", ...} 形式存在，
# 字段名未在样本中出现，本版不解析，留作后续扩展点。
# =============================================================================


_FENCE_LINE_RE = re.compile(r"^(\s*)`{3,}(.*)$", re.MULTILINE)


def _sanitize_fences_in_details(text):
    """<details> 折叠块内的 ``` 围栏改写为缩进 4 空格，避免围栏失配吞掉后续内容。

    背景（线上实锤，agent 日志实测）：模型在 thinking/text 里输出的 ``` 围栏
    是「裸」的 markdown 片段——模型并不知道自己正在 <details> HTML 块里写
    东西。marked 按 CommonMark 解析：块内一个未闭合的 ``` 会把其后 90KB
    内容（含后端持续追加的工具 <details> 块与正文）全部吞进一个巨型
    <pre><code>，其后所有 <details>/</details> 被转义成纯文本——表现为
    「思考过程和输出正文全包在一个思考块里」。

    做法：流式按行过一遍；折叠块内（<details> 开启且未闭合）的 ``` 围栏行
    一律加 4 空格缩进——不再区分开启 / 关闭 / 失配形态，保留任何裸围栏都
    可能与块外内容失配，宁可统一降级。CommonMark 中缩进 ≥4 的 ``` 不再是
    围栏，块内围栏失配从根上消除。正文里的围栏（块外）原样保留，代码
    高亮不受影响；块内缩进 ``` 的代码示例在折叠块里渲染为缩进代码块，
    观感等价。

    关闭行识别兼容两种形态：纯 </details>（思考块）与 </div></details>
    （工具执行块，历史格式带 </div> 前缀，前端有行级清洗）。

    非流式（入库清洗）同函数可直接复用：对整串按同一状态机处理。
    """
    if not isinstance(text, str) or "<details>" not in text:
        return text
    out_lines = []
    in_details = False
    for line in text.split("\n"):
        stripped = line.lstrip(" \t")
        if stripped.startswith("<details>"):
            in_details = True
            out_lines.append(line)
            continue
        if stripped.startswith("</details>") or stripped.startswith("</div></details>"):
            in_details = False
            out_lines.append(line)
            continue
        if in_details and stripped.startswith("`"):
            if _FENCE_LINE_RE.match(line):
                # 块内围栏行统一缩进化：缩进 ≥4 后 CommonMark 不再视为围栏
                out_lines.append("    " + stripped)
                continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _handle_pi_session(data):
    """pi 协议：session 事件。

    session_id 已不再作为独立视觉帧输出（迁移产出的建议正文里出现一串
    UUID 对用户没有信息量）；改为并入 _format_pi_env_summary 生成的开头
    运行信息摘要，保留溯源能力的同时不占独立帧。
    """
    return
    # 保留取值逻辑示意（不可达）：如需恢复独立帧，取消下方注释即可。
    # session_id = data.get("id") or ""
    # if session_id:
    #     yield to_line(
    #         AiDataStatus.RECEIVING_RESULT,
    #         f"\n🔌 **[pi session]** `{session_id}` 已建立\n\n",
    #     )


def _format_pi_env_summary(data):
    """生成 pi agent 运行环境开头摘要（模型 / Key / session / MCP）。

    pi 的 session 事件只带 id 与 cwd；模型与 API Key 信息由后端调用侧
    （generate_agent_response / generate_project_agent_response 的
    AGENT_KEY_INFO）掌握，故本函数接受调用方补充的 context：
      - model：实际调用的模型名（必填）
      - key_prefix：API Key 前三位（脱敏展示）
      - mcp_servers：容器镜像 mcp.json 里配置的 MCP 服务名列表

    输出形如：
      ── 运行环境 ─────────────
      模型：rch-eco-tool-glm（Key: aio…）
      会话：`01a07b33-f7ee…`
      MCP：riscv-doc-mcp 等 1 个服务已配置
      ─────────────────────────
    """
    lines = ["\n---\n**🚀 运行环境**\n\n"]
    model = (data or {}).get("model") or ""
    key_prefix = (data or {}).get("key_prefix") or ""
    session_id = (data or {}).get("session_id") or ""
    mcp_servers = (data or {}).get("mcp_servers") or []

    if model:
        entry = f"- **模型**：`{model}`"
        if key_prefix:
            entry += f"（Key: {key_prefix}…）"
        lines.append(entry + "\n")
    if session_id:
        short = session_id if len(session_id) <= 18 else session_id[:15] + "…"
        lines.append(f"- **会话**：`{short}`\n")
    if mcp_servers:
        names = ", ".join(f"`{n}`" for n in mcp_servers[:5])
        more = f" 等 {len(mcp_servers)} 个" if len(mcp_servers) > 1 else ""
        lines.append(f"- **MCP 服务**：{names}{more}（启动时自动加载）\n")
    else:
        lines.append("- **MCP 服务**：未配置\n")
    lines.append("\n---\n\n")
    return "".join(lines)


def _handle_pi_message_update(event, in_thinking_ref, in_text_ref,
                              thinking_buffer_ref, text_buffer_ref,
                              thinking_details_open_ref=None,
                              thinking_fence_flush=None):
    """pi 协议：message_update 事件。

    assistantMessageEvent.type 取值：
      thinking_start / thinking_delta / thinking_end / text_start / text_delta / text_end

    状态机（基于 contentIndex 切分，0 = thinking、1 = 正文）：
      - thinking_start → 进入 thinking 段（不输出）
      - thinking_delta  → 流式推理段增量；首个非空 delta 时开 <details>
                          折叠块，之后原样透传（空思考不留空折叠块）
      - text_start      → 标记正文开始；★先关思考折叠块★
      - text_delta      → 流式正文增量，直接透传 delta
      - text_end        → 标记正文定型
      - thinking_end    → 关闭折叠块（块没开过/已被 text_start 关闭则不输出）

    ★ 事件时序实测（docker 实跑 pi agent 抓包，/tmp/pi_probe/raw_jsonl.log）：
      thinking_start → N×thinking_delta → text_start → M×text_delta
      → thinking_end → text_end
      pi 按 contentIndex 并行推流，*_end 定型事件在所有 delta 之后统一到达，
      text_start 早于 thinking_end！若等 thinking_end 才关折叠块，正文 delta
      会全部灌进思考 <details>——即线上"所有内容全包在思考过程里，正文没有
      输出"的直接根因。因此关块时机改为 text_start（正文段开始必然意味着
      思考段结束，contentIndex 有序），thinking_end 退化为幂等兜底。

    ★ 思考折叠（替代早期 <think/> 标签方案）：
      思考内容包成 <details><summary>💭 思考过程</summary>...</details>，
      前端 markdown 渲染默认收起、点开可看，英文思考不再与中文正文混排。
      - 中断兜底：用户"停止生成"（GeneratorExit）时 </details> 不会发出，
        入库前由 close_unclosed_details 统一补闭合（与工具执行块同一兜底）；
        实时视图因块后无内容，浏览器自动闭合，无吞内容风险。
      - 展开态保持：前端 openDetailsAnchors 快照回放对全部 <details> 生效，
        流式重渲染不丢用户手动展开的思考块。
      - 开块状态双保险跟踪：
        1) thinking_buffer 空与否（turn/message 边界与 in_thinking 同步清空）；
        2) thinking_details_open_ref（可选 [bool] 引用，与 pi_exec_in_details_ref
           同套路）——thinking_end 丢失（协议丢事件）时由调用方在边界处
           据此补发 </details>，避免未闭合块把后续正文吞进折叠区。

    Args:
        event: message_update 整条数据（含 assistantMessageEvent）。
        in_thinking_ref: [bool] 当前是否在 thinking 段（list 是为了让 generator 内部 mutate）。
        in_text_ref: [bool] 当前是否在 text 段。
        thinking_buffer_ref / text_buffer_ref: [str] 累加器，供 message_end 去重。
        thinking_details_open_ref: [bool] 思考折叠块是否处于开启态（可选）。
        thinking_fence_flush: 可调用（可选），thinking_end 关块前调用、返回值
            作为文本 yield——用于放出流式围栏清洗的换行缓冲残片，防止最后
            一段不完整行被缓冲吞掉。
    """
    sub = event.get("assistantMessageEvent") or {}
    sub_type = sub.get("type")

    if sub_type == "thinking_start":
        in_thinking_ref[0] = True

    elif sub_type == "thinking_delta":
        in_thinking_ref[0] = True
        delta = sub.get("delta") or ""
        if delta:
            # 首个非空 delta 才开折叠块（空思考 delta 一条没来就什么都不输出）
            if not thinking_buffer_ref[0]:
                if thinking_details_open_ref is not None:
                    thinking_details_open_ref[0] = True
                yield to_line(
                    AiDataStatus.RECEIVING_RESULT,
                    "\n<details>\n<summary>💭 思考过程</summary>\n",
                )
            thinking_buffer_ref[0] += delta
            yield to_line(AiDataStatus.RECEIVING_RESULT, delta)

    elif sub_type == "thinking_end":
        in_thinking_ref[0] = False
        # 幂等关块：text_start 已先关过（pi 时序见 docstring）则此处无操作；
        # 纯思考无正文的消息仍靠这里收尾。空思考时块根本没开过，同样无操作。
        if thinking_buffer_ref[0] and thinking_details_open_ref is not None and thinking_details_open_ref[0]:
            # 关块前放出换行缓冲残片：最后一段不完整行还在流式围栏缓冲区里
            if thinking_fence_flush is not None:
                tail = thinking_fence_flush()
                if tail:
                    yield to_line(AiDataStatus.RECEIVING_RESULT, tail)
            thinking_details_open_ref[0] = False
            yield to_line(AiDataStatus.RECEIVING_RESULT, "\n</details>\n")

    elif sub_type == "text_start":
        in_text_ref[0] = True
        # ★ 正文段开始 = 思考段结束（contentIndex 有序，text_start 实测早于
        #   thinking_end 到达）。必须在此关思考折叠块，否则正文 delta 全部
        #   灌进思考 <details>——"所有内容全包在思考过程里"的直接根因。
        if thinking_details_open_ref is not None and thinking_details_open_ref[0]:
            if thinking_fence_flush is not None:
                tail = thinking_fence_flush()
                if tail:
                    yield to_line(AiDataStatus.RECEIVING_RESULT, tail)
            thinking_details_open_ref[0] = False
            yield to_line(AiDataStatus.RECEIVING_RESULT, "\n</details>\n")

    elif sub_type == "text_delta":
        in_text_ref[0] = True
        delta = sub.get("delta") or ""
        if delta:
            text_buffer_ref[0] += delta
            yield to_line(AiDataStatus.RECEIVING_RESULT, delta)

    elif sub_type == "text_end":
        in_text_ref[0] = False


def _handle_pi_message_end(data, thinking_buffer, text_buffer, saw_stream_event):
    """pi 协议：message_end 事件。assistant 消息定型。

    仿照 _handle_assistant_message 的去重套路：
      - 若 thinking/text 已通过 delta 流完（即累加 == message.content 里的最终段）→ 跳过
      - 若累加是 message.content 的前缀 → 仅补尾巴
      - 其他情况 → 透传（保守不丢内容）

    Args:
        data: 完整 message_end JSON。
        thinking_buffer / text_buffer: message_update 阶段累加的字符串。
        saw_stream_event: 是否收到过任何 delta（True 表示已流式发过，触发去重路径）。

    Yields:
        bytes: 需补发的正文尾巴（如果有）。
    """
    message = data.get("message") or {}
    contents = message.get("content") or []
    if isinstance(contents, str):
        contents = [{"type": "text", "text": contents}]

    final_text = ""
    for item in contents:
        if isinstance(item, dict) and item.get("type") == "text":
            final_text += item.get("text") or ""

    if not final_text:
        return

    if saw_stream_event and text_buffer:
        if final_text == text_buffer:
            return
        if final_text.startswith(text_buffer):
            tail = final_text[len(text_buffer):]
            if tail:
                yield to_line(AiDataStatus.RECEIVING_RESULT, tail)
            return
        if final_text in text_buffer:
            return

    yield to_line(AiDataStatus.RECEIVING_RESULT, final_text)


def _handle_pi_toolcall_end(event, action_map, sent_tasks, active_tool_name_ref, json_buffer_ref, is_in_details_ref):
    """pi 协议：message_update.assistantMessageEvent.type=toolcall_end。

    toolcall_end 是工具调用的定型事件，结构：
      {"assistantMessageEvent": {"type": "toolcall_end", "contentIndex": 2,
                                 "toolCall": {"type": "toolCall", "id": "...", "name": "bash",
                                              "arguments": {"command": "ls -la ..."}}}}
    注意：arguments 已经是 dict（不是字符串）。

    与 _handle_tool_call_message（cursor 协议）不同：
      - cursor 协议是顶层 {"type":"tool_call", "subtype":"started", "tool_call":{<name>: {...}}}
        用 _TOOL_CALL_NAME_MAP 把 <name> 映射为标准名（read_file/write_file 等），方便复用 _extract_*。
      - pi 协议这里 name 直接是工具的标准名（"bash"/"read"/"mcp"/"edit" ...），
        arguments 是 dict，需要先 json.dumps 再走 _handle_input_json_delta。
    """
    sub = event.get("assistantMessageEvent") or {}
    tool_call = sub.get("toolCall") or {}
    if not tool_call:
        return

    tool_name = tool_call.get("name") or ""
    args = tool_call.get("arguments") or {}
    args_json = json.dumps(args, ensure_ascii=False)

    # 把当前工具信息记录到 parse_agent_output 的状态变量，便于后续 tool_execution_* 使用
    active_tool_name_ref[0] = tool_name
    json_buffer_ref[0] = args_json
    is_in_details_ref[0] = True
    sent_tasks.clear()

    yield to_line(
        AiDataStatus.RECEIVING_RESULT,
        f"\n<details>\n<summary>🤖 [Agent动作] 调用{tool_name}工具</summary>\n",
    )

    # 复用 cursor 协议的参数显示逻辑
    result = _handle_input_json_delta(args_json, tool_name, action_map, sent_tasks)
    if isinstance(result, list):
        # todo_write 返回列表，逐个 yield
        for msg, _ in result:
            yield to_line(AiDataStatus.RECEIVING_RESULT, msg)
    elif result:
        yield to_line(AiDataStatus.RECEIVING_RESULT, f"{result}\n")

    # 复用 cursor 协议的闭合逻辑：write_file 要补一个缩进围栏收尾
    if tool_name == "write_file":
        yield to_line(AiDataStatus.RECEIVING_RESULT, "    ```\n")
    yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")
    is_in_details_ref[0] = False


def _handle_pi_tool_execution_start(data, exec_in_details_ref=None):
    """pi 协议：tool_execution_start（顶层事件，工具开始执行）。

    字段：{"toolCallId", "toolName", "args": {...}}。
    用于在 toolcall_end 与 tool_execution_end 之间显示执行状态。

    exec_in_details_ref：[bool] 引用，标记当前是否处于本函数开启的折叠块内。
    tool_execution_end 收尾时会复位；流异常中断（GeneratorExit / 停止生成 /
    协议丢事件）时由调用方据此补发闭合标签，避免未闭合的 <details> 吞掉
    后续所有输出并被持久化。
    """
    tool_name = data.get("toolName") or "?"
    tool_call_id = data.get("toolCallId") or ""
    if exec_in_details_ref is not None:
        exec_in_details_ref[0] = True
    if tool_call_id:
        yield to_line(
            AiDataStatus.RECEIVING_RESULT,
            f"\n<details>\n<summary>⚙️ [Agent动作] 执行{tool_name}工具 (id={tool_call_id})</summary>\n",
        )
    else:
        yield to_line(
            AiDataStatus.RECEIVING_RESULT,
            f"\n<details>\n<summary>⚙️ [Agent动作] 执行{tool_name}工具</summary>\n",
        )


def _handle_pi_tool_execution_update(data, last_update_sig_ref=None, last_update_text_ref=None):
    """pi 协议：tool_execution_update（执行进度，部分结果）。

    字段：{"toolCallId", "toolName", "args", "partialResult": {"content": [...]}}.
    content[] 元素通常是 {"type":"text", "text": "..."}。

    subagent_wait 等长轮询工具的进度是周期性全量快照（实测同一等待块内
    780 条 update、数字归一后仅 10 种形态），逐条透传会把折叠块撑到数千行、
    且 agent 在等待期被杀时收尾 </details> 永不到达——其后所有内容嵌进一个
    巨型折叠块。做两层抑制：
      1) 签名去重：数字/空白归一后的形态与上一条相同 → 跳过；
      2) end 去重：tool_execution_end 的 result 常与最后一条 update 的
         partialResult 完全相同（pi 短工具实测：update 携带完整结果，end
         再重复一遍），end 时跳过与已发内容一致的部分，避免结果双份。
    last_update_sig_ref: [str] 跨事件持久的上次已发签名（可选；list 包装供 mutate）。
    last_update_text_ref: [str] 跨事件持久的上次已发原文（可选；供 end 比对去重）。
    """
    partial = data.get("partialResult") or {}
    contents = partial.get("content") or []
    pieces = []
    for item in contents:
        if isinstance(item, dict):
            txt = item.get("text") or ""
            if txt:
                pieces.append(txt)
    if not pieces:
        return
    joined = "".join(pieces)

    if last_update_text_ref is not None:
        last_update_text_ref[0] = joined
    if last_update_sig_ref is not None:
        sig = " ".join(re.sub(r"\d+(\.\d+)?", "#", joined).split())
        if sig == last_update_sig_ref[0]:
            return
        last_update_sig_ref[0] = sig
    yield to_line(AiDataStatus.RECEIVING_RESULT, f"{joined}\n")


def _truncate_tool_result(text, threshold=50_000, label="工具结果"):
    """通用工具结果裁剪：超过 threshold 字符时折叠收尾。"""
    if len(text) <= threshold:
        return text, ""
    head = text[:threshold]
    tail = (
        f"\n…（{label}过长，已截断；"
        f"原始长度 {len(text)} 字符，仅展示前 {threshold // 1000}KB）"
    )
    return head, tail


def _handle_pi_tool_execution_end(data, exec_in_details_ref=None, last_update_text_ref=None):
    """pi 协议：tool_execution_end（顶层事件，工具执行结束）。

    字段：{"toolCallId", "toolName", "result": {"content": [{"type":"text","text":"..."}...]}, "isError": bool}。
    用于在折叠块里展示执行结果；折叠块由 tool_execution_start 开启，本函数收尾。
    收尾时复位 exec_in_details_ref（若传入），让调用方的兜底闭合逻辑不重复补标签。

    last_update_text_ref: [str] tool_execution_update 已发出的最后一条原文（可选）。
    pi 短工具的 end.result 与最后一条 update.partialResult 常完全一致（实测
    bash 工具：update 已含完整结果，end 再重复一遍），一致时跳过避免双份。
    """
    is_error = data.get("isError", False)
    tool_name = data.get("toolName") or "?"
    result = data.get("result") or {}
    contents = result.get("content") or []

    if exec_in_details_ref is not None:
        exec_in_details_ref[0] = False

    pieces = []
    for item in contents:
        if isinstance(item, dict):
            txt = item.get("text") or ""
            if txt:
                pieces.append(txt)

    # 不同工具有不同的结果前缀标记，让 AI 面板一眼可识别
    TOOL_RESULT_MARKERS = {
        "mcp": "\u00A0\u00A0\u00A0\u00A0📦 **MCP 工具结果**\n",
        "subagent": "\u00A0\u00A0\u00A0\u00A0🧑‍🤝‍🧑 **Subagent 执行结果**\n",
        "subagent_wait": "\u00A0\u00A0\u00A0\u00A0⏳ **Subagent 等待结果**\n",
    }
    INDENT = "\u00A0\u00A0\u00A0\u00A0"

    if is_error:
        yield to_line(
            AiDataStatus.RECEIVING_RESULT,
            f"{INDENT}❌ [工具执行失败] {tool_name}\n",
        )
    if pieces:
        joined = "".join(pieces)
        # end 与已发的最后一条 update 原文一致 → 结果已随 update 展示过，跳过
        if last_update_text_ref is not None and joined == last_update_text_ref[0]:
            yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")
            return
        marker = TOOL_RESULT_MARKERS.get(tool_name)
        if marker:
            head, tail = _truncate_tool_result(
                joined,
                threshold=50_000,
                label=f"{tool_name} 结果",
            )
            yield to_line(
                AiDataStatus.RECEIVING_RESULT,
                f"{marker}{head}{tail}\n",
            )
        else:
            yield to_line(AiDataStatus.RECEIVING_RESULT, f"{joined}\n")

    yield to_line(AiDataStatus.RECEIVING_RESULT, "</div></details>\n")
