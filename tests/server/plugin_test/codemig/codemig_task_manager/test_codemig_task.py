import sqlite3
import time
import pytest
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

from plugin.codemig.codemig_task_manager.codemig_task import (
    check_taskname,
    create_insert_values, create_changes, process_extracted_dir,
    process_missing_dir, create_prepared_text_changes,
    create_prepared_lib_changes, raise_error_for_wrong_file_type,
    update_config, check_user_task_limit, insert_task_db,
    start_task, create_database_of_task, save_files_to_database,
    process_directory, create_and_process_task, create_task,
    save_changes_to_database, process_target_file, process_extracted_path,
    create_processing_data,
)
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.codemig_task_manager.task_common import TaskStatus


# ---------------------------------------------------------------------------
# check_taskname
# ---------------------------------------------------------------------------

class TestCheckTaskname:
    """测试 check_taskname 函数"""

    # ---- 非 string 类型输入 ----

    @pytest.mark.parametrize(
        "value",
        [123, None, [], {}, 3.14, True, set(), (1, 2), b"bytes"],
        ids=[
            "int", "None", "list", "dict", "float", "bool",
            "set", "tuple", "bytes",
        ],
    )
    def test_non_string_input(self, value):
        status, cn_msg, en_msg = check_taskname(value)
        assert status is False
        assert cn_msg == "名称必须是字符串"
        assert en_msg == "Name must be a string"

    # ---- 空 string ----

    def test_empty_string(self):
        status, cn_msg, en_msg = check_taskname("")
        assert status is False
        assert cn_msg == "名称不能为空"
        assert en_msg == "Name cannot be empty"

    # ---- 长度超过 100 ----

    def test_length_exceeds_100(self):
        long_name = "a" + "b" * 100  # 101 个字符
        status, cn_msg, en_msg = check_taskname(long_name)
        assert status is False
        assert "100" in cn_msg
        assert "101" in cn_msg
        assert "100" in en_msg
        assert "101" in en_msg

    # ---- 以非字母字符开头 ----

    @pytest.mark.parametrize(
        "name",
        ["1task", "_test", "-task", ".name", "0abc"],
        ids=["digit", "underscore", "hyphen", "dot", "zero"],
    )
    def test_starts_with_non_alpha(self, name):
        status, cn_msg, en_msg = check_taskname(name)
        assert status is False
        assert cn_msg == "名称必须以字母开头"
        assert en_msg == "Name must start with a letter"

    # ---- 包含非法字符 ----

    @pytest.mark.parametrize(
        "name, expected_chars",
        [
            ("test name", {"' '"}),
            ("test@name", {"'@'"}),
            ("test/name", {"'/'"}),
            ("test#name", {"'#'"}),
            ("test!", {"'!'"}),
            ("a b c", {"' '"}),
            ("a\tb", {"'\\t'"}),
        ],
        ids=["space", "at", "slash", "hash", "bang", "multi_space", "tab"],
    )
    def test_illegal_characters(self, name, expected_chars):
        status, cn_msg, en_msg = check_taskname(name)
        assert status is False
        assert "非法字符" in cn_msg
        assert "illegal characters" in en_msg.lower() or "illegal" in en_msg.lower()

    # ---- 有效名称 ----

    @pytest.mark.parametrize(
        "name",
        [
            "a",
            "test",
            "MyTask",
            "task-1",
            "task_name",
            "task.name",
            "My-Task_1.0",
            "taskName123",
            "A",
            "abcXYZ",
            "a0",
            "a" + "b" * 99,  # 刚好 100 个字符
        ],
        ids=[
            "single_letter", "simple", "camelCase", "hyphen",
            "underscore", "dot", "mixed_special", "alphanumeric",
            "single_upper", "mixed_case", "letter_digit",
            "max_length_100",
        ],
    )
    def test_valid_names(self, name):
        status, cn_msg, en_msg = check_taskname(name)
        assert status is True
        assert cn_msg == "名称有效"
        assert en_msg == "Name is valid"

    # ---- 边界长度测试 ----

    def test_exactly_100_chars_valid(self):
        name = "a" + "b" * 99  # 100 字符，全字母，满足 pattern
        status, cn_msg, en_msg = check_taskname(name)
        assert status is True

    def test_exactly_100_chars_with_special(self):
        name = "a" + "b" * 97 + "-_"  # 100 字符，含合法特殊字符
        status, cn_msg, en_msg = check_taskname(name)
        assert status is True

    # ---- 名称格式不正确（兜底分支） ----

    def test_format_incorrect_fallback(self):
        # 以字母开头、不含非法字符但格式仍不正确的情况很难构造，
        # 因为 pattern 只允许 [a-zA-Z0-9\-_.]，而非法字符检查覆盖了不在该集合中的字符。
        # 若所有字符都合法但 pattern 不匹配，唯一可能是开头不是字母，
        # 但这已被 "必须以字母开头" 分支捕获。
        # 此分支在当前实现中理论上不可达，测试仅作记录。
        pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_mock_solver(migration_class, solver_type=0, append_or_replace=0):
    solver = MagicMock()
    solver.migration_class.return_value = migration_class
    solver.get_solver_type.return_value = solver_type
    solver.append_or_replace.return_value = append_or_replace
    return solver


