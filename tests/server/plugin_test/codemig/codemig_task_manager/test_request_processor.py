import pytest
from common.response.response_code import ResponseCode
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_task_manager.codemig_task import *
from plugin.codemig.codemig_task_manager.request_processor import *
from plugin.codemig.codemig_task_manager.task_common import TaskStatus
from plugin.codemig.solver.makefile_solver import MakefileSolver

import os
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import override
from unittest.mock import patch, call

from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.codemig_common.common_sql import SELECT_FILE_PATH_SQL, \
    INSERT_SUGGESTION_WITH_IGNORE_SQL, REMOVE_SUGGESTION_OF_FILE_SQL
from plugin.codemig.codemig_common.codemig_common_utils import BEGIN_TRANSACTION

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))


@pytest.fixture
def mock_db_connection(mocker):
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 123  # 确保 lastrowid 为 123
    mocker.patch("plugin.codemig.codemig_task_manager.codemig_task.get_conn",
                 return_value=mock_conn)
    mocker.patch("plugin.codemig.codemig_task_manager.request_processor.get_conn",
                 return_value=mock_conn)
    return mock_cursor


# 测试 create_and_process_task 函数的正常情况
def test_create_and_process_task_success(mocker):
    # 模拟 create_task 返回成功和有效的 task_id
    # create_task 返回值格式: (status: bool, msg: int|str, extract_path_original: Path|None)
    # 成功时: (True, task_id, extract_path_original)
    mock_extract_path = Path('test/extract/path')
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                 return_value=(True, 100, mock_extract_path))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks.update_task_status',
                 return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                 return_value=(True, None))
    dependencies_data = DependenceInfo(0)
    result = create_and_process_task("test_user", 1, "test_task", 1, 'test.zip',
                                     dependencies_data)

    # 断言返回值
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK
    assert result['task_id'] == 100


# 测试 create_and_process_task 时遇到数据库错误
def test_create_and_process_task_db_error(mocker):
    # 模拟 create_task 返回 False（表示失败）
    # create_task 返回值格式: (status: bool, msg: int|str, extract_path_original: Path|None)
    # 失败时: (False, error_message, None)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                 return_value=(False, 'insert test_task into database failed', None))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks.update_task_status',
                 return_value=True)
    dependencies_data = DependenceInfo(0)
    result = create_and_process_task("test_user", 1, "test_task", 1, 'test.zip',
                                     dependencies_data)

    # 断言返回值
    assert result['code'] == -1
    assert 'insert test_task into database failed' in result['msg']


# 测试 create_and_process_task 时遇到后台处理错误
def test_create_and_process_task_backend_error(mocker):
    # 模拟 create_task 返回成功和有效的 task_id，但 process_directory 失败
    # create_task 返回值格式: (status: bool, msg: int|str, extract_path_original: Path|None)
    # 成功时: (True, task_id, extract_path_original)
    mock_extract_path = Path('test/extract/path')
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_task',
                 return_value=(True, 100, mock_extract_path))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks.update_task_status',
                 return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                 return_value=(False, "error"))
    dependencies_data = DependenceInfo(0)
    result = create_and_process_task("test_user", 1, "test_task", 1, 'test.zip',
                                     dependencies_data)

    # 断言返回值
    assert result['code'] == -1
    assert "Backend Error!" in result['msg']


def test_create_task_success(mocker):
    # Mock SysConfig.query_system_configuration
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                 return_value=(True, '30', None))
    
    # Mock session 和查询
    mock_session = mocker.Mock()
    
    # Mock check_user_task_limit 中的 count 查询
    mock_count_query = mocker.Mock()
    mock_count_filter = mocker.Mock()
    mock_count_filter.count = mocker.Mock(return_value=0)  # 用户任务数量为 0，未超过限制
    mock_count_query.filter.return_value = mock_count_filter
    
    # Mock insert_task_db 中的操作
    # 需要 mock session.add 和 session.flush，但保持 new_task 是真实对象
    def mock_add(obj):
        # 当调用 session.add(new_task) 时，设置 task_id
        if hasattr(obj, '__class__') and 'CodemigTasks' in str(obj.__class__):
            obj.task_id = 100
    
    mock_session.add = mocker.Mock(side_effect=mock_add)
    mock_session.flush = mocker.Mock()
    
    # Mock CodemigTasks 查询（用于获取 task_id，但实际上不需要，因为 task_id 从对象获取）
    mock_task_query = mocker.Mock()
    mock_task_filter = mocker.Mock()
    mock_task_query.filter.return_value = mock_task_filter
    
    # Mock CodemigDirectoryStorage 的 update 操作
    mock_dir_query = mocker.Mock()
    mock_dir_filter = mocker.Mock()
    mock_dir_filter.update = mocker.Mock(return_value=2)
    mock_dir_query.filter.return_value = mock_dir_filter
    
    # 设置查询链：根据不同的模型返回不同的查询对象
    def query_side_effect(model):
        model_name = str(model)
        if 'CodemigTasks' in model_name:
            # 第一次调用是 count，第二次是 first
            if not hasattr(query_side_effect, 'call_count'):
                query_side_effect.call_count = 0
            query_side_effect.call_count += 1
            if query_side_effect.call_count == 1:
                return mock_count_query
            else:
                return mock_task_query
        elif 'CodemigDirectoryStorage' in model_name:
            return mock_dir_query
        return mock_count_query
    
    query_side_effect.call_count = 0
    mock_session.query.side_effect = query_side_effect
    
    # Mock db_session_scope
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    # Mock update_config 函数
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.update_config',
                 return_value=None)
    
    # Mock CodemigTaskDirectory 和 CodemigDirectoryStorage 的批量操作
    mock_session.bulk_save_objects = mocker.Mock()
    
    # Mock insert_task_db 函数（直接 mock，因为测试重点是 create_task 的整体流程）
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                 return_value=(True, 100))
    # Mock git commit (create_task 内部会调用 commit_git_repo)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                 return_value=(True, None))
    
    # Mock 文件系统操作
    mock_extract_path = Path('test/extract/path')
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                 return_value='/test/data')
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                 return_value=True)
    # Mock Path methods properly
    original_exists = Path.exists
    original_unlink = Path.unlink
    def mock_exists(self):
        return True
    def mock_unlink(self):
        pass
    mocker.patch.object(Path, 'exists', mock_exists)
    mocker.patch.object(Path, 'unlink', mock_unlink)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                 return_value=(True, None))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                 return_value=(True, None))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                 return_value=(True, 100))
    
    # 测试正常情况
    # create_task 签名: (user_id, user_name, task_name, dir_id, zip_name, dep_info)
    dependencies_data = DependenceInfo(0)
    result = create_task("test_user", 1, "test_task", 1, 'test.zip', dependencies_data)
    # 断言返回值格式: (status: bool, msg: int|str, extract_path_original: Path|None)
    assert result[0] == True  # status
    assert result[1] == 100  # task_id
    assert result[2] is not None  # extract_path_original


