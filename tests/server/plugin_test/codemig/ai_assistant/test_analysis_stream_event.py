"""analysis_stream_event.py 单元测试"""
import json
import pytest

from plugin.codemig.ai_assistant.analysis_stream_event import (
    to_line,
    _get_action_map,
    _handle_system_message,
    _extract_single_path_tool_param,
    _extract_edit_tool_param,
    _extract_write_file_tool_param,
    _extract_glob_tool_param,
    _extract_read_many_files_param,
    _extract_todo_write_param,
    _extract_grep_search_param,
    _extract_run_shell_command_param,
    _extract_resolve_library_id_param,
    _extract_query_tool_param,
    _handle_input_json_delta,
    _handle_content_block_delta,
    _handle_content_block_start,
    _extract_assistant_text,
    _handle_assistant_message,
    _handle_user_message,
    _handle_error_message,
    _convert_tool_call_args,
    _handle_tool_call_message,
    _TOOL_CALL_NAME_MAP,
    _TODO_STATUS_MAP,
)
from plugin.codemig.ai_assistant.ai_data_status import AiDataStatus


# ---------------------------------------------------------------------------
# to_line
# ---------------------------------------------------------------------------
class TestToLine:
    def test_basic(self):
        result = to_line(AiDataStatus.RECEIVING_RESULT, "hello")
        parsed = json.loads(result)
        assert parsed["status"] == AiDataStatus.RECEIVING_RESULT.value
        assert parsed["value"] == "hello"
        assert result.endswith(b"\n")

    def test_empty_value(self):
        result = to_line(AiDataStatus.DONE, "")
        parsed = json.loads(result)
        assert parsed["status"] == AiDataStatus.DONE.value
        assert parsed["value"] == ""

    def test_unicode_value(self):
        result = to_line(AiDataStatus.RECEIVING_RESULT, "中文内容")
        parsed = json.loads(result)
        assert parsed["value"] == "中文内容"


# ---------------------------------------------------------------------------
# _get_action_map
# ---------------------------------------------------------------------------
class TestGetActionMap:
    def test_returns_dict(self):
        am = _get_action_map()
        assert isinstance(am, dict)
        assert "read_file" in am
        assert "edit" in am
        assert "write_file" in am


# ---------------------------------------------------------------------------
# _handle_system_message
# ---------------------------------------------------------------------------
class TestHandleSystemMessage:
    def _collect(self, data):
        return list(_handle_system_message(data))

    def test_full_data(self):
        data = {
            "model": "gpt-4",
            "permission_mode": "yolo",
            "tools": ["read_file", "edit"],
            "mcp_servers": [{"name": "svc1", "status": "ok"}],
        }
        lines = self._collect(data)
        assert len(lines) > 0
        # Should contain model, permission, tools, mcp info
        joined = b"".join(lines).decode("utf-8")
        assert "gpt-4" in joined
        assert "yolo" in joined
        assert "read_file" in joined
        assert "svc1" in joined

    def test_minimal_data(self):
        data = {}
        lines = self._collect(data)
        assert len(lines) >= 1
        joined = b"".join(lines).decode("utf-8")
        assert "系统初始化完成" in joined

    def test_no_tools(self):
        data = {"model": "test-model", "tools": []}
        lines = self._collect(data)
        joined = b"".join(lines).decode("utf-8")
        assert "test-model" in joined

    def test_mcp_servers_non_dict(self):
        data = {"mcp_servers": ["not_a_dict", {"name": "ok", "status": "running"}]}
        lines = self._collect(data)
        joined = b"".join(lines).decode("utf-8")
        assert "ok" in joined
        # non-dict items should be skipped

    def test_mcp_servers_empty(self):
        data = {"mcp_servers": []}
        lines = self._collect(data)
        joined = b"".join(lines).decode("utf-8")
        # should not crash


# ---------------------------------------------------------------------------
# _extract_single_path_tool_param
# ---------------------------------------------------------------------------
class TestExtractSinglePathToolParam:
    def test_path_key(self):
        am = _get_action_map()
        result = _extract_single_path_tool_param(
            '{"path": "/tmp/file.txt"}', "read_file", am
        )
        assert "/tmp/file.txt" in result
        assert "读取文件" in result

    def test_url_key(self):
        am = _get_action_map()
        result = _extract_single_path_tool_param(
            '{"url": "http://example.com"}', "web_fetch", am
        )
        assert "http://example.com" in result

    def test_no_match(self):
        am = _get_action_map()
        result = _extract_single_path_tool_param(
            '{"other": "value"}', "read_file", am
        )
        assert result == ""

    def test_absolute_path_key(self):
        am = _get_action_map()
        result = _extract_single_path_tool_param(
            '{"absolute_path": "/abs/path"}', "read_file", am
        )
        assert "/abs/path" in result


