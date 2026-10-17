import plugin.codemig.codemig_task_manager.query_processor as query_processor
import pytest
from common.response.response_code import ResponseCode
from plugin.codemig.ai_assistant.query_ai_handler import create_asm_file_content
from plugin.codemig.ai_assistant.query_ai_handler import create_asm_question_content
from plugin.codemig.ai_assistant.query_ai_handler import create_inline_asm_content
from plugin.codemig.ai_assistant.query_ai_handler import query_ai_suggestion_for_change
from plugin.codemig.codemig_task_manager.query_processor import SELECT_FILE_PATH_SQL
from plugin.codemig.codemig_task_manager.query_processor import SELECT_FILE_INFO_SQL
from plugin.codemig.codemig_task_manager.query_processor import SELECT_FILE_SQL
from plugin.codemig.codemig_task_manager.query_processor import SELECT_SUGGESTION_SQL
from plugin.codemig.codemig_task_manager.query_processor import SELECT_SUMMARY_SQL
from plugin.codemig.codemig_task_manager.query_processor import SELECT_TASK_FILE_SUMMARY_SQL
from plugin.codemig.codemig_task_manager.query_processor import create_data
from plugin.codemig.codemig_task_manager.query_processor import create_response_for_task
from plugin.codemig.codemig_task_manager.query_processor import query_change_from_database
from plugin.codemig.codemig_task_manager.query_processor import query_changes_for_file
from plugin.codemig.codemig_task_manager.query_processor import query_file_tree_from_database
from plugin.codemig.codemig_task_manager.query_processor import query_file_tree_processor
from plugin.codemig.codemig_task_manager.query_processor import query_task_from_database
# from plugin.codemig.codemig_task_manager.query_processor import SELECT_TASK_SQL
from plugin.codemig.codemig_task_manager.query_processor import query_user_task_files
from plugin.codemig.codemig_task_manager.query_processor import query_user_task_files_from_database
from plugin.codemig.codemig_task_manager.query_processor import query_user_tasks
from plugin.codemig.codemig_common.common_sql import SELECT_FILE_TREE_SQL
from plugin.codemig.dependence_process.req_file import PyProjectParser
from plugin.codemig.solver.solvers_mapping import SolverType

import os
from pathlib import Path
from unittest.mock import call
from unittest.mock import mock_open, patch

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))


@pytest.fixture
def mock_db_connection(mocker):
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch("plugin.codemig.codemig_task_manager.query_processor.get_conn",
                 return_value=mock_conn)
    return mock_cursor


def test_query_user_tasks_success(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_task_from_database',
        return_value=[True, [(1, 2)]])
    result = query_user_tasks("test_user")
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


def test_query_user_tasks_failed(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_task_from_database',
        return_value=[False, []])
    result = query_user_tasks("test_user")
    assert result['code'] == -1
    assert result['msg'] == "Database Error!"


def test_query_task_from_database(mocker):
    # Mock ORM 查询
    from plugin.codemig.codemig_task_manager.models import CodemigTasks
    from plugin.codemig.dependence_process.models import CodemigTaskDependence, DependencePackages
    from common.db.SQLOperation import db_session_scope
    
    # 创建模拟的任务对象
    mock_task1 = mocker.Mock()
    mock_task1.task_id = 1
    mock_task1.task_name = "task_alpha"
    mock_task1.is_scan_dependence = False
    
    mock_task2 = mocker.Mock()
    mock_task2.task_id = 2
    mock_task2.task_name = "task_beta"
    mock_task2.is_scan_dependence = False
    
    # Mock session 和查询
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_order_by = mocker.Mock()
    
    # 设置查询链
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.order_by.return_value = mock_order_by
    mock_order_by.all.return_value = [mock_task1, mock_task2]
    
    # Mock db_session_scope
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    result = query_task_from_database("test_user")
    assert result == (True, [(1, 'task_alpha', False, []), (2, 'task_beta', False, [])])