# 测试用例：模拟数据库错误的情况
def test_create_task_database_error(mocker):
    # Mock SysConfig.query_system_configuration
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.SysConfig.query_system_configuration',
                 return_value=(True, '30', None))
    
    # Mock check_user_task_limit
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.check_user_task_limit',
                 return_value=True)
    # Mock git commit (create_task 内部会调用 commit_git_repo)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.commit_git_repo',
                 return_value=(True, None))
    
    # Mock 文件系统操作
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.get_codemig_data_path',
                 return_value='/test/data')
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.extract_file',
                 return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_database_of_task',
                 return_value=(True, ''))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_files_to_database',
                 return_value=(True, ''))
    # Mock Path methods properly
    def mock_exists(self):
        return True
    def mock_unlink(self):
        pass
    mocker.patch.object(Path, 'exists', mock_exists)
    mocker.patch.object(Path, 'unlink', mock_unlink)
    # Mock insert_task_db 函数，模拟数据库错误（两次都失败）
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.insert_task_db',
                 return_value=(False, None))
    
    dependencies_data = DependenceInfo(0)
    # 测试数据库操作失败时的异常
    # create_task 签名: (user_id, user_name, task_name, dir_id, zip_name, dep_info)
    result = create_task("test_user", 1, "test_task", 1, 'test.zip', dependencies_data)
    # 断言返回错误信息格式: (status: bool, msg: int|str, extract_path_original: Path|None)
    assert result[0] == False  # status
    assert 'insert test_task into database failed' in result[1]  # error message
    assert result[2] is None  # extract_path_original


# def test_process_task_success(mocker):
def process_task_success(mocker):
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_task_status',
                 return_value=False)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                 return_value=False)
    # result = process_task("user1", 123, 456, [1, 2, 3])
    # assert result == False


# def test_process_task_failed(mocker):
def process_task_failed(mocker):
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_task_status',
                 return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_directory',
                 return_value=None)
    # result = process_task("user1", 123, 456, [1, 2, 3])
    # assert result == (True, 'Error: updating the task status to processing!!!')


# def test_process_extracted_dir():
def process_extracted_dir():
    """测试正常情况下的处理逻辑"""
    # 准备测试数据
    extract_path = "/test/extract/path"
    user_id = 123
    dir_id = 456

    mock_dir_solver = {
        "/original/missing/path1": [
            "/original/arch/path1", "/original/arch/path2"
        ],
        "/original/missing/path2": ["/original/arch/path3"]
    }

    with patch('plugin.codemig.main.dir_solver.DirSolver.solve',
               return_value=mock_dir_solver) as mock_solve, \
            patch(
                'plugin.codemig.codemig_task_manager.codemig_task.create_changed_path') as mock_create, \
            patch(
                'plugin.codemig.codemig_common.codemig_common_utils.move_file_to_new_path') as mock_move:
        # 设置 create_changed_path 的模拟行为
        mock_create.side_effect = lambda x: x.replace("/original", "/tmp/changed")

        # 调用被测函数
        result = process_extracted_dir(extract_path, user_id, dir_id)

        # 验证返回结果
        expected_result = {
            ("/changed/missing/path1", 123, 456): [
                ("/changed/arch/path1", 123, 456),
                ("/changed/arch/path2", 123, 456)
            ],
            ("/changed/missing/path2", 123, 456): [("/changed/arch/path3", 123,
                                                    456)]
        }
        assert result == expected_result

        # 验证路径转换函数调用
        assert mock_create.call_count == 5  # 2 missing + 3 arch 路径转换
        mock_create.assert_any_call("/original/missing/path1")
        mock_create.assert_any_call("/original/arch/path1")

        # 验证文件移动函数调用
        assert mock_move.call_count == 3
        mock_move.assert_any_call("/original/arch/path1", "/changed/arch/path1")
        mock_move.assert_any_call("/original/arch/path2", "/changed/arch/path2")
        mock_move.assert_any_call("/original/arch/path3", "/changed/arch/path3")

        # 验证 DirSolver.solve 调用
        mock_solve.assert_called_once_with(extract_path)


def test_update_task_status_success(mocker):
    # Mock session 和查询
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    
    # Mock ORM 更新操作
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.update = mocker.Mock(return_value=1)  # 更新了 1 条记录
    
    # Mock db_session_scope
    mocker.patch('plugin.codemig.codemig_task_manager.models.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    result = CodemigTasks.update_task_status(1, TaskStatus.PROCESSING)
    assert result == True
    # 验证 update 被调用
    mock_filter.update.assert_called_once()


def test_save_changes_to_database(mocker, mock_db_connection):
    mock_cursor = mock_db_connection
    mock_cursor.lastrowid = 100  # 模拟 lastrowid
    # Mock fetchone() 返回文件 ID (file_id)
    mock_cursor.fetchone.return_value = (4,)  # 返回 file_id = 4
    
    # my_files 格式: (user_id, task_id, dir_id, file_path, type)
    # file_path 使用字符串路径
    # type: 0 = TEXT, 1 = DYNAMIC_LINK_LIBRARY
    my_files = [(1, 2, 3, '/test/path/file.txt', MigrationClass.TEXT.value),
                (1, 2, 3, '/test/path/lib.so', MigrationClass.DYNAMIC_LINK_LIBRARY.value),
                (1, 2, 3, '/test/path/lib2.so', MigrationClass.DYNAMIC_LINK_LIBRARY.value)]
    # text_file_changes 格式: (file_path, user_id, task_id, dir_id, solver_type, append_or_replace,
    #                          start_lineno, end_lineno, suggestion, code_too_long, mycode)
    my_changes = [('/test/path/file.txt', 1, 2, 3, 0, 2, 10, 20, 'suggestion', CodeTooLong.HAS_SOURCE_CODE, 'mycode'),
                  ('/test/path/file.txt', 1, 2, 3, 0, 2, 30, 40, 'suggestion2', CodeTooLong.HAS_SOURCE_CODE, 'mycode2')]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_prepared_text_changes',
                 return_value=my_changes)
    # lib_file_changes 格式: (file_path, user_id, task_id, dir_id, support_architecture, suggestion)
    my_lib_changes = [('/test/path/lib.so', 1, 2, 3, 'x86_64', 'suggestion'),
                      ('/test/path/lib2.so', 1, 2, 3, 'riscv64', 'suggestion2')]
    tmp_missing_files_results = {
        ("missing_path1", 1, 2): [("arch_path1", 1, 2), ("arch_path2", 1, 2)],
        ("missing_path2", 1, 3): [("arch_path3", 1, 3)]
    }
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_prepared_lib_changes',
                 return_value=my_lib_changes)
    # Mock update_task_status
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks.update_task_status',
                 return_value=True)
    mock_db_path = Path('/test/test_user/123/123.db')
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=mock_db_path)
    # Mock Path.exists() method
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    mocker.patch('os.path.exists', return_value=True)
    result = save_changes_to_database("test_user",123, my_files, my_changes, my_lib_changes,
                                      tmp_missing_files_results, [])
    assert result == True