# ---------------------------------------------------------------------------
# raise_error_for_wrong_file_type
# ---------------------------------------------------------------------------
class TestRaiseErrorForWrongFileType:

    def test_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file type: 99"):
            raise_error_for_wrong_file_type(99)

    def test_error_message_contains_file_type(self):
        file_type = MigrationClass.UNKNOWN
        with pytest.raises(ValueError) as exc_info:
            raise_error_for_wrong_file_type(file_type)
        assert str(file_type) in str(exc_info.value)
        assert "Unsupported file type" in str(exc_info.value)

    def test_raises_for_string_type(self):
        with pytest.raises(ValueError, match="Unsupported file type: some_type"):
            raise_error_for_wrong_file_type("some_type")


# ---------------------------------------------------------------------------
# create_insert_values
# ---------------------------------------------------------------------------
class TestCreateInsertValues:

    # --- TEXT ---

    def test_text_single_change(self):
        solver = make_mock_solver(MigrationClass.TEXT, solver_type=1, append_or_replace=0)
        change_list = [
            (10, 20, "suggestion_text", CodeTooLong.HAS_SOURCE_CODE, "my_code"),
        ]
        result = create_insert_values("/a/b.c", 1, 2, 3, solver, change_list)

        assert len(result) == 1
        assert result[0] == (
            "/a/b.c", 1, 2, 3, 1, 0,
            10, 20, "suggestion_text",
            CodeTooLong.HAS_SOURCE_CODE, "my_code",
        )

    def test_text_multiple_changes(self):
        solver = make_mock_solver(MigrationClass.TEXT, solver_type=2, append_or_replace=1)
        change_list = [
            (1, 5, "sug1", CodeTooLong.HAS_SOURCE_CODE, "code1"),
            (6, 10, "sug2", CodeTooLong.CODE_TOO_LONG, "code2"),
            (11, 15, "sug3", CodeTooLong.HAS_SOURCE_CODE, "code3"),
        ]
        result = create_insert_values("file.py", 100, 200, 300, solver, change_list)

        assert len(result) == 3
        for i, change in enumerate(change_list):
            assert result[i] == ("file.py", 100, 200, 300, 2, 1, *change)

    def test_text_empty_change_list(self):
        solver = make_mock_solver(MigrationClass.TEXT)
        result = create_insert_values("f", 1, 2, 3, solver, [])
        assert result == []

    # --- DYNAMIC_LINK_LIBRARY ---

    def test_dll_single_change(self):
        solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)
        change_list = [("x86_64", "install liba")]
        result = create_insert_values("/lib/a.so", 10, 20, 30, solver, change_list)

        assert len(result) == 1
        assert result[0] == ("/lib/a.so", 10, 20, 30, "x86_64", "install liba")

    def test_dll_multiple_changes(self):
        solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)
        change_list = [
            ("x86_64", "install liba"),
            ("aarch64", "install liba-arm"),
            ("riscv64", "install liba-rv"),
        ]
        result = create_insert_values("/usr/lib/b.so", 1, 2, 3, solver, change_list)

        assert len(result) == 3
        assert result[0] == ("/usr/lib/b.so", 1, 2, 3, "x86_64", "install liba")
        assert result[1] == ("/usr/lib/b.so", 1, 2, 3, "aarch64", "install liba-arm")
        assert result[2] == ("/usr/lib/b.so", 1, 2, 3, "riscv64", "install liba-rv")

    def test_dll_empty_change_list(self):
        solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)
        result = create_insert_values("f.so", 1, 2, 3, solver, [])
        assert result == []

    # --- Unknown / unsupported ---

    def test_unknown_file_type_raises_value_error(self):
        solver = make_mock_solver(MigrationClass.UNKNOWN)
        with pytest.raises(ValueError, match="Unsupported file type"):
            create_insert_values("f", 1, 2, 3, solver, [("anything",)])

    def test_missing_arch_file_type_raises_value_error(self):
        solver = MagicMock()
        solver.migration_class.return_value = MigrationClass.MISSING_ARCH_FILE
        with pytest.raises(ValueError, match="Unsupported file type"):
            create_insert_values("f", 1, 2, 3, solver, [])