def test_query_user_task_files_failed(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_user_task_files_from_database',
        return_value=(False, "Database Error!"))
    result = query_user_task_files("test_user", 123, 0)
    assert result['code'] == -1
    assert result['msg'] == "Database Error!"


def test_query_user_task_files_success(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_user_task_files_from_database',
        return_value=(True, 1))
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.create_data', return_value=1)
    result = query_user_task_files("test_user", 123, 0)
    assert result['code'] == 0
    assert result['msg'] == 'ok'
    assert result['data'] == 1


def test_query_user_task_files_from_database(mock_db_connection, mocker):
    # Mock query_task_info_from_database
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.query_task_info_from_database',
                 return_value=(True, ("task_name", "time", False)))
    # Mock query_dir_id_by_task_id
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.query_dir_id_by_task_id',
                 return_value=(True, 456))  # dir_id = 456
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    # Mock Path.exists() method
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    # Mock 用户特定数据库连接（用于查询文件信息）
    mock_user_conn = mocker.Mock()
    mock_user_cursor = mocker.Mock()
    mock_user_conn.cursor.return_value = mock_user_cursor
    # SELECT_FILE_SQL 返回格式: (file_id, file_path, num_changed_lines)
    # SELECT_SUMMARY_SQL 返回格式: (suggestion_type, num_changes, num_changed_lines)
    # SELECT_TASK_FILE_SUMMARY_SQL 返回格式: (file_type, number_files)
    mock_user_cursor.fetchall.side_effect = [
        [(0, 10, 20), (1, 5, 10)],  # summary
        [(0, 3), (1, 2)],  # task_file_summary
        [(789, '/test/file1.txt', 5), (790, '/test/file2.txt', 3)]  # file_rows
    ]
    # Mock get_conn for user-specific database
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_conn',
                 return_value=mock_user_conn)
    result = query_user_task_files_from_database("test_user", 123, 0)
    # 返回值格式: (True, (task_name, created_time, summary, task_file_summary, select_file_info, is_scan_dependence))
    assert result[0] == True
    assert result[1][0] == "task_name"  # task_name
    assert result[1][1] == "time"  # created_time
    assert len(result[1][2]) == 2  # summary
    assert len(result[1][3]) == 2  # task_file_summary
    assert len(result[1][4]) == 2  # select_file_info
    assert result[1][5] == False  # is_scan_dependence
    # 验证用户数据库的调用（使用新的 SQL，不需要参数）
    from plugin.codemig.codemig_task_manager.query_processor import SELECT_SUMMARY_SQL, SELECT_TASK_FILE_SUMMARY_SQL, SELECT_FILE_SQL
    execute_expected_calls = [
        call(SELECT_SUMMARY_SQL),
        call(SELECT_TASK_FILE_SUMMARY_SQL),
        call(SELECT_FILE_SQL),
    ]
    mock_user_cursor.execute.assert_has_calls(execute_expected_calls, any_order=False)


def test_create_data_use_absolute_path(mocker):
    query_processor.USE_ABSOLUTE_PATH = True
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
        return_value="/mocked/data")
    user_name = "test_user"
    task_name = "Test Task"
    created_time = "2025-04-11 10:00:00"

    summary = [(0, 100, 200), (1, 300, 400)]
    task_file_summary = [(0, 111), (1, 222)]
    select_file_info = [
        (1, 101, 1001, "/mocked/data/test_user/101/changed/fileA.txt", 5),
        (1, 102, 1002, "/mocked/data/test_user/102/changed/fileB.txt", 3),
        (1, 101, 1003, "/mocked/data/test_user/101/changed/fileC.txt", 2),
    ]

    expected_directories = [
        "/mocked/data/test_user/101/changed",
        "/mocked/data/test_user/102/changed"
    ]

    data = (task_name, created_time, summary, task_file_summary,
            select_file_info, False)
    result = create_data(user_name, data)

    assert result["task_name"] == task_name
    assert result["created_time"] == created_time
    assert result["directories"] == expected_directories

    # Check files format and content
    assert result["files"] == [
        (1, 1, 101, 1001, "fileA.txt",
         "/mocked/data/test_user/101/changed/fileA.txt", 5),
        (2, 1, 102, 1002, "fileB.txt",
         "/mocked/data/test_user/102/changed/fileB.txt", 3),
        (3, 1, 101, 1003, "fileC.txt",
         "/mocked/data/test_user/101/changed/fileC.txt", 2),
    ]

    assert result["summary"] == [('Makefile', 100, 200), ('内联函数', 300, 400),
                                 ('源码扫描', 111, None), ('软件包扫描', 222, None)]