# ---------------------------------------------------------------------------
# _extract_edit_tool_param
# ---------------------------------------------------------------------------
class TestExtractEditToolParam:
    def test_full_edit(self):
        am = _get_action_map()
        buf = json.dumps({"file_path": "/a/b.c", "old_string": "old", "new_string": "new"})
        result = _extract_edit_tool_param(buf, "edit", am)
        assert "/a/b.c" in result
        assert "old" in result
        assert "new" in result

    def test_no_old_string(self):
        am = _get_action_map()
        buf = json.dumps({"file_path": "/a/b.c", "new_string": "new"})
        result = _extract_edit_tool_param(buf, "edit", am)
        assert "/a/b.c" in result
        assert "原始代码" not in result


# ---------------------------------------------------------------------------
# _extract_write_file_tool_param
# ---------------------------------------------------------------------------
class TestExtractWriteFileToolParam:
    def test_with_content(self):
        am = _get_action_map()
        buf = json.dumps({"file_path": "/x/y.z", "content": "hello"})
        result = _extract_write_file_tool_param(buf, "write_file", am)
        assert "/x/y.z" in result
        assert "hello" in result

    def test_no_content(self):
        am = _get_action_map()
        buf = json.dumps({"file_path": "/x/y.z"})
        result = _extract_write_file_tool_param(buf, "write_file", am)
        assert result == ""

    def test_path_key(self):
        am = _get_action_map()
        buf = json.dumps({"path": "/x/y.z", "content": "hi"})
        result = _extract_write_file_tool_param(buf, "write_file", am)
        assert "/x/y.z" in result


# ---------------------------------------------------------------------------
# _extract_glob_tool_param
# ---------------------------------------------------------------------------
class TestExtractGlobToolParam:
    def test_with_pattern_and_path(self):
        am = _get_action_map()
        buf = '{"path": "/src", "pattern": "*.py"}'
        result = _extract_glob_tool_param(buf, "glob", am)
        assert "*.py" in result
        assert "/src" in result

    def test_pattern_only(self):
        am = _get_action_map()
        buf = '{"pattern": "*.txt"}'
        result = _extract_glob_tool_param(buf, "glob", am)
        assert "*.txt" in result

    def test_path_only(self):
        am = _get_action_map()
        buf = '{"path": "/home"}'
        result = _extract_glob_tool_param(buf, "glob", am)
        assert "扫描目录" in result

    def test_empty(self):
        am = _get_action_map()
        buf = '{}'
        result = _extract_glob_tool_param(buf, "glob", am)
        assert "扫描目录" in result  # default path is "?"


# ---------------------------------------------------------------------------
# _extract_read_many_files_param
# ---------------------------------------------------------------------------
class TestExtractReadManyFilesParam:
    def test_with_paths(self):
        buf = '{"paths": ["/a.txt", "/b.txt"]}'
        result = _extract_read_many_files_param(buf)
        assert "/a.txt" in result
        assert "/b.txt" in result

    def test_empty(self):
        buf = '{"paths": []}'
        result = _extract_read_many_files_param(buf)
        assert result == ""


# ---------------------------------------------------------------------------
# _extract_todo_write_param
# ---------------------------------------------------------------------------
class TestExtractTodoWriteParam:
    def test_basic(self):
        buf = '[{"content": "Step 1", "status": "completed"}, {"content": "Step 2", "status": "in_progress"}]'
        sent = set()
        result = _extract_todo_write_param(buf, sent)
        assert len(result) == 2
        assert "Step 1" in result[0][0]
        assert "Step 2" in result[1][0]

    def test_dedup(self):
        buf = '[{"content": "Step 1", "status": "completed"}]'
        sent = set()
        result1 = _extract_todo_write_param(buf, sent)
        result2 = _extract_todo_write_param(buf, sent)
        assert len(result1) == 1
        assert len(result2) == 0

    def test_all_statuses(self):
        statuses = ["completed", "in_progress", "pending", "failed", "skipped"]
        for s in statuses:
            buf = f'[{{"content": "test", "status": "{s}"}}]'
            result = _extract_todo_write_param(buf, set())
            assert len(result) == 1