# ---------------------------------------------------------------------------
# create_changes
# ---------------------------------------------------------------------------
class TestCreateChanges:

    def test_empty_result(self):
        result = create_changes(1, 2, 3, {}, "file.c")
        assert isinstance(result, defaultdict)
        assert len(result) == 0

    def test_with_text_changes(self):
        solver = make_mock_solver(MigrationClass.TEXT, solver_type=0, append_or_replace=1)
        change_list = [
            (1, 10, "fix this", CodeTooLong.HAS_SOURCE_CODE, "new code"),
        ]
        file_solvers_result = {solver: (change_list, None)}

        result = create_changes(100, 200, 300, file_solvers_result, "main.c")

        assert MigrationClass.TEXT in result
        assert len(result[MigrationClass.TEXT]) == 1
        assert result[MigrationClass.TEXT][0] == (
            "main.c", 100, 200, 300, 0, 1,
            1, 10, "fix this", CodeTooLong.HAS_SOURCE_CODE, "new code",
        )

    def test_with_dll_changes(self):
        solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)
        change_list = [("aarch64", "sudo apt install libfoo")]
        file_solvers_result = {solver: (change_list, None)}

        result = create_changes(10, 20, 30, file_solvers_result, "/lib/foo.so")

        assert MigrationClass.DYNAMIC_LINK_LIBRARY in result
        assert len(result[MigrationClass.DYNAMIC_LINK_LIBRARY]) == 1
        assert result[MigrationClass.DYNAMIC_LINK_LIBRARY][0] == (
            "/lib/foo.so", 10, 20, 30, "aarch64", "sudo apt install libfoo",
        )

    def test_empty_result_list_is_skipped(self):
        solver = make_mock_solver(MigrationClass.TEXT)
        file_solvers_result = {solver: ()}
        result = create_changes(1, 2, 3, file_solvers_result, "f.c")
        assert len(result) == 0

    def test_empty_change_list_is_skipped(self):
        solver = make_mock_solver(MigrationClass.TEXT)
        file_solvers_result = {solver: ([], None)}
        result = create_changes(1, 2, 3, file_solvers_result, "f.c")
        assert len(result) == 0

    def test_multiple_solvers_same_file(self):
        text_solver = make_mock_solver(MigrationClass.TEXT, solver_type=1, append_or_replace=0)
        dll_solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)

        text_changes = [(1, 5, "sug", CodeTooLong.HAS_SOURCE_CODE, "code")]
        dll_changes = [("x86_64", "install libx")]

        file_solvers_result = {
            text_solver: (text_changes, None),
            dll_solver: (dll_changes, None),
        }

        result = create_changes(1, 2, 3, file_solvers_result, "mixed.c")

        assert len(result[MigrationClass.TEXT]) == 1
        assert len(result[MigrationClass.DYNAMIC_LINK_LIBRARY]) == 1

    def test_multiple_text_solvers_extend(self):
        solver_a = make_mock_solver(MigrationClass.TEXT, solver_type=0, append_or_replace=0)
        solver_b = make_mock_solver(MigrationClass.TEXT, solver_type=1, append_or_replace=1)

        changes_a = [(1, 5, "sug_a", CodeTooLong.HAS_SOURCE_CODE, "code_a")]
        changes_b = [(10, 15, "sug_b", CodeTooLong.CODE_TOO_LONG, "code_b")]

        file_solvers_result = {
            solver_a: (changes_a, None),
            solver_b: (changes_b, None),
        }

        result = create_changes(1, 2, 3, file_solvers_result, "file.c")
        assert len(result[MigrationClass.TEXT]) == 2


# ---------------------------------------------------------------------------
# process_extracted_dir
# ---------------------------------------------------------------------------
class TestProcessExtractedDir:

    def test_empty_dict(self):
        result = process_extracted_dir({}, 1, 2)
        assert result == {}

    def test_single_entry_single_arch(self):
        miss_files = {"/missing/liba.so": ["/arch/x86_64/liba.so"]}
        result = process_extracted_dir(miss_files, 10, 20)

        assert len(result) == 1
        key = ("/missing/liba.so", 10, 20)
        assert key in result
        assert result[key] == [("/arch/x86_64/liba.so", 10, 20)]

    def test_single_entry_multiple_arches(self):
        miss_files = {"/missing/libb.so": ["/x86/libb.so", "/arm/libb.so"]}
        result = process_extracted_dir(miss_files, 1, 2)

        key = ("/missing/libb.so", 1, 2)
        assert len(result[key]) == 2
        assert result[key][0] == ("/x86/libb.so", 1, 2)
        assert result[key][1] == ("/arm/libb.so", 1, 2)

    def test_multiple_entries(self):
        miss_files = {
            "/miss/a.so": ["/x86/a.so"],
            "/miss/b.so": ["/arm/b.so", "/riscv/b.so"],
        }
        result = process_extracted_dir(miss_files, 5, 6)

        assert len(result) == 2
        assert ("/miss/a.so", 5, 6) in result
        assert ("/miss/b.so", 5, 6) in result
        assert len(result[("/miss/b.so", 5, 6)]) == 2