def test_create_data_use_relative_path(mocker):
    query_processor.USE_ABSOLUTE_PATH = False
    mocker.patch(
        'plugin.codemig.codemig_common.codemig_common_utils.get_codemig_data_path',
        return_value="/mocked/data")
    user_name = "test_user"
    task_name = "Test Task"
    created_time = "2025-04-11 10:00:00"

    summary = [(0, 100, 200), (1, 300, 400)]
    task_file_summary = [(0, 111), (1, 222)]
    select_file_info = [
        (1, 101, 1001, "/mocked/data/test_user/101/changed/fileA.txt", 5),
        (1, 102, 1002, "/mocked/data/test_user/102/changed/fileB.txt", 3),
        (1, 101, 1003, "/mocked/data/test_user/101/changed/fileC.txt", 2),
    ]

    expected_directories = [
        "./test_user/101/changed", "./test_user/102/changed"
    ]

    data = (task_name, created_time, summary, task_file_summary,
            select_file_info, False)
    result = create_data(user_name, data)

    assert result["task_name"] == task_name
    assert result["created_time"] == created_time
    assert result["directories"] == expected_directories

    # Check files format and content
    assert result["files"] == [
        (1, 1, 101, 1001, "fileA.txt", "./test_user/101/changed/fileA.txt", 5),
        (2, 1, 102, 1002, "fileB.txt", "./test_user/102/changed/fileB.txt", 3),
        (3, 1, 101, 1003, "fileC.txt", "./test_user/101/changed/fileC.txt", 2),
    ]
    assert result["summary"] == [('Makefile', 100, 200), ('内联函数', 300, 400),
                                 ('源码扫描', 111, None), ('软件包扫描', 222, None)]


def test_query_changes_for_file(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_change_from_database',
        return_value=(True, "/test_user/1/changed/abc.txt", [(1, 2, 3, "suggestion", 4, 5, False)]))
    # Mock query_original_file_from_git（query_changes_for_file 从 git 获取原始文件内容）
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.query_original_file_from_git',
        return_value=(True, "original content"))

    # Mock os.path.exists: 对 /original 和 /changed 路径都返回 True
    mock_exists = mocker.patch('os.path.exists')
    mock_exists.side_effect = lambda path: path in [
        "/test_user/1/changed/abc.txt",
        "/test_user/1/original/abc.txt"
    ]

    # original_file 来自 query_original_file_from_git（已 mock）；file 来自 open(file_path).read()
    m = mock_open()
    m.return_value.read.return_value = 'hello world'
    with patch('builtins.open', m):
        result = query_changes_for_file("test_user", 1, 2, 3)
        assert result['code'] == 0
        assert result['msg'] == 'ok'
        assert result['original_file'] == 'original content'
        assert result['file'] == 'hello world'
        assert result['changes'] == [(1, 2, 3, "suggestion", 4, 5, False)]


def test_query_change_from_database(mock_db_connection, mocker):
    mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = ("file_path", "changed", 0, 1)
    mock_cursor.fetchall.return_value = [1, 2]
    # Mock get_database_path and Path.exists()
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    # Mock get_conn for user-specific database
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_conn',
                 return_value=mock_conn)
    result = query_change_from_database("test_user", 11, 22, 33)
    assert result == (True, "file_path", [1, 2])
    execute_expected_calls = [
        call(SELECT_FILE_INFO_SQL, (33,)),
        call(SELECT_SUGGESTION_SQL, (33,)),
    ]
    mock_cursor.execute.assert_has_calls(execute_expected_calls, any_order=False)