def test_save_changes_to_database_error(mocker, mock_db_connection):
    mock_cursor = mock_db_connection
    my_files = [(1, 2, 3, 4, 5)]
    my_changes = [(999, 888, 777, 666, 555, 444, 333, 222, 111),
                  (123, 234, 345, 456, 567, 678, 789, 890, 901)]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_prepared_text_changes',
                 return_value=my_changes)
    my_lib_changes = [(111, 222, 333, 444, 555, 666),
                      (123, 234, 345, 456, 567, 678)]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_prepared_lib_changes',
                 return_value=my_lib_changes)
    tmp_missing_files_results = {
        ("missing_path1", 1, 2): [("arch_path1", 1, 2), ("arch_path2", 1, 2)],
        ("missing_path2", 1, 3): [("arch_path3", 1, 3)]
    }
    mock_cursor.execute.side_effect = sqlite3.Error("模拟的数据库错误")
    mock_db_path = Path('/test/test_user/123/123.db')
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=mock_db_path)
    # Mock Path.exists() method
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    mocker.patch('os.path.exists', return_value=True)
    result = save_changes_to_database("test_user", 123, my_files, my_changes, my_lib_changes,
                                      tmp_missing_files_results, [])
    assert result == False
    # execute_expected_calls = [call(UPDATE_TASK_STATUS, (3, 123)), ]
    # mock_cursor.execute.assert_has_calls(execute_expected_calls, any_order=True)


def test_save_updated_file_with_content_query_error(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, None))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_new_path',
                 return_value='/data')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.write_temp_file',
                 return_value=None)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.process_updated_file',
        return_value=[])
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.update_file_suggestion_to_database',
        return_value=(True))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.remove_file_and_move_edited_file',
        return_value=None)
    # save_updated_file_with_content 签名: (user_name, dir_id, file_id, content)
    result = save_updated_file_with_content("test_user", 33, 44, '55')
    assert result['code'] == -1
    assert result['msg'] == 'Database query error!!!'


def test_save_updated_file_with_content_db_error(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/abc/123'))
    # Mock git commit before operation
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.commit_git_repo',
        return_value=(True, ('git_hash', 'git_message', 'git_time')))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_new_path',
                 return_value='/data')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.write_temp_file',
                 return_value=None)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.process_updated_file',
        return_value=[])
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.update_file_suggestion_to_database',
        return_value=(False))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.remove_file_and_move_edited_file',
        return_value=None)
    # save_updated_file_with_content 签名: (user_name, dir_id, file_id, content)
    result = save_updated_file_with_content("test_user", 33, 44, '55')
    assert result['code'] == -1
    assert result['msg'] == 'Database update or insert error!!!'


def test_save_updated_file_with_content_success(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/abc/123'))
    # Mock git commit operations (before and after)
    mock_commit_git_repo = mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.commit_git_repo',
        return_value=(True, ('git_hash', 'git_message', 'git_time')))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_new_path',
                 return_value='/data')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.write_temp_file',
                 return_value=None)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.process_updated_file',
        return_value=[])
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.update_file_suggestion_to_database',
        return_value=(True))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.remove_file_and_move_edited_file',
        return_value=None)
    # save_updated_file_with_content 签名: (user_name, dir_id, file_id, content)
    result = save_updated_file_with_content("test_user", 33, 44, '55')
    assert result['code'] == 0
    assert result['msg'] == 'ok'
    # 验证git commit被调用了两次（before和after）
    assert mock_commit_git_repo.call_count == 2
    # 验证调用参数
    mock_commit_git_repo.assert_any_call("test_user", 33, "manual", "before",
                                         src="codemig-file-change-view", reason="user-save")
    mock_commit_git_repo.assert_any_call("test_user", 33, "manual", "after",
                                         src="codemig-file-change-view", reason="user-save")


def test_save_updated_file_with_content_success_with_new_file_id(mocker):
    """测试成功保存文件更新并返回新文件ID"""
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/abc/123'))
    # Mock git commit operations (before and after)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.commit_git_repo',
        return_value=(True, None))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_new_path',
                 return_value='/data')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.write_temp_file',
                 return_value=None)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.process_updated_file',
        return_value=[])
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.update_file_suggestion_to_database',
        return_value=(True))  # 返回新文件ID
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.remove_file_and_move_edited_file',
        return_value=None)
    # save_updated_file_with_content 签名: (user_name, dir_id, file_id, content)
    result = save_updated_file_with_content("test_user", 33, 44, '55')
    assert result['code'] == 0
    assert result['msg'] == 'ok'
    assert result['new_file_id'] == 44


def test_save_updated_file_with_content_git_commit_failure(mocker):
    """测试git commit失败的情况（应该继续执行，只记录警告）"""
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/abc/123'))
    # Mock git commit失败
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.commit_git_repo',
        return_value=(False, "Git commit failed"))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_new_path',
                 return_value='/data')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.write_temp_file',
                 return_value=None)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.process_updated_file',
        return_value=[])
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.update_file_suggestion_to_database',
        return_value=(True))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.remove_file_and_move_edited_file',
        return_value=None)
    # save_updated_file_with_content 签名: (user_name, dir_id, file_id, content)
    result = save_updated_file_with_content("test_user", 33, 44, '55')
    # git commit失败不应该影响整体流程，应该仍然成功
    assert result['code'] == 0
    assert result['msg'] == 'ok'


def test_create_tmp_parent(mocker):
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value='/base/data')
    tmp_parent = create_tmp_parent('/base/data/1/2/3/4/5/6/7/8/9/file.txt')
    assert tmp_parent == '/base/data/1/2/3'


def test_process_updated_file():
    suggestion = "此处参数可能与架构相关，请修改为RISCV支持的参数"
    test_path = os.path.realpath(
        os.path.join(MODULE_PATH, "../../codemig/solver/test_files/makefile_solver/Makefile"))
    # process_updated_file 签名: (file_id, temp_path)
    # 返回值格式: (file_id, solver_type, append_or_replace, start_lineno, end_lineno, suggestion, code_too_long, mycode)
    result = process_updated_file(1, test_path)
    # 检查返回值的格式和内容
    assert len(result) > 0
    # 检查第一个元素的格式
    assert len(result[0]) == 9  # 9个元素
    assert result[0][0] == 1  # file_id
    assert result[0][1] == 0  # solver_type (MakefileSolver)
    assert result[0][2] == 2  # append_or_replace
    # 其他字段根据实际返回值调整