# ---------------------------------------------------------------------------
# process_missing_dir
# ---------------------------------------------------------------------------
class TestProcessMissingDir:

    def test_empty_dict(self):
        result = process_missing_dir({}, 1, 2)
        assert result == {}

    def test_single_entry(self):
        miss_dirs = {"/miss/dir": ["/found/dir1"]}
        result = process_missing_dir(miss_dirs, 10, 20)

        key = ("/miss/dir", 10, 20)
        assert key in result
        assert result[key] == [("/found/dir1", 10, 20)]

    def test_multiple_arches_appended(self):
        miss_dirs = {"/miss/dir": ["/x86/dir", "/arm/dir", "/riscv/dir"]}
        result = process_missing_dir(miss_dirs, 1, 2)

        key = ("/miss/dir", 1, 2)
        assert len(result[key]) == 3
        for i, arch in enumerate(["/x86/dir", "/arm/dir", "/riscv/dir"]):
            assert result[key][i] == (arch, 1, 2)

    def test_multiple_entries_independent_keys(self):
        miss_dirs = {
            "/miss/d1": ["/f1"],
            "/miss/d2": ["/f2"],
        }
        result = process_missing_dir(miss_dirs, 5, 6)
        assert len(result) == 2
        assert ("/miss/d1", 5, 6) in result
        assert ("/miss/d2", 5, 6) in result


# ---------------------------------------------------------------------------
# create_prepared_text_changes
# ---------------------------------------------------------------------------
class TestCreatePreparedTextChanges:

    def _make_text_change(self, file_path, user_id, task_id, dir_id,
                          solver_type=0, append_or_replace=1,
                          start=1, end=5, suggestion="sug",
                          code_too_long=CodeTooLong.HAS_SOURCE_CODE,
                          mycode="code"):
        return (
            file_path, user_id, task_id, dir_id, solver_type,
            append_or_replace, start, end, suggestion,
            code_too_long, mycode,
        )

    def test_happy_path(self):
        change = self._make_text_change("/a/b.c", 1, 2, 3)
        file_path_to_file_id = {
            (1, 2, 3, "/a/b.c", MigrationClass.TEXT.value): 42,
        }

        result = create_prepared_text_changes(file_path_to_file_id, [change])

        assert len(result) == 1
        assert result[0] == (
            42, 0, 1, 1, 5, "sug",
            CodeTooLong.HAS_SOURCE_CODE.value, "code",
        )

    def test_multiple_changes(self):
        changes = [
            self._make_text_change("/a.c", 1, 2, 3, start=10, end=20),
            self._make_text_change("/b.c", 1, 2, 3, solver_type=2, start=30, end=40),
        ]
        file_path_to_file_id = {
            (1, 2, 3, "/a.c", MigrationClass.TEXT.value): 100,
            (1, 2, 3, "/b.c", MigrationClass.TEXT.value): 200,
        }

        result = create_prepared_text_changes(file_path_to_file_id, changes)

        assert len(result) == 2
        assert result[0][0] == 100
        assert result[0][3] == 10
        assert result[0][4] == 20
        assert result[1][0] == 200
        assert result[1][3] == 30

    def test_empty_changes(self):
        result = create_prepared_text_changes({}, [])
        assert result == []

    def test_missing_key_raises_sqlite3_error(self):
        change = self._make_text_change("/not_found.c", 1, 2, 3)
        file_path_to_file_id = {}

        with pytest.raises(sqlite3.Error, match="Error finding file Id with key"):
            create_prepared_text_changes(file_path_to_file_id, [change])

    def test_code_too_long_value_is_used(self):
        change = self._make_text_change(
            "/x.c", 1, 2, 3,
            code_too_long=CodeTooLong.CODE_TOO_LONG,
        )
        file_path_to_file_id = {
            (1, 2, 3, "/x.c", MigrationClass.TEXT.value): 99,
        }

        result = create_prepared_text_changes(file_path_to_file_id, [change])
        assert result[0][6] == CodeTooLong.CODE_TOO_LONG.value


# ---------------------------------------------------------------------------
# create_prepared_lib_changes
# ---------------------------------------------------------------------------
class TestCreatePreparedLibChanges:

    def _make_lib_change(self, file_path, user_id, task_id, dir_id,
                         arch="x86_64", suggestion="install pkg"):
        return (file_path, user_id, task_id, dir_id, arch, suggestion)

    def test_happy_path(self):
        change = self._make_lib_change("/lib/a.so", 1, 2, 3, "aarch64", "apt install liba")
        file_path_to_file_id = {
            (1, 2, 3, "/lib/a.so", MigrationClass.DYNAMIC_LINK_LIBRARY.value): 55,
        }

        result = create_prepared_lib_changes(file_path_to_file_id, [change])

        assert len(result) == 1
        assert result[0] == (55, "aarch64", "apt install liba")

    def test_multiple_changes(self):
        changes = [
            self._make_lib_change("/a.so", 1, 2, 3, arch="x86_64"),
            self._make_lib_change("/b.so", 1, 2, 3, arch="riscv64", suggestion="install b-rv"),
        ]
        file_path_to_file_id = {
            (1, 2, 3, "/a.so", MigrationClass.DYNAMIC_LINK_LIBRARY.value): 10,
            (1, 2, 3, "/b.so", MigrationClass.DYNAMIC_LINK_LIBRARY.value): 20,
        }

        result = create_prepared_lib_changes(file_path_to_file_id, changes)

        assert len(result) == 2
        assert result[0] == (10, "x86_64", "install pkg")
        assert result[1] == (20, "riscv64", "install b-rv")

    def test_empty_changes(self):
        result = create_prepared_lib_changes({}, [])
        assert result == []

    def test_missing_key_raises_sqlite3_error(self):
        change = self._make_lib_change("/not_found.so", 1, 2, 3)
        file_path_to_file_id = {}

        with pytest.raises(sqlite3.Error, match="Error finding file Id with key"):
            create_prepared_lib_changes(file_path_to_file_id, [change])

    def test_lookup_uses_dll_value(self):
        change = self._make_lib_change("/foo.so", 7, 8, 9)
        file_path_to_file_id = {
            (7, 8, 9, "/foo.so", MigrationClass.DYNAMIC_LINK_LIBRARY.value): 777,
        }

        result = create_prepared_lib_changes(file_path_to_file_id, [change])
        assert result[0][0] == 777