def test_query_file_tree_processor(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.build_file_tree',
        return_value=["info_1", "info_2"])
    result = query_file_tree_processor("test_user", 123, 0, 1)
    assert result['code'] == 0
    assert result['msg'] == 'ok'
    assert result['file_tree'] == ["info_1", "info_2"]


def test_create_response_for_task_use_absolute_path(mocker):
    query_processor.USE_ABSOLUTE_PATH = True
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
        return_value="/mocked/data")
    task_id = "task-123"
    result = [("dir1", "file1", "/mocked/data/project1/fileA.txt"),
              ("dir1", "file2", "/mocked/data/project1/fileB.txt"),
              ("dir2", "file3", "/mocked/data/project2/fileC.txt")]

    actual = create_response_for_task(task_id, result)
    expected = [
        ("/mocked/data/project1", [("task-123", "dir1", "file1", "fileA.txt", "changed"),
                                   ("task-123", "dir1", "file2", "fileB.txt", "changed")]),
        ("/mocked/data/project2", [("task-123", "dir2", "file3", "fileC.txt", "changed")])
    ]
    assert actual == expected


def test_create_response_for_task_use_relative_path(mocker):
    query_processor.USE_ABSOLUTE_PATH = False
    mocker.patch(
        'plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
        return_value="/mocked/data")
    task_id = "task-123"
    result = [("dir1", "file1", "/mocked/data/project1/fileA.txt"),
              ("dir1", "file2", "/mocked/data/project1/fileB.txt"),
              ("dir2", "file3", "/mocked/data/project2/fileC.txt")]

    actual = create_response_for_task(task_id, result)
    expected = [("./project1", [("task-123", "dir1", "file1", "fileA.txt", "changed"),
                                ("task-123", "dir1", "file2", "fileB.txt", "changed")]),
                ("./project2", [("task-123", "dir2", "file3", "fileC.txt", "changed")])]
    assert actual == expected


def test_query_file_tree_from_database(mock_db_connection, mocker):
    mock_cursor = mock_db_connection
    mock_cursor.fetchall.return_value = [1, 2]
    # Mock get_database_path 和 Path.exists()
    db_path = Path('/test/db/path.db')
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=db_path)
    mocker.patch.object(Path, 'exists', return_value=True)
    # Mock get_conn for codemig_common_utils module
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    # query_file_tree_from_database 只需要 user_name 和 dir_id 两个参数
    result = query_file_tree_from_database("test_user", 11)
    assert result == (True, [1, 2])
    execute_expected_calls = [call(SELECT_FILE_TREE_SQL)]
    mock_cursor.execute.assert_has_calls(execute_expected_calls, any_order=False)


def test_create_asm_question_content_basic():
    """测试基本功能"""
    code = ["mov eax, ebx", "add eax, ecx"]
    suggestion = "优化寄存器使用"
    expected = "优化寄存器使用然后，请讲解一下生成的代码。\nmov eax, ebxadd eax, ecx"
    assert create_asm_question_content(code, suggestion) == expected


def test_create_inline_asm_content():
    file_path = Path(MODULE_PATH) / 'test_files' / 'incode_asm_aarch64.c'
    query_data = file_path.as_posix(), 123, 7, 7, "这是建议。", False
    actual = create_inline_asm_content(query_data)
    expected = "这是建议。然后，请讲解一下生成的代码。\n    asm volatile ();\n"
    assert actual == expected