def test_query_file_path_from_database(mock_db_connection, mocker):
    mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = ('/test/path',)
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    mocker.patch('os.path.exists', return_value=True)
    result, file_path = query_file_path_from_database('test_user', 11, 11111)
    assert result == True
    assert file_path == '/test/path'
    execute_expected_calls = [call(SELECT_FILE_PATH_SQL, (11111,)), ]
    mock_cursor.execute.assert_has_calls(execute_expected_calls, any_order=False)


def test_update_file_suggestion_to_database(mocker, mock_db_connection):
    mock_cursor = mock_db_connection
    mock_cursor.lastrowid = 123
    my_changes = [(999, 888, 777, 666, 555, 444, 333, 222, 0),
                  (123, 234, 345, 456, 567, 678, 789, 890, 0)]
    mock_db_path = Path('/test/db/path.db')
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=mock_db_path)
    # Mock Path.exists() method
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor._match_ignored_suggestion')
    # update_file_suggestion_to_database 签名: (user_name, dir_id, file_id, my_changes)
    result = update_file_suggestion_to_database("test_user", 222, 444, my_changes)
    assert result == (True)
    execute_expected_calls = [
        call(BEGIN_TRANSACTION),
        call(REMOVE_SUGGESTION_OF_FILE_SQL, (444,)),
    ]
    mock_cursor.execute.assert_has_calls(execute_expected_calls, any_order=False)
    executemany_expected_calls = [call(INSERT_SUGGESTION_WITH_IGNORE_SQL, my_changes), ]
    mock_cursor.executemany.assert_has_calls(executemany_expected_calls, any_order=False)


def test_process_directory(mocker, tmp_path):
    test_path = tmp_path / 'abc' / '3' / 'original'
    test_path.mkdir(parents=True, exist_ok=True)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value=str(tmp_path))
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.extract_file',
                 return_value=None)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_extracted_path',
                 return_value=([1], [], [], {}, {}))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_changes_to_database',
                 return_value=True)
    dependencies_data = DependenceInfo(0)
    status, message = process_directory("abc", 1, 2, 3, test_path, dependencies_data)
    assert status == True
    assert message == None


def test_process_directory_has_error(mocker, tmp_path):
    test_path = tmp_path / 'abc' / '3' / 'original'
    test_path.mkdir(parents=True, exist_ok=True)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value=str(tmp_path))
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.extract_file',
                 return_value=None)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.process_extracted_path',
                 return_value=([1], [], [], {}, {}))
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.save_changes_to_database',
                 return_value=False)
    dependencies_data = DependenceInfo(0)
    status, message = process_directory("abc", 1, 2, 3, test_path, dependencies_data)
    assert status == False
    assert message == 'Error: Failed to save changes to database!!!'


def test_process_directory_something_went_wrong(mocker):
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_processing_data',
                 side_effect=RuntimeError("Something went wrong"))
    # Mock update_task_status
    mock_update_task_status = mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.CodemigTasks.update_task_status',
                                          return_value=True)
    dependencies_data = DependenceInfo(0)
    # process_directory 签名: (user_name, user_id, task_id, dir_id, source_path, dep_info)
    test_path = Path('/test/path')
    status, error_msg = process_directory("abc", 1, 222, 3, test_path, dependencies_data)
    assert status == False
    assert error_msg == "Processing directory failed: Something went wrong"
    # 验证 update_task_status 被调用，参数为 task_id=222, status=TaskStatus.FAILED
    mock_update_task_status.assert_called_once()


def test_raise_error_for_wrong_file_type():
    """测试函数是否正确抛出 ValueError 异常"""
    unsupported_type = "invalid_type"

    # 验证是否抛出 ValueError 异常
    with pytest.raises(ValueError) as exc_info:
        raise_error_for_wrong_file_type(unsupported_type)

    # 验证异常消息是否正确
    assert str(exc_info.value) == "Error: Unsupported file type: invalid_type."


def test_logger_error_called(caplog):
    """测试是否正确记录了错误日志"""
    unsupported_type = "invalid_type"
    expected_error_msg = f"Error: Unsupported file type: invalid_type."

    # 确保函数会抛出异常
    with pytest.raises(ValueError):
        raise_error_for_wrong_file_type(unsupported_type)

    # 验证日志记录
    assert expected_error_msg in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)


def test_process_target_file(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
        return_value={})
    file_type_and_changes = defaultdict(list)
    file_type_and_changes[MigrationClass.TEXT] = [1]
    file_type_and_changes[MigrationClass.DYNAMIC_LINK_LIBRARY] = [2]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_changes',
                 return_value=file_type_and_changes)

    my_files, text_file_changes, lib_file_changes = [], [], []
    process_target_file(MODULE_PATH, 1, 2, 3, my_files, text_file_changes, lib_file_changes)

    assert my_files == [(1, 2, 3, MODULE_PATH, 0), (1, 2, 3, MODULE_PATH, 1)]
    assert text_file_changes == [1]
    assert lib_file_changes == [2]


def test_process_target_file_no_change(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
        return_value={})
    file_type_and_changes = defaultdict(list)
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_changes',
                 return_value=file_type_and_changes)

    my_files, text_file_changes, lib_file_changes = [], [], []
    process_target_file(MODULE_PATH, 1, 2, 3, my_files, text_file_changes, lib_file_changes)

    assert my_files == []
    assert text_file_changes == []
    assert lib_file_changes == []


def test_process_target_file_wrong_file_type(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
        return_value={})
    file_type_and_changes = defaultdict(list)
    file_type_and_changes[MigrationClass.UNKNOWN] = [3]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_changes',
                 return_value=file_type_and_changes)

    with pytest.raises(ValueError) as exc_info:
        process_target_file(MODULE_PATH, 1, 2, 3, [], [], [])

    # 验证异常消息是否正确
    assert "Error: Unsupported file type" in str(exc_info.value)


def test_process_extracted_path(mocker):
    mocker.patch(
        'plugin.codemig.codemig_task_manager.codemig_task.CodemigProcessor.process_file',
        return_value={})
    file_type_and_changes = defaultdict(list)
    file_type_and_changes[MigrationClass.TEXT] = [1]
    file_type_and_changes[MigrationClass.DYNAMIC_LINK_LIBRARY] = [2]
    mocker.patch('plugin.codemig.codemig_task_manager.codemig_task.create_changes',
                 return_value=file_type_and_changes)

    extract_path = Path(MODULE_PATH) / 'test_files' / 'test_dir'
    my_files, text_file_changes, lib_file_changes, missing, dirs = process_extracted_path(1, 2, 3,
                                                                                          extract_path)

    assert len(my_files) == 2
    assert my_files[0][:3] == (1, 2, 3) and my_files[0][4] == 0
    assert my_files[1][:3] == (1, 2, 3) and my_files[1][4] == 1
    assert text_file_changes == [1]
    assert lib_file_changes == [2]