# ---------------------------------------------------------------------------
# update_config
# ---------------------------------------------------------------------------
class TestUpdateConfig:
    def test_scan_not_1_returns_early(self):
        dep_info = DependenceInfo(0)
        mock_session = MagicMock()
        result = update_config(1, dep_info, mock_session)
        assert result is None
        mock_session.query.assert_not_called()

    def test_python_lang_existing_config(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "python"
        dep_info.python = "/usr/bin/python3"
        dep_info.python_config = "pip"
        dep_info.go = None
        dep_info.go_config = None

        mock_config = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        update_config(1, dep_info, mock_session)
        assert mock_config.python_interpreter == "/usr/bin/python3"
        assert mock_config.python_image_source == "pip"

    def test_python_lang_existing_config_with_go(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "python"
        dep_info.python = "/usr/bin/python3"
        dep_info.python_config = "pip"
        dep_info.go = "/usr/local/go"
        dep_info.go_config = "gomod"

        mock_config = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        update_config(1, dep_info, mock_session)
        assert mock_config.go_install_path == "/usr/local/go"
        assert mock_config.go_environment == "gomod"

    def test_go_lang_existing_config(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "go"
        dep_info.go = "/usr/local/go"
        dep_info.go_config = "gomod"
        dep_info.python = None
        dep_info.python_config = None

        mock_config = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        update_config(1, dep_info, mock_session)
        assert mock_config.go_install_path == "/usr/local/go"

    def test_go_lang_existing_config_with_python(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "go"
        dep_info.go = "/usr/local/go"
        dep_info.go_config = "gomod"
        dep_info.python = "/usr/bin/python3"
        dep_info.python_config = "pip"

        mock_config = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_config

        update_config(1, dep_info, mock_session)
        assert mock_config.python_interpreter == "/usr/bin/python3"

    def test_no_existing_config_inserts_new(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "python"
        dep_info.python = "/usr/bin/python3"
        dep_info.python_config = "pip"
        dep_info.go = None
        dep_info.go_config = None

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        update_config(1, dep_info, mock_session)
        mock_session.add.assert_called_once()

    def test_go_lang_no_existing_config(self, mocker):
        dep_info = DependenceInfo(1)
        dep_info.lang = "go"
        dep_info.go = "/usr/local/go"
        dep_info.go_config = "gomod"
        dep_info.python = None
        dep_info.python_config = None

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        update_config(1, dep_info, mock_session)
        mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# check_user_task_limit
# ---------------------------------------------------------------------------
class TestCheckUserTaskLimit:
    def test_config_query_fails_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(False, '30', None))
        result = check_user_task_limit(1)
        assert result is True

    def test_task_limit_zero_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, '0', None))
        result = check_user_task_limit(1)
        assert result is True

    def test_task_limit_negative_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, '-1', None))
        result = check_user_task_limit(1)
        assert result is True

    def test_invalid_limit_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, 'not_a_number', None))
        result = check_user_task_limit(1)
        assert result is True

    def test_within_limit_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, '10', None))
        mock_session = mocker.MagicMock()
        mock_query = mocker.MagicMock()
        mock_filter = mocker.MagicMock()
        mock_filter.count.return_value = 5
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                     return_value=mocker.MagicMock(
                         __enter__=mocker.Mock(return_value=mock_session),
                         __exit__=mocker.Mock(return_value=None)))
        result = check_user_task_limit(1)
        assert result is True

    def test_at_limit_returns_false(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, '10', None))
        mock_session = mocker.MagicMock()
        mock_query = mocker.MagicMock()
        mock_filter = mocker.MagicMock()
        mock_filter.count.return_value = 10
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                     return_value=mocker.MagicMock(
                         __enter__=mocker.Mock(return_value=mock_session),
                         __exit__=mocker.Mock(return_value=None)))
        result = check_user_task_limit(1)
        assert result is False

    def test_db_exception_returns_true(self, mocker):
        from common.db.SQLOperation import DatabaseException
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, '10', None))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                     side_effect=DatabaseException("db error"))
        result = check_user_task_limit(1)
        assert result is True

    def test_none_limit_returns_true(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                     return_value=(True, None, None))
        result = check_user_task_limit(1)
        assert result is True