def test_create_asm_file_content():
    file_path = Path(MODULE_PATH) / 'test_files' / 'hello_aarch64.s'
    query_data = file_path.as_posix(), 123, 100, 200, "这是建议。", False
    actual = create_asm_file_content(query_data)
    expected = "这是建议。然后，请讲解一下生成的代码。\n_start:\n    mov     x8, #64\n"
    assert actual == expected


# def test_query_ai_suggestion_for_change_incode_asm(mocker):
#     file_path = Path(MODULE_PATH) / 'test_files' / 'incode_asm_aarch64.c'
#     query_data = ('test', file_path.as_posix(), SolverType.INLINE_ASM.value, 7, 7, "这是建议。")
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_query_ai_suggestion_data',
#         return_value=query_data)
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion',
#         side_effect=lambda x, y: x)
#     request = mocker.Mock()
#     request.user_id = "test_user"
#     request.remote_addr = 1
#     mocker.patch('plugin.codemig.ai_assistant.query_ai_handler.UserDB.query_by_id',
#                  return_value=User(111, "test_user", "test_user", 'normal'))
#     params = {"user_name": "test_user", "task_id": 1, "dir_id": 2, "file_id": 3, "change_id": 4}
#     response = query_ai_suggestion_for_change(params, request)

#     expected = "这是建议。然后，请讲解一下生成的代码。\n    asm volatile ();\n"
#     assert response == expected


# def test_query_ai_suggestion_for_change_asm_file(mocker):
#     file_path = Path(MODULE_PATH) / 'test_files' / 'hello_aarch64.s'
#     query_data = ('test', file_path.as_posix(), SolverType.ASM_FILE.value, 100, 200, "这是建议。")
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_query_ai_suggestion_data',
#         return_value=query_data)
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion',
#         side_effect=lambda x, y: x)
#     request = mocker.Mock()
#     request.user_id = "test_user"
#     request.remote_addr = 1
#     mocker.patch('plugin.codemig.ai_assistant.query_ai_handler.UserDB.query_by_id',
#                  return_value=User(111, "test_user", "test_user", 'normal'))
#     params = {"user_name": "test_user", "task_id": 1, "dir_id": 2, "file_id": 3, "change_id": 4}
#     actual = query_ai_suggestion_for_change(params, request)
#     expected = "这是建议。然后，请讲解一下生成的代码。\n_start:\n    mov     x8, #64\n"
#     assert actual == expected


# def test_query_ai_suggestion_for_change_unsupported(mocker):
#     file_path = Path(MODULE_PATH) / 'test_files' / 'hello_aarch64.s'
#     query_data = ('test', file_path.as_posix(), 12, 100, 200, "这是建议。")
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_query_ai_suggestion_data',
#         return_value=query_data)
#     mocker.patch(
#         'plugin.codemig.ai_assistant.query_ai_handler.query_ai_suggestion',
#         side_effect=lambda x,y: x)
#     request = mocker.Mock()
#     request.user_id = "test_user"
#     request.remote_addr = 1
#     params = {"user_name": "test_user", "task_id": 1, "dir_id": 2, "file_id": 3, "change_id": 4}
#
#     actual = query_ai_suggestion_for_change(params, request)
#     assert str(actual) == "不支持的建议类型: SolverType.GO_SOURCE_CODE"


# 测试函数
def test_conversion():
    """测试转换函数"""
    test_cases = [
        ("requests ^1.5.3", "requests>=1.5.3, <2.0.0"),
        ("django ~3.2.0", "django>=3.2.0, <3.3.0"),
        ("numpy >=1.20.0", "numpy>=1.20.0"),
        ("pandas ==1.3.5", "pandas==1.3.5"),
        ("flask *", "flask"),
        ("click ^0.4.0", "click>=0.4.0, <0.5.0"),
        ("package ~1.2", "package>=1.2.0, <1.3.0"),
        ("package ==1.2.*", "package>=1.2.0, <1.3.0"),
        ("package", "package"),
    ]

    print("测试结果:")
    print("-" * 50)
    for input_spec, expected in test_cases:
        result = PyProjectParser._convert_dependency_line(input_spec)
        status = "✓" if result == expected else "✗"
        print(f"{status} 输入: {input_spec}")
        print(f"   期望: {expected}")
        print(f"   实际: {result}")
        print()