def test_create_changes_text_only():
    """测试 create_changes 只包含 TEXT 类型的变更"""
    file_solvers_result = {
        MakefileSolver(): ([[1, 2, "suggestion1", CodeTooLong.HAS_SOURCE_CODE, "code1"],
                           [3, 4, "suggestion2", CodeTooLong.CODE_TOO_LONG, "code2"]], None)
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    assert MigrationClass.TEXT in result
    assert MigrationClass.DYNAMIC_LINK_LIBRARY not in result
    assert len(result[MigrationClass.TEXT]) == 2
    assert result[MigrationClass.TEXT][0] == (
        "/test/file.txt", 1, 2, 3, 0, 2, 1, 2, "suggestion1", CodeTooLong.HAS_SOURCE_CODE, "code1"
    )
    assert result[MigrationClass.TEXT][1] == (
        "/test/file.txt", 1, 2, 3, 0, 2, 3, 4, "suggestion2", CodeTooLong.CODE_TOO_LONG, "code2"
    )


def test_create_changes_lib_only(mocker):
    """测试 create_changes 只包含 DYNAMIC_LINK_LIBRARY 类型的变更"""
    # 创建一个 mock solver，返回 DYNAMIC_LINK_LIBRARY 类型
    mock_solver = mocker.Mock()
    mock_solver.migration_class.return_value = MigrationClass.DYNAMIC_LINK_LIBRARY
    
    file_solvers_result = {
        mock_solver: ([["x86_64", "lib suggestion1"],
                      ["riscv64", "lib suggestion2"]], None)
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/lib.so")
    
    assert MigrationClass.DYNAMIC_LINK_LIBRARY in result
    assert MigrationClass.TEXT not in result
    assert len(result[MigrationClass.DYNAMIC_LINK_LIBRARY]) == 2
    assert result[MigrationClass.DYNAMIC_LINK_LIBRARY][0] == (
        "/test/lib.so", 1, 2, 3, "x86_64", "lib suggestion1"
    )
    assert result[MigrationClass.DYNAMIC_LINK_LIBRARY][1] == (
        "/test/lib.so", 1, 2, 3, "riscv64", "lib suggestion2"
    )


def test_create_changes_mixed_types(mocker):
    """测试 create_changes 同时包含 TEXT 和 DYNAMIC_LINK_LIBRARY 类型的变更"""
    # 创建一个 mock solver，返回 DYNAMIC_LINK_LIBRARY 类型
    mock_lib_solver = mocker.Mock()
    mock_lib_solver.migration_class.return_value = MigrationClass.DYNAMIC_LINK_LIBRARY
    
    file_solvers_result = {
        MakefileSolver(): ([[1, 2, "text suggestion", CodeTooLong.HAS_SOURCE_CODE, "code"]], None),
        mock_lib_solver: ([["x86_64", "lib suggestion"]], None)
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/mixed")
    
    assert MigrationClass.TEXT in result
    assert MigrationClass.DYNAMIC_LINK_LIBRARY in result
    assert len(result[MigrationClass.TEXT]) == 1
    assert len(result[MigrationClass.DYNAMIC_LINK_LIBRARY]) == 1
    assert result[MigrationClass.TEXT][0] == (
        "/test/mixed", 1, 2, 3, 0, 2, 1, 2, "text suggestion", CodeTooLong.HAS_SOURCE_CODE, "code"
    )
    assert result[MigrationClass.DYNAMIC_LINK_LIBRARY][0] == (
        "/test/mixed", 1, 2, 3, "x86_64", "lib suggestion"
    )


def test_create_changes_empty_result_list():
    """测试 create_changes 处理空的 result_list（应该跳过）"""
    file_solvers_result = {
        MakefileSolver(): ([], None)  # result_list 为空列表
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    # 空的 result_list 应该被跳过，不产生任何变更
    assert len(result) == 0


def test_create_changes_empty_change_list():
    """测试 create_changes 处理空的 change_list（应该跳过）"""
    # result_list 不为空，但 change_list 为空
    file_solvers_result = {
        MakefileSolver(): ([], None)  # change_list 为空，但 result_list 是 ([], None)
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    # 空的 change_list 应该被跳过（在解包后检查）
    assert len(result) == 0


def test_create_changes_none_result_list():
    """测试 create_changes 处理 None 的 result_list（应该跳过）"""
    file_solvers_result = {
        MakefileSolver(): None  # result_list 为 None
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    # None 的 result_list 应该被跳过
    assert len(result) == 0


def test_create_changes_empty_file_solvers_result():
    """测试 create_changes 处理空的 file_solvers_result"""
    file_solvers_result = {}
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    # 应该返回空的 defaultdict
    assert len(result) == 0
    assert isinstance(result, defaultdict)


def test_create_changes_multiple_solvers_same_type():
    """测试 create_changes 处理同一类型的多个 solver"""
    # 创建两个不同的 TEXT 类型 solver（通过 mock）
    solver1 = MakefileSolver()
    solver2 = MakefileSolver()
    file_solvers_result = {
        solver1: ([[1, 2, "suggestion1", CodeTooLong.HAS_SOURCE_CODE, "code1"]], None),
        solver2: ([[3, 4, "suggestion2", CodeTooLong.HAS_SOURCE_CODE, "code2"]], None)
    }
    result = create_changes(1, 2, 3, file_solvers_result, "/test/file.txt")
    
    # 两个 solver 的变更应该都被添加到 TEXT 类型中
    assert MigrationClass.TEXT in result
    assert len(result[MigrationClass.TEXT]) == 2


def test_create_insert_values():
    result = create_insert_values("abc", 1, 2, 3, MakefileSolver(),
                                  [[1, 2, "suggestion", CodeTooLong.HAS_SOURCE_CODE, "mycode"]])
    assert result == [
        ('abc', 1, 2, 3, 0, 2, 1, 2, "suggestion", CodeTooLong.HAS_SOURCE_CODE, "mycode")]


class NewMakefileSolver(MakefileSolver):

    @staticmethod
    @override
    def database_table():
        return MigrationClass.DYNAMIC_LINK_LIBRARY


def test_create_insert_values_lib():
    result = create_insert_values("abc", 1, 2, 3, NewMakefileSolver(), [["arch", "suggestion"]])
    assert result == [('abc', 1, 2, 3, "arch", "suggestion")]


class NewMakefileSolver2(MakefileSolver):

    @staticmethod
    @override
    def database_table():
        return MigrationClass.UNKNOWN


def test_create_insert_values_lib():
    with pytest.raises(KeyError) as exc_info:
        create_insert_values("abc", 1, 2, 3, NewMakefileSolver2(), [])

    # 验证异常消息是否正确
    assert str(exc_info.value) == "'NewMakefileSolver2'"


def test_create_prepared_text_changes():
    file_path_to_file_id = {}
    file_path_to_file_id[(1, 2, 3, "abc", MigrationClass.TEXT.value)] = 4
    prepared_text_file_changes = [
        ("abc", 1, 2, 3, 5, 6, 10, 20, "suggestion", CodeTooLong.HAS_SOURCE_CODE, "mycode")]

    result = create_prepared_text_changes(file_path_to_file_id, prepared_text_file_changes)

    # 当前返回格式: (file_id, solver_type, append_or_replace, start_lineno, end_lineno, suggestion, code_too_long.value, mycode)
    assert result == [(4, 5, 6, 10, 20, "suggestion", 0, 'mycode')]


def test_create_prepared_text_changes_error():
    file_path_to_file_id = {}
    prepared_text_file_changes = [
        ("abc", 1, 2, 3, 5, 6, 10, 20, "suggestion", CodeTooLong.HAS_SOURCE_CODE, "mycode")]

    with pytest.raises(sqlite3.Error) as exc_info:
        create_prepared_text_changes(file_path_to_file_id, prepared_text_file_changes)

    # 验证异常消息是否正确（codemig_task 中抛出 sqlite3.Error）
    key = (1, 2, 3, "abc", MigrationClass.TEXT.value)
    assert f"Error finding file Id with key: {key}" in str(exc_info.value)


def test_create_prepared_lib_changes():
    file_path_to_file_id = {}
    file_path_to_file_id[(1, 2, 3, "abc", MigrationClass.DYNAMIC_LINK_LIBRARY.value)] = 4
    prepared_text_file_changes = [("abc", 1, 2, 3, "arch", "suggestion")]

    result = create_prepared_lib_changes(file_path_to_file_id, prepared_text_file_changes)

    # create_prepared_lib_changes 返回格式: (file_id, support_architecture, suggestion)
    assert result == [(4, "arch", "suggestion")]


def test_create_prepared_lib_changes_error():
    file_path_to_file_id = {}
    prepared_text_file_changes = [("abc", 1, 2, 3, "arch", "suggestion")]

    with pytest.raises(sqlite3.Error) as exc_info:
        create_prepared_lib_changes(file_path_to_file_id, prepared_text_file_changes)

    key = (1, 2, 3, "abc", MigrationClass.DYNAMIC_LINK_LIBRARY.value)
    assert f"Error finding file Id with key: {key}" in str(exc_info.value)


def test_remove_file_and_move_edited_file(mocker):
    """测试删除文件并移动编辑后的文件"""
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.remove')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.move_file_to_new_path')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.create_tmp_parent',
                 return_value="/tmp/parent")
    mocker.patch('shutil.rmtree')
    from plugin.codemig.codemig_task_manager.request_processor import remove_file_and_move_edited_file
    remove_file_and_move_edited_file("/test/file.txt", "/tmp/file.txt")
    # 验证调用了相关函数
    import os
    os.remove.assert_called_once_with("/test/file.txt")


def test_write_temp_file(mocker):
    """测试写入临时文件"""
    mocker.patch('os.makedirs')
    mocker.patch('os.path.exists', return_value=False)
    mock_open_file = mocker.mock_open()
    mocker.patch('builtins.open', mock_open_file)
    from plugin.codemig.codemig_task_manager.request_processor import write_temp_file
    write_temp_file("/tmp/test.txt", "content")
    mock_open_file.assert_called_once_with("/tmp/test.txt", 'w', encoding='utf-8')
    mock_open_file().write.assert_called_once_with("content")


def test_write_temp_file_existing(mocker):
    """测试写入已存在的临时文件（应该先删除）"""
    mocker.patch('os.makedirs')
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.remove')
    mock_open_file = mocker.mock_open()
    mocker.patch('builtins.open', mock_open_file)
    from plugin.codemig.codemig_task_manager.request_processor import write_temp_file
    write_temp_file("/tmp/test.txt", "content")
    import os
    os.remove.assert_called_once_with("/tmp/test.txt")


def test_mark_as_deleted_success(mocker):
    """测试成功标记任务为已删除"""
    from plugin.codemig.codemig_task_manager.models import CodemigTasks, CodemigTaskDirectory
    from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage
    
    mock_session = mocker.Mock()
    mock_task = mocker.Mock()
    mock_task.task_id = 1
    mock_task.task_name = "test_task"
    mock_task.user_id = 100
    
    # Mock 第一次查询（更新任务状态）
    mock_query1 = mocker.Mock()
    mock_filter1 = mocker.Mock()
    mock_query1.filter.return_value = mock_filter1
    mock_filter1.update.return_value = 1  # 影响1行
    
    # Mock 查询目录（session.query(CodemigTaskDirectory.dir_id)）
    mock_dir_query = mocker.Mock()
    mock_dir_filter = mocker.Mock()
    mock_dir_query.filter.return_value = mock_dir_filter
    mock_dir_filter.all.return_value = [(123,), (456,)]
    
    # Mock 更新目录存储
    mock_dir_storage_query = mocker.Mock()
    mock_dir_storage_filter = mocker.Mock()
    mock_dir_storage_query.filter.return_value = mock_dir_storage_filter
    mock_dir_storage_filter.update.return_value = 2
    
    # Mock 查询任务（获取任务名称）
    mock_task_query = mocker.Mock()
    mock_task_filter = mocker.Mock()
    mock_task_query.filter.return_value = mock_task_filter
    mock_task_filter.first.return_value = mock_task
    
    call_count = {'count': 0}
    def query_side_effect(*args):
        call_count['count'] += 1
        # 检查第一个参数是否是模型类
        if len(args) > 0:
            model = args[0]
            # 使用字符串比较模型类名，避免 SQLAlchemy 的 __eq__ 问题
            model_name = getattr(model, '__name__', None) if hasattr(model, '__name__') else str(model)
            if model_name == 'CodemigTasks':
                if call_count['count'] == 1:
                    return mock_query1  # 第一次：更新任务状态
                elif call_count['count'] == 3:
                    return mock_task_query  # 第三次：查询任务名称
            elif model_name == 'CodemigTaskDirectory' or (hasattr(model, 'class_') and model.class_.__name__ == 'CodemigTaskDirectory'):
                return mock_dir_query  # 第二次：查询目录
            elif model_name == 'CodemigDirectoryStorage':
                return mock_dir_storage_query  # 第四次：更新目录存储
        return mock_query1
    
    mock_session.query.side_effect = query_side_effect
    
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.record_operation_log')
    
    mock_request = mocker.Mock()
    mock_request.user_id = 100
    mock_request.remote_addr = "127.0.0.1"
    
    from plugin.codemig.codemig_task_manager.request_processor import mark_as_deleted
    result = mark_as_deleted(1, mock_request)
    assert result['code'] == '0'
    assert result['msg'] == "ok"


def test_mark_as_deleted_not_found(mocker):
    """测试任务不存在的情况"""
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.update.return_value = 0  # 影响0行，表示任务不存在
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.record_operation_log')
    
    mock_request = mocker.Mock()
    mock_request.user_id = 100
    mock_request.remote_addr = "127.0.0.1"
    
    from plugin.codemig.codemig_task_manager.request_processor import mark_as_deleted
    result = mark_as_deleted(999, mock_request)
    assert result['code'] == '-1'
    assert result['msg'] == "task not found"


def test_delete_user(mocker):
    """测试删除用户"""
    mock_session = mocker.Mock()
    mock_query = mocker.Mock()
    mock_filter = mocker.Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.update.return_value = 1
    mock_session.query.return_value = mock_query
    
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.db_session_scope',
                 return_value=mocker.MagicMock(__enter__=mocker.Mock(return_value=mock_session),
                                               __exit__=mocker.Mock(return_value=None)))
    
    from plugin.codemig.codemig_task_manager.request_processor import delete_user
    delete_user(100)
    # 验证调用了更新操作
    assert mock_filter.update.call_count == 2  # 更新两个表


def test_create_file_or_directory_handler_file(mocker):
    """测试创建文件处理器"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.save_new_file_to_database',
                 return_value=(True, 123))
    mocker.patch('pathlib.Path.mkdir')
    mocker.patch('pathlib.Path.touch')
    mocker.patch('pathlib.Path.exists', return_value=False)
    mocker.patch('builtins.open', mocker.mock_open())
    
    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "./test.txt", False)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


def test_create_file_or_directory_handler_directory(mocker):
    """测试创建目录处理器"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.save_new_file_to_database',
                 return_value=(True, 123))
    mocker.patch('pathlib.Path.mkdir')
    
    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "./test_dir", True)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


def test_create_file_or_directory_handler_db_error(mocker):
    """测试数据库错误的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_codemig_data_path',
                 return_value="/data/codemig")
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.save_new_file_to_database',
                 return_value=(False, None))
    mocker.patch('pathlib.Path.mkdir')
    mocker.patch('pathlib.Path.touch')
    mocker.patch('pathlib.Path.exists', return_value=False)
    mocker.patch('builtins.open', mocker.mock_open())
    
    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "./test.txt", False)
    assert result['code'] == -1
    assert result['msg'] == "数据库操作失败"


def test_delete_file_or_directory_handler_success(mocker):
    """测试成功删除文件或目录"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/file.txt", 'changed', '', '')))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)
    mocker.patch('os.remove')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_file_removed_to_database',
                 return_value=True)
    
    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