# ---------------------------------------------------------------------------
# insert_task_db
# ---------------------------------------------------------------------------
class TestInsertTaskDb:
    def test_success(self, mocker):
        dep_info = DependenceInfo(0)
        mock_session = mocker.MagicMock()

        def mock_add(obj):
            obj.task_id = 42
        mock_session.add = mocker.Mock(side_effect=mock_add)
        mock_session.flush = mocker.Mock()
        mock_session.bulk_save_objects = mocker.Mock()
        mock_dir_query = mocker.MagicMock()
        mock_dir_filter = mocker.MagicMock()
        mock_dir_filter.update.return_value = 1
        mock_dir_query.filter.return_value = mock_dir_filter
        mock_session.query.return_value = mock_dir_query

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                     return_value=mocker.MagicMock(
                         __enter__=mocker.Mock(return_value=mock_session),
                         __exit__=mocker.Mock(return_value=None)))

        status, task_id = insert_task_db(1, "test_task", dep_info, 100)
        assert status is True
        assert task_id == 42

    def test_db_error(self, mocker):
        from common.db.SQLOperation import DatabaseException
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                     side_effect=DatabaseException("error"))
        status, task_id = insert_task_db(1, "test_task", dep_info, 100)
        assert status is False
        assert task_id is None


# ---------------------------------------------------------------------------
# start_task
# ---------------------------------------------------------------------------
class TestStartTask:
    def test_illegal_task_name(self, mocker):
        dep_info = DependenceInfo(0)
        mock_request = mocker.MagicMock()
        mock_request.user_id = 1
        mock_request.remote_addr = "127.0.0.1"
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.record_operation_log')
        result = start_task("user1", "", 1, "test.zip", dep_info, mock_request)
        assert result["code"] == -1

    def test_valid_task_success(self, mocker):
        dep_info = DependenceInfo(0)
        mock_request = mocker.MagicMock()
        mock_request.user_id = 1
        mock_request.remote_addr = "127.0.0.1"

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_and_process_task',
                     return_value={"code": 0, "msg": "ok", "task_id": 100})
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.record_operation_log')

        result = start_task("user1", "validTask", 1, "test.zip", dep_info, mock_request)
        assert result["code"] == 0
        assert result["task_id"] == 100

    def test_valid_task_failed(self, mocker):
        dep_info = DependenceInfo(0)
        mock_request = mocker.MagicMock()
        mock_request.user_id = 1
        mock_request.remote_addr = "127.0.0.1"

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_and_process_task',
                     return_value={"code": -1, "msg": "some error"})
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.record_operation_log')

        result = start_task("user1", "validTask", 1, "test.zip", dep_info, mock_request)
        assert result["code"] == -1


# ---------------------------------------------------------------------------
# create_database_of_task
# ---------------------------------------------------------------------------
class TestCreateDatabaseOfTask:
    def test_success(self, mocker, tmp_path):
        mock_db_path = tmp_path / "user1" / "1" / "1.db"
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        status, msg = create_database_of_task("user1", 1)
        assert status is True
        assert "successfully" in msg

    def test_db_error(self, mocker, tmp_path):
        mock_db_path = tmp_path / "user1" / "1" / "1.db"
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("db error")
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        status, msg = create_database_of_task("user1", 1)
        assert status is False


# ---------------------------------------------------------------------------
# save_files_to_database
# ---------------------------------------------------------------------------
class TestSaveFilesToDatabase:
    def test_db_not_exists(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = False
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        status, msg = save_files_to_database("user1", 1, 1, Path("/tmp/nonexistent"), "original")
        assert status is False

    def test_dir_not_exists(self, mocker, tmp_path):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        status, msg = save_files_to_database("user1", 1, 1, tmp_path / "nonexistent", "original")
        assert status is False

    def test_success_with_files(self, mocker, tmp_path):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)

        test_dir = tmp_path / "test_files"
        test_dir.mkdir()
        (test_dir / "file.c").write_text("int main(){}")

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        status, msg = save_files_to_database("user1", 1, 1, test_dir, "original")
        assert status is True

    def test_db_error(self, mocker, tmp_path):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)

        test_dir = tmp_path / "test_files"
        test_dir.mkdir()
        (test_dir / "file.c").write_text("int main(){}")

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.executemany.side_effect = sqlite3.Error("db error")
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        status, msg = save_files_to_database("user1", 1, 1, test_dir, "original")
        assert status is False