def test_query_dir_id_by_task_id_success(mocker):
    """测试成功查询 dir_id"""
    mock_session = mocker.Mock()
    mock_task_dir = mocker.Mock()
    mock_task_dir.dir_id = 123
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_task_dir
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_dir_id_by_task_id
    status, dir_id = query_dir_id_by_task_id(1)
    assert status == True
    assert dir_id == 123


def test_query_dir_id_by_task_id_not_found(mocker):
    """测试任务不存在的情况"""
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = None
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_dir_id_by_task_id
    status, dir_id = query_dir_id_by_task_id(999)
    assert status == True
    assert dir_id is None


def test_query_task_name_from_database_success(mocker):
    """测试成功查询任务名称"""
    mock_session = mocker.Mock()
    mock_task = mocker.Mock()
    mock_task.task_name = "test_task"
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_task
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_task_name_from_database
    status, task_name = query_task_name_from_database(1)
    assert status == True
    assert task_name == "test_task"


def test_query_task_name_from_database_not_found(mocker):
    """测试任务不存在的情况"""
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = None
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_task_name_from_database
    status, task_name = query_task_name_from_database(999)
    assert status == False
    assert task_name is None


def test_query_task_info_from_database_success(mocker):
    """测试成功查询任务信息"""
    from datetime import datetime
    mock_session = mocker.Mock()
    mock_task = mocker.Mock()
    mock_task.task_name = "test_task"
    mock_task.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_task.is_scan_dependence = True
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_task
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_task_info_from_database
    status, task_info = query_task_info_from_database(1)
    assert status == True
    assert task_info[0] == "test_task"
    assert task_info[1] == datetime(2023, 1, 1, 12, 0, 0)
    assert task_info[2] == True


def test_query_task_info_from_database_not_found(mocker):
    """测试任务不存在的情况"""
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = None
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.query_processor import query_task_info_from_database
    status, task_info = query_task_info_from_database(999)
    assert status == False
    assert task_info is None


def test_create_dir_path_absolute(mocker):
    """测试创建绝对路径"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', True)
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    from plugin.codemig.codemig_task_manager.query_processor import create_dir_path
    result = create_dir_path("test_user", 123)
    assert result == "/data/codemig/test_user/123/changed"


def test_create_dir_path_relative(mocker):
    """测试创建相对路径"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', False)
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    from plugin.codemig.codemig_task_manager.query_processor import create_dir_path
    result = create_dir_path("test_user", 123)
    assert result == "./test_user/123/changed"


def test_convert_summary(mocker):
    """测试转换汇总信息"""
    from plugin.codemig.codemig_task_manager.query_processor import convert_summary
    from plugin.codemig.codemig_common.migration_class import MigrationClass
    summary = [(0, 10, 20), (1, 5, 15)]
    task_file_summary = [(1, 3), (2, 5)]
    result = convert_summary(summary, task_file_summary)
    # MigrationClass(1) 是软件包扫描，MigrationClass(2) 是缺失架构文件
    assert result == [
        ('Makefile', 10, 20),
        ('内联函数', 5, 15),
        (MigrationClass(1).description, 3, None),
        (MigrationClass(2).description, 5, None)
    ]


def test_query_missing_file_from_database_success(mocker, mock_db_connection):
    """测试成功查询缺失文件"""
    mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = ("/test/file.txt",)
    mock_cursor.fetchall.return_value = [("arch1", 0), ("arch2", 1)]
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_conn',
                 return_value=mock_conn)
    from plugin.codemig.codemig_task_manager.query_processor import query_missing_file_from_database
    status, file_path, existing_arch_data = query_missing_file_from_database("test_user", 1, 2, 3)
    assert status == True
    assert file_path == "/test/file.txt"
    assert existing_arch_data == [("arch1", 0), ("arch2", 1)]