# ---------------------------------------------------------------------------
# _extract_grep_search_param
# ---------------------------------------------------------------------------
class TestExtractGrepSearchParam:
    def test_both(self):
        buf = '{"path": "/src", "pattern": "TODO"}'
        result = _extract_grep_search_param(buf)
        assert "TODO" in result
        assert "/src" in result

    def test_pattern_only(self):
        buf = '{"pattern": "TODO"}'
        result = _extract_grep_search_param(buf)
        assert "TODO" in result

    def test_path_only(self):
        buf = '{"path": "/src"}'
        result = _extract_grep_search_param(buf)
        assert "/src" in result

    def test_empty(self):
        buf = '{}'
        result = _extract_grep_search_param(buf)
        assert "搜索范围" in result  # default path is "?"


# ---------------------------------------------------------------------------
# _extract_run_shell_command_param
# ---------------------------------------------------------------------------
class TestExtractRunShellCommandParam:
    def test_both(self):
        buf = json.dumps({"command": "ls -la", "description": "list files"})
        result = _extract_run_shell_command_param(buf)
        assert "ls -la" in result
        assert "list files" in result

    def test_no_description(self):
        buf = json.dumps({"command": "ls"})
        result = _extract_run_shell_command_param(buf)
        assert result == ""


# ---------------------------------------------------------------------------
# _extract_resolve_library_id_param
# ---------------------------------------------------------------------------
class TestExtractResolveLibraryIdParam:
    def test_both(self):
        buf = json.dumps({"query": "memcpy", "libraryName": "glibc"})
        result = _extract_resolve_library_id_param(buf)
        assert "memcpy" in result
        assert "glibc" in result

    def test_no_query(self):
        buf = json.dumps({"libraryName": "glibc"})
        result = _extract_resolve_library_id_param(buf)
        assert result == ""


# ---------------------------------------------------------------------------
# _extract_query_tool_param
# ---------------------------------------------------------------------------
class TestExtractQueryToolParam:
    def test_with_value(self):
        buf = 'query: "some search term"'
        result = _extract_query_tool_param(buf)
        assert "some search term" in result

    def test_no_match(self):
        buf = "no colon here"
        result = _extract_query_tool_param(buf)
        assert result == ""


# ---------------------------------------------------------------------------
# _handle_input_json_delta
# ---------------------------------------------------------------------------
class TestHandleInputJsonDelta:
    def setup_method(self):
        self.am = _get_action_map()
        self.sent = set()

    def test_read_file(self):
        result = _handle_input_json_delta(
            '{"path": "/tmp/f.txt"}', "read_file", self.am, self.sent
        )
        assert "/tmp/f.txt" in result

    def test_edit(self):
        buf = json.dumps({"file_path": "/a.c", "old_string": "x", "new_string": "y"})
        result = _handle_input_json_delta(buf, "edit", self.am, self.sent)
        assert "/a.c" in result

    def test_write_file(self):
        buf = json.dumps({"file_path": "/a.c", "content": "code"})
        result = _handle_input_json_delta(buf, "write_file", self.am, self.sent)
        assert "/a.c" in result

    def test_glob(self):
        result = _handle_input_json_delta(
            '{"pattern": "*.py", "path": "/src"}', "glob", self.am, self.sent
        )
        assert "*.py" in result

    def test_read_many_files(self):
        buf = '{"paths": ["/a.txt"]}'
        result = _handle_input_json_delta(buf, "read_many_files", self.am, self.sent)
        assert "/a.txt" in result

    def test_todo_write_returns_list(self):
        buf = '[{"content": "step1", "status": "completed"}]'
        result = _handle_input_json_delta(buf, "todo_write", self.am, self.sent)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_grep_search(self):
        buf = '{"path": "/src", "pattern": "TODO"}'
        result = _handle_input_json_delta(buf, "grep_search", self.am, self.sent)
        assert "TODO" in result

    def test_run_shell_command(self):
        buf = json.dumps({"command": "ls", "description": "list"})
        result = _handle_input_json_delta(buf, "run_shell_command", self.am, self.sent)
        assert "ls" in result

    def test_resolve_library_id(self):
        buf = json.dumps({"query": "memcpy", "libraryName": "glibc"})
        result = _handle_input_json_delta(buf, "resolve-library-id", self.am, self.sent)
        assert "memcpy" in result

    def test_query_docs(self):
        result = _handle_input_json_delta('query: "search"', "query-docs", self.am, self.sent)
        assert "search" in result

    def test_task(self):
        result = _handle_input_json_delta('task: "do it"', "task", self.am, self.sent)
        assert isinstance(result, str)

    def test_exit_plan_mode(self):
        result = _handle_input_json_delta("{}", "exit_plan_mode", self.am, self.sent)
        assert "退出规划模式" in result

    def test_unknown_tool(self):
        result = _handle_input_json_delta("raw buffer", "unknown_tool", self.am, self.sent)
        assert result == "raw buffer"

    def test_list_directory(self):
        result = _handle_input_json_delta(
            '{"path": "/tmp/dir"}', "list_directory", self.am, self.sent
        )
        assert "/tmp/dir" in result

    def test_save_memory(self):
        result = _handle_input_json_delta(
            '{"path": "/tmp/mem"}', "save_memory", self.am, self.sent
        )
        assert "/tmp/mem" in result

    def test_web_fetch(self):
        result = _handle_input_json_delta(
            '{"url": "http://example.com"}', "web_fetch", self.am, self.sent
        )
        assert "http://example.com" in result