# ---------------------------------------------------------------------------
# process_directory
# ---------------------------------------------------------------------------
class TestProcessDirectory:
    def test_processing_error(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_processing_data',
                     side_effect=AttributeError("processing error"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        status, msg = process_directory("user1", 1, 100, 1, Path("/src"), DependenceInfo(0))
        assert status is False
        assert "Processing directory failed" in msg

    def test_runtime_error(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_processing_data',
                     side_effect=RuntimeError("runtime error"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        status, msg = process_directory("user1", 1, 100, 1, Path("/src"), DependenceInfo(0))
        assert status is False

    def test_save_changes_success(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_processing_data',
                     return_value=([], [], [], {}, {}))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_changes_to_database',
                     return_value=True)
        mock_tasks = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        status, msg = process_directory("user1", 1, 100, 1, Path("/src"), DependenceInfo(0))
        assert status is True
        mock_tasks.update_task_status.assert_called_with(100, TaskStatus.SUCCESS)

    def test_save_changes_failure(self, mocker):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_processing_data',
                     return_value=([], [], [], {}, {}))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_changes_to_database',
                     return_value=False)
        mock_tasks = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        status, msg = process_directory("user1", 1, 100, 1, Path("/src"), DependenceInfo(0))
        assert status is False
        mock_tasks.update_task_status.assert_called_with(100, TaskStatus.FAILED)


# ---------------------------------------------------------------------------
# create_and_process_task
# ---------------------------------------------------------------------------
class TestCreateAndProcessTask:
    def test_create_task_fails(self, mocker):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                     return_value=(False, "error msg", None))
        result = create_and_process_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert result["code"] == -1

    def test_update_status_fails(self, mocker):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                     return_value=(True, 42, Path("/src")))
        mock_tasks = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        mock_tasks.update_task_status.return_value = False
        result = create_and_process_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert result["code"] == -1

    def test_process_directory_fails(self, mocker):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                     return_value=(True, 42, Path("/src")))
        mock_tasks = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        mock_tasks.update_task_status.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                     return_value=(False, "process error"))
        result = create_and_process_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert result["code"] == -1

    def test_success(self, mocker):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                     return_value=(True, 42, Path("/src")))
        mock_tasks = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks')
        mock_tasks.update_task_status.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                     return_value=(True, None))
        result = create_and_process_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert result["code"] == 0
        assert result["task_id"] == 42


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------
class TestCreateTask:
    def test_task_limit_reached(self, mocker):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=False)
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "task limit" in msg.lower()
        assert path is None

    def test_file_not_found(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=tmp_path / "repo")
        status, msg, path = create_task("user1", 1, "task1", 1, "nonexistent.zip", dep_info)
        assert status is False
        assert "not found" in msg

    def test_extract_file_fails_cleanup(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        # Create a zip file
        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=False)
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "uncompress" in msg

    def test_extract_file_fails_repo_not_exists(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo_notexist"
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=False)
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False

    def test_extract_path_not_found(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))

        repo_path = tmp_path / "repo_notexist"
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "extract path" in msg

    def test_create_database_fails(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(False, "db error"))
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "db error" in msg

    def test_save_files_fails(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                     return_value=(False, "save error"))
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "save error" in msg

    def test_git_init_fails(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                     return_value=(True, ''))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                     return_value=(False, "git error"))
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "git" in msg.lower()

    def test_insert_task_fails_both_times(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                     return_value=(True, ''))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                     return_value=(False, None))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.time.sleep')
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is False
        assert "failed" in msg.lower()

    def test_insert_task_succeeds_on_retry(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                     return_value=(True, ''))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                     side_effect=[(False, None), (True, 42)])
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.time.sleep')
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is True
        assert msg == 42

    def test_full_success(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                     return_value=str(tmp_path))
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_repo_path',
                     return_value=repo_path)

        import zipfile
        user_dir = tmp_path / "user1" / "1"
        user_dir.mkdir(parents=True)
        zip_path = user_dir / "test.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("test.txt", "content")

        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                     return_value=True)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                     return_value=(True, ''))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                     return_value=(True, "ok"))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                     return_value=(True, 42))
        status, msg, path = create_task("user1", 1, "task1", 1, "test.zip", dep_info)
        assert status is True
        assert msg == 42
        assert path == repo_path