def test_query_missing_file_from_database_not_found(mocker, mock_db_connection):
    """测试文件不存在的情况：fetchone 返回 None 时返回失败状态"""
    mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = None
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_conn',
                 return_value=mock_conn)
    from plugin.codemig.codemig_task_manager.query_processor import query_missing_file_from_database
    status, file_path, arch_data = query_missing_file_from_database("test_user", 1, 2, 3)
    assert status is False
    assert file_path == []
    assert arch_data == []


def test_query_original_file_processor_success(mocker):
    """测试成功查询原始文件"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('builtins.open', mock_open(read_data="file content"))
    from plugin.codemig.codemig_task_manager.query_processor import query_original_file_processor
    result = query_original_file_processor("test_user", 1, 2, "test.txt")
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK
    assert result['file_content'] == "file content"


def test_query_original_file_processor_not_found(mocker):
    """测试文件不存在的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('os.path.exists', return_value=False)
    from plugin.codemig.codemig_task_manager.query_processor import query_original_file_processor
    result = query_original_file_processor("test_user", 1, 2, "test.txt")
    assert result['code'] == -1
    assert result['msg'] == "File not found"


def test_find_parent_and_file_name_ex_absolute(mocker):
    """测试绝对路径下的父路径和文件名提取"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', True)
    from plugin.codemig.codemig_task_manager.query_processor import find_parent_and_file_name_ex
    parent, file_name = find_parent_and_file_name_ex("/path/to/file.txt", "/path/to")
    assert parent == "/path/to"
    assert file_name == "file.txt"


def test_find_parent_and_file_name_ex_relative(mocker):
    """测试相对路径下的父路径和文件名提取"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', False)
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.add_dot_slash',
                 side_effect=lambda x: f"./{x}")
    from plugin.codemig.codemig_task_manager.query_processor import find_parent_and_file_name_ex
    parent, file_name = find_parent_and_file_name_ex("/path/to/file.txt", "/path")
    assert parent == "./to"
    assert file_name == "file.txt"


def test_find_parent_and_file_name_absolute(mocker):
    """测试绝对路径下的父路径和文件名提取（使用 get_codemig_data_path）"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', True)
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    from plugin.codemig.codemig_task_manager.query_processor import find_parent_and_file_name
    parent, file_name = find_parent_and_file_name("/data/codemig/user/1/file.txt")
    assert parent == "/data/codemig/user/1"
    assert file_name == "file.txt"


def test_find_parent_and_file_name_relative(mocker):
    """测试相对路径下的父路径和文件名提取（使用 get_codemig_data_path）"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', False)
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.add_dot_slash',
                 side_effect=lambda x: f"./{x}")
    from plugin.codemig.codemig_task_manager.query_processor import find_parent_and_file_name
    parent, file_name = find_parent_and_file_name("/data/codemig/user/1/file.txt")
    assert parent == "./user/1"
    assert file_name == "file.txt"


def test_create_response_for_task_with_missing(mocker):
    """测试创建包含缺失文件的任务响应"""
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('plugin.codemig.codemig_task_manager.query_processor.USE_ABSOLUTE_PATH', True)
    from plugin.codemig.codemig_task_manager.query_processor import create_response_for_task_with_missing
    # 函数期望格式: (dir_id, file_id, file_path, is_missing)
    result = [
        (2, 3, "/data/codemig/user/1/file1.txt", "missing"),
        (2, 4, "/data/codemig/user/1/file2.txt", "changed")
    ]
    actual = create_response_for_task_with_missing(100, result)
    assert len(actual) == 1
    assert actual[0][0] == "/data/codemig/user/1"
    assert len(actual[0][1]) == 2
    assert actual[0][1][0] == (100, 2, 3, "file1.txt", "missing")
    assert actual[0][1][1] == (100, 2, 4, "file2.txt", "changed")