def test_delete_file_or_directory_handler_directory(mocker):
    """测试删除目录"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/dir", 'changed', '', '')))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=True)
    mocker.patch('shutil.rmtree')
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_directory_removed_recursively_to_database',
                 return_value=True)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_directory_removed_recursively_to_database',
                 return_value=True)
    
    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


def test_delete_file_or_directory_handler_db_not_found(mocker):
    """测试数据库不存在的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return False
    mocker.patch.object(Path, 'exists', mock_path_exists)

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Database not found!"


def test_update_suggestion_ignored_handler_success(mocker, mock_db_connection):
    """测试成功更新建议的忽略状态"""
    mock_cursor = mock_db_connection
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)

    from plugin.codemig.codemig_task_manager.request_processor import update_suggestion_ignored_handler
    from plugin.codemig.codemig_common.common_sql import UPDATE_SUGGESTION_IGNORED_SQL

    result = update_suggestion_ignored_handler("test_user", 1, 123, 456, True)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK

    # 验证 SQL 调用
    mock_cursor.execute.assert_called_once_with(UPDATE_SUGGESTION_IGNORED_SQL, (True, 123, 456))
    mock_conn.commit.assert_called_once()


def test_update_suggestion_ignored_handler_db_not_found(mocker):
    """测试数据库不存在的情况"""
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return False
    mocker.patch.object(Path, 'exists', mock_path_exists)

    from plugin.codemig.codemig_task_manager.request_processor import update_suggestion_ignored_handler
    result = update_suggestion_ignored_handler("test_user", 1, 123, 456, True)
    assert result['code'] == -1
    assert result['msg'] == "Database update error!!!"