# ---------------------------------------------------------------------------
# _handle_content_block_delta
# ---------------------------------------------------------------------------
class TestHandleContentBlockDelta:
    def test_text_delta(self):
        event = {"delta": {"type": "text_delta", "text": "hello world"}}
        lines = list(_handle_content_block_delta(event, [""], "read_file", _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "hello world" in joined

    def test_input_json_delta(self):
        event = {"delta": {"type": "input_json_delta", "partial_json": '{"path": "/test"}'}}
        lines = list(_handle_content_block_delta(
            event, ["", None, False], "read_file", _get_action_map(), set()
        ))
        assert len(lines) >= 1

    def test_input_json_delta_no_div_flood(self):
        """每个 input_json_delta 不再注入裸 <div>，也不重复输出同一路径摘要"""
        events = [
            {"delta": {"type": "input_json_delta", "partial_json": '{"path": "/t'}},
            {"delta": {"type": "input_json_delta", "partial_json": 'est.txt"}'}},
            {"delta": {"type": "input_json_delta", "partial_json": ',"mode": "r"}'}},
        ]
        buf = ["", None, False]
        all_lines = []
        for ev in events:
            all_lines.extend(_handle_content_block_delta(
                ev, buf, "read_file", _get_action_map(), set()))
        joined = b"".join(all_lines).decode("utf-8")
        assert "<div>" not in joined
        # 路径拼全后展示一次，后续内容变化不重复刷屏
        assert joined.count("/test.txt") == 1

    def test_input_json_delta_write_file_header_once(self):
        """write_file 只发一次头部摘要，内容体不重复输出（O(n²) 修复）"""
        args = {"file_path": "/app/main.c", "content": "int main(){return 0;}"}
        payload = json.dumps(args)
        half = len(payload) // 2
        events = [
            {"delta": {"type": "input_json_delta", "partial_json": payload[:half]}},
            {"delta": {"type": "input_json_delta", "partial_json": payload[half:]}},
            {"delta": {"type": "input_json_delta", "partial_json": ""}},
        ]
        buf = ["", None, False]
        all_lines = []
        for ev in events:
            all_lines.extend(_handle_content_block_delta(
                ev, buf, "write_file", _get_action_map(), set()))
        joined = b"".join(all_lines).decode("utf-8")
        # 路径只在头部摘要里出现一次，文件内容体完全不进流
        assert "/app/main.c" in joined
        assert "int main" not in joined
        # 无 <div> 噪声
        assert "<div>" not in joined

    def test_input_json_delta_write_file_header_waits_full_path(self):
        """路径值未闭合时不出头部（避免半截路径），拼全后输出"""
        buf = ["", None, False]
        first = list(_handle_content_block_delta(
            {"delta": {"type": "input_json_delta", "partial_json": '{"file_path": "/app/ma'}},
            buf, "write_file", _get_action_map(), set()))
        assert len(first) == 0
        second = list(_handle_content_block_delta(
            {"delta": {"type": "input_json_delta", "partial_json": 'in.c", "content": "x"}'}},
            buf, "write_file", _get_action_map(), set()))
        joined = b"".join(second).decode("utf-8")
        assert "/app/main.c" in joined

    def test_input_json_delta_edit_waits_complete_json(self):
        """edit 参数 JSON 完整闭合后才展示一次摘要"""
        args = {"file_path": "/a.c", "old_string": "x", "new_string": "y"}
        payload = json.dumps(args)
        half = len(payload) // 2
        buf = ["", None, False]
        first = list(_handle_content_block_delta(
            {"delta": {"type": "input_json_delta", "partial_json": payload[:half]}},
            buf, "edit", _get_action_map(), set()))
        assert len(first) == 0
        second = list(_handle_content_block_delta(
            {"delta": {"type": "input_json_delta", "partial_json": payload[half:]}},
            buf, "edit", _get_action_map(), set()))
        joined = b"".join(second).decode("utf-8")
        assert "/a.c" in joined

    def test_input_json_delta_todo_write_still_streams(self):
        """todo_write 保持逐 delta 渐进输出语义（sent_tasks 去重）"""
        buf = ["", None, False]
        lines = list(_handle_content_block_delta(
            {"delta": {"type": "input_json_delta",
                       "partial_json": '[{"content": "step1", "status": "completed"}]'}},
            buf, "todo_write", _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "step1" in joined

    def test_text_delta_empty(self):
        event = {"delta": {"type": "text_delta", "text": ""}}
        lines = list(_handle_content_block_delta(event, [""], "read_file", _get_action_map(), set()))
        assert len(lines) == 0


# ---------------------------------------------------------------------------
# _handle_content_block_start
# ---------------------------------------------------------------------------
class TestHandleContentBlockStart:
    def test_tool_use(self):
        event = {"content_block": {"type": "tool_use", "name": "read_file"}}
        name, msg = _handle_content_block_start(event)
        assert name == "read_file"
        assert "read_file" in msg

    def test_not_tool_use(self):
        event = {"content_block": {"type": "text"}}
        name, msg = _handle_content_block_start(event)
        assert name is None
        assert msg is None


# ---------------------------------------------------------------------------
# _extract_assistant_text
# ---------------------------------------------------------------------------
class TestExtractAssistantText:
    def test_list_content(self):
        data = {"message": {"content": [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ]}}
        result = _extract_assistant_text(data)
        assert result == "hello world"

    def test_str_content(self):
        data = {"message": {"content": "just text"}}
        result = _extract_assistant_text(data)
        assert result == "just text"

    def test_empty_list(self):
        data = {"message": {"content": []}}
        result = _extract_assistant_text(data)
        assert result == ""

    def test_none_message(self):
        data = {"message": None}
        result = _extract_assistant_text(data)
        assert result == ""

    def test_non_text_items_filtered(self):
        data = {"message": {"content": [
            {"type": "image", "data": "..."},
            {"type": "text", "text": "only this"},
        ]}}
        result = _extract_assistant_text(data)
        assert result == "only this"


# ---------------------------------------------------------------------------
# _handle_assistant_message
# ---------------------------------------------------------------------------
class TestHandleAssistantMessage:
    def _collect(self, data, **kwargs):
        return list(_handle_assistant_message(data, **kwargs))

    def test_no_dedup(self):
        data = {"message": {"content": "simple text"}}
        lines = self._collect(data, saw_stream_event=False)
        assert len(lines) == 1

    def test_full_duplicate_skipped(self):
        data = {"message": {"content": "abc"}}
        lines = self._collect(data, saw_stream_event=True, stream_text_accum="abc")
        assert len(lines) == 0

    def test_prefix_dedup_tail(self):
        data = {"message": {"content": "abcDEF"}}
        lines = self._collect(data, saw_stream_event=True, stream_text_accum="abc")
        joined = b"".join(lines).decode("utf-8")
        assert "DEF" in joined
        assert "abc" not in joined

    def test_contained_in_accum(self):
        data = {"message": {"content": "bc"}}
        lines = self._collect(data, saw_stream_event=True, stream_text_accum="abcdef")
        assert len(lines) == 0

    def test_empty_text_no_output(self):
        data = {"message": {"content": []}}
        lines = self._collect(data)
        assert len(lines) == 0

    def test_str_content(self):
        data = {"message": {"content": "hello"}}
        lines = self._collect(data, saw_stream_event=False)
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# _handle_user_message
# ---------------------------------------------------------------------------
class TestHandleUserMessage:
    def test_error_result(self):
        data = {"message": {"content": [
            {"type": "tool_result", "is_error": True, "tool_use_id": "123"}
        ]}}
        lines = list(_handle_user_message(data, False))
        joined = b"".join(lines).decode("utf-8")
        assert "工具执行失败" in joined
        assert "123" in joined

    def test_no_error(self):
        data = {"message": {"content": [
            {"type": "tool_result", "is_error": False, "tool_use_id": "456"}
        ]}}
        lines = list(_handle_user_message(data, False))
        assert len(lines) == 0


# ---------------------------------------------------------------------------
# _handle_error_message
# ---------------------------------------------------------------------------
class TestHandleErrorMessage:
    def test_with_message(self):
        data = {"error": {"message": "something broke"}}
        lines = list(_handle_error_message(data))
        joined = b"".join(lines).decode("utf-8")
        assert "something broke" in joined
        assert "Agent Error" in joined

    def test_no_error_field(self):
        data = {}
        lines = list(_handle_error_message(data))
        joined = b"".join(lines).decode("utf-8")
        assert "未知执行错误" in joined


# ---------------------------------------------------------------------------
# _convert_tool_call_args
# ---------------------------------------------------------------------------
class TestConvertToolCallArgs:
    def test_glob_tool_call(self):
        args = {"globPattern": "*.py", "targetDirectory": "/src"}
        result = _convert_tool_call_args("globToolCall", args)
        parsed = json.loads(result)
        assert parsed["pattern"] == "*.py"
        assert parsed["path"] == "/src"

    def test_edit_tool_call(self):
        args = {"path": "/a.c", "streamContent": "new code"}
        result = _convert_tool_call_args("editToolCall", args)
        parsed = json.loads(result)
        assert parsed["file_path"] == "/a.c"
        assert parsed["content"] == "new code"

    def test_update_todos_tool_call(self):
        args = {"todos": [{"content": "step", "status": "TODO_STATUS_COMPLETED"}]}
        result = _convert_tool_call_args("updateTodosToolCall", args)
        assert "completed" in result
        assert "TODO_STATUS_COMPLETED" not in result

    def test_other_tool_call(self):
        args = {"key": "value"}
        result = _convert_tool_call_args("unknownToolCall", args)
        parsed = json.loads(result)
        assert parsed["key"] == "value"


# ---------------------------------------------------------------------------
# _handle_tool_call_message
# ---------------------------------------------------------------------------
class TestHandleToolCallMessage:
    def test_non_started_subtype_ignored(self):
        data = {"subtype": "completed", "tool_call": {"globToolCall": {"args": {}}}}
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        assert len(lines) == 0

    def test_empty_tool_call(self):
        data = {"subtype": "started", "tool_call": {}}
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        assert len(lines) == 0

    def test_delete_tool_call(self):
        data = {
            "subtype": "started",
            "tool_call": {"deleteToolCall": {"args": {"path": "/tmp/del.txt"}}}
        }
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "删除文件" in joined
        assert "/tmp/del.txt" in joined

    def test_glob_tool_call(self):
        data = {
            "subtype": "started",
            "tool_call": {"globToolCall": {"args": {"globPattern": "*.c", "targetDirectory": "/src"}}}
        }
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "*.c" in joined

    def test_write_file_tool_call_adds_code_block(self):
        data = {
            "subtype": "started",
            "tool_call": {"editToolCall": {"args": {"path": "/a.c", "streamContent": "code"}}}
        }
        # editToolCall maps to "write_file" in _TOOL_CALL_NAME_MAP
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "```" in joined

    def test_todo_write_tool_call(self):
        data = {
            "subtype": "started",
            "tool_call": {"updateTodosToolCall": {"args": {
                "todos": [{"content": "step1", "status": "TODO_STATUS_COMPLETED"}]
            }}}
        }
        lines = list(_handle_tool_call_message(data, _get_action_map(), set()))
        joined = b"".join(lines).decode("utf-8")
        assert "step1" in joined