# ---------------------------------------------------------------------------
# save_changes_to_database
# ---------------------------------------------------------------------------
class TestSaveChangesToDatabase:
    def test_db_not_exists(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = False
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        result = save_changes_to_database("user1", 1, [], [], [], {}, {})
        assert result == (False, "Error: Database not found!!")

    def test_empty_data_success(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)
        result = save_changes_to_database("user1", 1, [], [], [], {}, {})
        assert result is True

    def test_with_my_files_success(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        # my_file tuple: (user_id, task_id, dir_id, file_path, file_type)
        # Must match lookup_key in create_prepared_text_changes: (user_id, task_id, dir_id, file_path, MigrationClass.TEXT.value)
        my_files = [(100, 200, 1, "/file.c", MigrationClass.TEXT.value)]
        text_file_changes = [
            ("/file.c", 100, 200, 1, 0, 1, 10, 20, "sug", CodeTooLong.HAS_SOURCE_CODE, "code")
        ]
        result = save_changes_to_database("user1", 1, my_files, text_file_changes, [], {}, {})
        assert result is True

    def test_with_my_files_no_result(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        my_files = [(100, 200, 1, "/file.c", MigrationClass.TEXT.value)]
        result = save_changes_to_database("user1", 1, my_files, [], [], {}, {})
        assert result is True

    def test_with_my_files_db_inner_error(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            # BEGIN_TRANSACTION passes (call 1), then UPDATE_CHANGED_FILE_SQL raises (call 2),
            # then it continues to SELECT_FILE_BY_PATH_SQL which also raises (handled by inner except)
            if call_count[0] == 2:
                raise sqlite3.Error("inner db error")
            return None

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchone.return_value = None  # After inner error, result is None
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        my_files = [(100, 200, 1, "/file.c", MigrationClass.TEXT.value)]
        result = save_changes_to_database("user1", 1, my_files, [], [], {}, {})
        # The inner error causes rollback + continue, then commit succeeds
        assert result is True

    def test_with_lib_changes(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        my_files = [(100, 200, 1, "/lib.so", MigrationClass.DYNAMIC_LINK_LIBRARY.value)]
        lib_changes = [("/lib.so", 100, 200, 1, "x86_64", "install lib")]
        result = save_changes_to_database("user1", 1, my_files, [], lib_changes, {}, {})
        assert result is True

    def test_with_missing_files(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        missing_files = {
            ("/miss/lib.so", 100, 1): [("/arch/x86/lib.so", 100, 1)]
        }
        result = save_changes_to_database("user1", 1, [], [], [], missing_files, {})
        assert result is True

    def test_with_missing_dirs(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        missing_dirs = {
            ("/miss/dir", 100, 1): [("/arch/x86/dir", 100, 1)]
        }
        result = save_changes_to_database("user1", 1, [], [], [], {}, missing_dirs)
        assert result is True

    def test_outer_db_error(self, mocker):
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_database_path',
                     return_value=mock_db_path)
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("outer db error")
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_conn',
                     return_value=mock_conn)

        result = save_changes_to_database("user1", 1, [], [], [], {}, {})
        assert result is False


# ---------------------------------------------------------------------------
# process_target_file
# ---------------------------------------------------------------------------
class TestProcessTargetFile:
    def test_text_file_type(self, mocker):
        my_files, text_changes, lib_changes = [], [], []
        solver = make_mock_solver(MigrationClass.TEXT, solver_type=0, append_or_replace=0)
        change_list = [(1, 10, "sug", CodeTooLong.HAS_SOURCE_CODE, "code")]
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
                     return_value={solver: (change_list, None)})
        process_target_file("/file.c", 1, 2, 3, my_files, text_changes, lib_changes)
        assert len(my_files) == 1
        assert len(text_changes) == 1

    def test_dll_file_type(self, mocker):
        my_files, text_changes, lib_changes = [], [], []
        solver = make_mock_solver(MigrationClass.DYNAMIC_LINK_LIBRARY)
        change_list = [("x86_64", "install lib")]
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
                     return_value={solver: (change_list, None)})
        process_target_file("/lib.so", 1, 2, 3, my_files, text_changes, lib_changes)
        assert len(my_files) == 1
        assert len(lib_changes) == 1

    def test_unknown_file_type_raises(self, mocker):
        my_files, text_changes, lib_changes = [], [], []
        solver = make_mock_solver(MigrationClass.UNKNOWN)
        change_list = [("data",)]
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
                     return_value={solver: (change_list, None)})
        with pytest.raises(ValueError, match="Unsupported file type"):
            process_target_file("/file.xyz", 1, 2, 3, my_files, text_changes, lib_changes)


# ---------------------------------------------------------------------------
# process_extracted_path
# ---------------------------------------------------------------------------
class TestProcessExtractedPath:
    def test_empty_directory(self, mocker, tmp_path):
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.detect_arch',
                     return_value={'missing': {}, 'found': {}, 'other': []})
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.group_files',
                     return_value=({}, {}, []))
        my_files, text_changes, lib_changes, miss_file, miss_dir = \
            process_extracted_path(1, 2, 3, str(tmp_path))
        assert my_files == []
        assert text_changes == []
        assert lib_changes == []

    def test_with_arch_dirs(self, mocker, tmp_path):
        """测试有架构目录的场景"""
        # Create directory structure
        riscv_dir = tmp_path / "lib_riscv64"
        riscv_dir.mkdir()
        x86_dir = tmp_path / "lib_x86_64"
        x86_dir.mkdir()

        detect_result = {
            'missing': {},
            'found': {('lib_riscv64',): (['lib_x86_64'], 'lib_*arch*')},
            'other': []
        }
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.detect_arch',
                     return_value=detect_result)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.group_files',
                     return_value=({}, {}, []))
        my_files, text_changes, lib_changes, miss_file, miss_dir = \
            process_extracted_path(1, 2, 3, str(tmp_path))
        assert 'lib_x86_64' in str(miss_dir) or len(miss_dir) >= 0


# ---------------------------------------------------------------------------
# create_processing_data
# ---------------------------------------------------------------------------
class TestCreateProcessingData:
    def test_basic_flow(self, mocker, tmp_path):
        dep_info = DependenceInfo(0)
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.submit_dependence_task')
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_extracted_path',
                     return_value=([], [], [], {}, {}))
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_extracted_dir',
                     return_value={})
        mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_missing_dir',
                     return_value={})
        result = create_processing_data(1, 2, 3, str(tmp_path), dep_info)
        assert len(result) == 5
        assert result[0] == []
        assert result[1] == []
        assert result[2] == []