def test_update_suggestion_ignored_handler_db_error(mocker, mock_db_connection):
    """测试数据库操作失败的情况"""
    mock_cursor = mock_db_connection
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    # 模拟数据库错误
    mock_cursor.execute.side_effect = sqlite3.Error("Database error")
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)

    from plugin.codemig.codemig_task_manager.request_processor import update_suggestion_ignored_handler
    result = update_suggestion_ignored_handler("test_user", 1, 123, 456, True)
    assert result['code'] == -1
    assert result['msg'] == "Database update error!!!"
    # 验证异常时连接被正确释放（closing 上下文管理器保证 close 被调用）
    mock_conn.close.assert_called_once()


def test_update_suggestion_ignored_handler_ignored_false(mocker, mock_db_connection):
    """测试将 ignored 设置为 False"""
    mock_cursor = mock_db_connection
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)

    from plugin.codemig.codemig_task_manager.request_processor import update_suggestion_ignored_handler
    from plugin.codemig.codemig_common.common_sql import UPDATE_SUGGESTION_IGNORED_SQL

    result = update_suggestion_ignored_handler("test_user", 1, 123, 456, False)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK

    # 验证 SQL 调用，ignored 参数为 False
    mock_cursor.execute.assert_called_once_with(UPDATE_SUGGESTION_IGNORED_SQL, (False, 123, 456))
    mock_conn.commit.assert_called_once()


def test_file_rollback_handler_success(mocker):
    """测试成功回滚文件"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/test/file.txt'))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.revert_to_last_commit',
        return_value=(True, "Reverted successfully", "file content"))
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK
    assert result['content'] == "file content"


def test_file_rollback_handler_db_not_found(mocker):
    """测试数据库不存在的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return False
    mocker.patch.object(Path, 'exists', mock_path_exists)
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Database not found!"
    assert result['content'] == ""


def test_file_rollback_handler_query_error(mocker):
    """测试数据库查询错误的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(False, None))
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Database query error!!!"
    assert result['content'] == ""


def test_file_rollback_handler_file_not_found(mocker):
    """测试文件不存在的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/test/file.txt'))
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "File not found!!!"
    assert result['content'] == ""


def test_file_rollback_handler_revert_failed(mocker):
    """测试回滚失败的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/test/file.txt'))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.revert_to_last_commit',
        return_value=(False, "Revert failed", ""))
    # Mock文件读取（当回滚失败时，会读取当前文件内容）
    mock_open_file = mocker.mock_open(read_data="current file content")
    mocker.patch('builtins.open', mock_open_file)
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Revert failed"
    assert result['content'] == "current file content"


def test_file_rollback_handler_revert_empty_content(mocker):
    """测试回滚成功但内容为空的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/test/file.txt'))
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.revert_to_last_commit',
        return_value=(True, "Reverted successfully", ""))  # 内容为空
    # Mock文件读取（当内容为空时，会读取当前文件内容）
    mock_open_file = mocker.mock_open(read_data="current file content")
    mocker.patch('builtins.open', mock_open_file)
    
    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Reverted successfully"
    assert result['content'] == "current file content"


def test_file_rollback_handler_is_directory(mocker):
    """测试回滚目标是一个目录"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=True)
    mocker.patch(
        'plugin.codemig.codemig_task_manager.request_processor.query_file_path_from_database',
        return_value=(True, '/test/dir'))

    from plugin.codemig.codemig_task_manager.request_processor import file_rollback_handler
    result = file_rollback_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "This is a directory!!!"


def test_match_ignored_suggestion_basic():
    """测试 _match_ignored_suggestion 基本匹配"""
    from plugin.codemig.codemig_task_manager.request_processor import _match_ignored_suggestion
    my_changes = [(1, 0, 1, 10, 20, "suggestion1", 0, "code1", False)]
    ignored_suggestions = [(10, 20, "suggestion1", "code1")]
    _match_ignored_suggestion(my_changes, ignored_suggestions)
    assert my_changes[0][8] is True


def test_match_ignored_suggestion_no_match():
    """测试 _match_ignored_suggestion 没有匹配"""
    from plugin.codemig.codemig_task_manager.request_processor import _match_ignored_suggestion
    my_changes = [(1, 0, 1, 10, 20, "suggestion1", 0, "code1", False)]
    ignored_suggestions = [(10, 20, "suggestion2", "code2")]
    _match_ignored_suggestion(my_changes, ignored_suggestions)
    assert my_changes[0][8] is False


def test_match_ignored_suggestion_empty_changes():
    """测试 _match_ignored_suggestion 空变更"""
    from plugin.codemig.codemig_task_manager.request_processor import _match_ignored_suggestion
    my_changes = []
    ignored_suggestions = [(10, 20, "suggestion1", "code1")]
    _match_ignored_suggestion(my_changes, ignored_suggestions)
    assert my_changes == []


def test_match_ignored_suggestion_empty_ignored():
    """测试 _match_ignored_suggestion 空忽略列表"""
    from plugin.codemig.codemig_task_manager.request_processor import _match_ignored_suggestion
    my_changes = [(1, 0, 1, 10, 20, "suggestion1", 0, "code1", False)]
    _match_ignored_suggestion(my_changes, [])
    assert my_changes[0][8] is False


def test_match_ignored_suggestion_already_ignored():
    """测试 _match_ignored_suggestion 已忽略的不变"""
    from plugin.codemig.codemig_task_manager.request_processor import _match_ignored_suggestion
    my_changes = [(1, 0, 1, 10, 20, "suggestion1", 0, "code1", True)]
    ignored_suggestions = [(10, 20, "suggestion1", "code1")]
    _match_ignored_suggestion(my_changes, ignored_suggestions)
    # Already ignored, should not change (stays True)
    assert my_changes[0][8] is True


def test_delete_file_or_directory_handler_original_source(mocker):
    """测试删除原始来源的文件"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/file.txt", 'original', '', '')))

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == -2


def test_delete_file_or_directory_handler_missing_source(mocker):
    """测试删除missing来源的文件"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/file.txt", 'missing', '', '')))

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == -2


def test_delete_file_or_directory_handler_query_error(mocker):
    """测试数据库查询失败"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(False, None))

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == -1
    assert result['msg'] == "Database query error!!!"


def test_delete_file_or_directory_handler_file_not_exists(mocker):
    """测试文件不存在时的删除（走 else 分支）"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/file.txt", 'changed', '', '')))
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.update_directory_removed_recursively_to_database',
                 return_value=True)

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == 0


def test_delete_file_or_directory_handler_delete_error(mocker):
    """测试删除文件失败"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_database_path',
                 return_value=Path('/test/db/path.db'))
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.query_file_info_from_database',
                 return_value=(True, ("/test/file.txt", 'changed', '', '')))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)
    mocker.patch('os.remove', side_effect=PermissionError("no permission"))

    from plugin.codemig.codemig_task_manager.request_processor import delete_file_or_directory_handler
    result = delete_file_or_directory_handler("test_user", 1, 123)
    assert result['code'] == -1


def test_create_file_or_directory_handler_existing_path(mocker):
    """测试路径已存在的情况"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_repo_path',
                 return_value=Path('/data/codemig/user1/1/changed'))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)

    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "./test.txt", False)
    assert result['code'] == -1
    assert result['msg'] == 'This path already exists'


def test_create_file_or_directory_handler_leading_slash(mocker):
    """测试路径以 / 开头"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_repo_path',
                 return_value=Path('/data/codemig/user1/1/changed'))
    mocker.patch('pathlib.Path.mkdir')
    mocker.patch('pathlib.Path.touch')
    mocker.patch('pathlib.Path.exists', return_value=False)
    mocker.patch('builtins.open', mocker.mock_open())
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.save_new_file_to_database',
                 return_value=(True, 123))

    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "/test.txt", False)
    assert result['code'] == 0


def test_create_file_or_directory_handler_create_error(mocker):
    """测试创建文件失败"""
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.get_repo_path',
                 return_value=Path('/data/codemig/user1/1/changed'))
    mocker.patch('pathlib.Path.mkdir', side_effect=PermissionError("no permission"))

    from plugin.codemig.codemig_task_manager.request_processor import create_file_or_directory_handler
    result = create_file_or_directory_handler("test_user", 100, 1, "./test.txt", False)
    assert result['code'] == -1


def test_delete_user_db_error(mocker):
    """测试删除用户数据库错误"""
    from common.db.SQLOperation import DatabaseException
    mocker.patch('plugin.codemig.codemig_task_manager.request_processor.db_session_scope',
                 side_effect=DatabaseException("db error"))

    from plugin.codemig.codemig_task_manager.request_processor import delete_user
    delete_user(100)  # Should not raise


def test_update_file_suggestion_to_database_no_changes(mocker, mock_db_connection):
    """测试没有变更时的数据库更新"""
    mock_cursor = mock_db_connection
    mock_db_path = Path('/test/db/path.db')
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=mock_db_path)
    def mock_path_exists(self):
        return True
    mocker.patch.object(Path, 'exists', mock_path_exists)
    mock_conn = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)

    result = update_file_suggestion_to_database("test_user", 222, 444, [])
    assert result is True
