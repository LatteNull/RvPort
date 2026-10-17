"""
为 query_processor.py 中覆盖率较低的函数补充测试。
"""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.response.response_code import ResponseCode
from plugin.codemig.codemig_task_manager import query_processor as qp


# ------------------- query_user_task_files -------------------

def test_query_user_task_files_failed(mocker):
    mocker.patch.object(qp, 'query_user_task_files_from_database',
                        return_value=(False, "Error: Task not found!!"))
    result = qp.query_user_task_files('me', 1, 'uid')
    assert result == {"code": -1, "msg": "Error: Task not found!!"}


def test_query_user_task_files_success(mocker):
    mocker.patch.object(qp, 'query_user_task_files_from_database',
                        return_value=(True, ('tname', None, [], [], [], 0)))
    mocker.patch.object(qp, 'create_data',
                        return_value={'task_name': 'tname'})
    result = qp.query_user_task_files('me', 1, 'uid')
    assert result['code'] == 0
    assert result['msg'] == ResponseCode.OK


# ------------------- query_task_id_by_dir_id -------------------

def test_query_task_id_by_dir_id_success(mocker):
    """成功查询"""
    mock_task_dir = MagicMock()
    mock_task_dir.task_id = 100
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_task_dir
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, task_id = qp.query_task_id_by_dir_id(1)
    assert status is True
    assert task_id == 100


def test_query_task_id_by_dir_id_not_found(mocker):
    """未找到时 task_id 为 None"""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, task_id = qp.query_task_id_by_dir_id(1)
    assert status is True
    assert task_id is None


def test_query_task_id_by_dir_id_exception(mocker):
    """内部异常时返回 (False, None)"""
    mocker.patch.object(qp, 'db_session_scope',
                        side_effect=qp.DatabaseException("boom"))
    status, task_id = qp.query_task_id_by_dir_id(1)
    assert status is False
    assert task_id is None


# ------------------- query_task_name_from_database exception -------------------

def test_query_task_name_from_database_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                        side_effect=qp.DatabaseException("boom"))
    status, name = qp.query_task_name_from_database(1)
    assert status is False
    assert name is None


# ------------------- query_task_info_from_database exception -------------------

def test_query_task_info_from_database_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                        side_effect=qp.DatabaseException("boom"))
    status, info = qp.query_task_info_from_database(1)
    assert status is False
    assert info is None


# ------------------- query_user_task_files_from_database -------------------

def test_query_user_task_files_from_database_task_not_found(mocker):
    mocker.patch.object(qp, 'query_task_info_from_database', return_value=(False, None))
    status, msg = qp.query_user_task_files_from_database('me', 1, 'uid')
    assert status is False
    assert msg == "Error: Task not found!!"


def test_query_user_task_files_from_database_dir_query_failed(mocker):
    mocker.patch.object(qp, 'query_task_info_from_database',
                        return_value=(True, ('tname', None, 0)))
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(False, None))
    status, msg = qp.query_user_task_files_from_database('me', 1, 'uid')
    assert status is False
    assert msg == "Error: Task not found!!"


def test_query_user_task_files_from_database_db_not_exist(mocker):
    mocker.patch.object(qp, 'query_task_info_from_database',
                        return_value=(True, ('tname', None, 0)))
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, msg = qp.query_user_task_files_from_database('me', 1, 'uid')
    assert status is False
    assert 'not found' in msg


def test_query_user_task_files_from_database_success(mocker):
    mocker.patch.object(qp, 'query_task_info_from_database',
                        return_value=(True, ('tname', 'time1', 0)))
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.side_effect = [
        [(1, 5, 10)],   # summary
        [(1, 3)],        # task_file_summary
        [(11, '/a/b.py', 7)],  # file_rows
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, data = qp.query_user_task_files_from_database('me', 1, 'uid')
    assert status is True
    assert data[0] == 'tname'


def test_query_user_task_files_from_database_db_exception(mocker):
    mocker.patch.object(qp, 'query_task_info_from_database',
                        return_value=(True, ('tname', 'time1', 0)))
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, msg = qp.query_user_task_files_from_database('me', 1, 'uid')
    assert status is False
    assert msg == "Database Error!"


# ------------------- convert_summary -------------------

def test_convert_summary_success(mocker):
    summary = [(1, 5, 10)]
    task_file_summary = [(2, 3)]
    # 直接构造 mock 替代 SolverType/MigrationClass
    mock_solver_enum = MagicMock()
    mock_solver_enum.description = 'solver_desc'
    mock_mig_enum = MagicMock()
    mock_mig_enum.description = 'mig_desc'
    mocker.patch.object(qp, 'SolverType', lambda v: mock_solver_enum)
    mocker.patch.object(qp, 'MigrationClass', lambda v: mock_mig_enum)
    rows = qp.convert_summary(summary, task_file_summary)
    assert rows == [('solver_desc', 5, 10), ('mig_desc', 3, None)]


# ------------------- create_data -------------------

def test_create_data_filters_zero_changes(mocker):
    """num_changed_lines 为 0 的文件不加入 files"""
    data = ('tname', 'ctime', [], [], [(1, 1, 11, '/a.py', 0), (2, 1, 12, '/b.py', 5)], 0)
    mocker.patch.object(qp, 'convert_summary', return_value=[])
    out = qp.create_data('me', data)
    assert len(out['files']) == 1
    assert out['files'][0][3] == 12


# ------------------- query_changes_for_file -------------------

def test_query_changes_for_file_failed(mocker):
    mocker.patch.object(qp, 'query_change_from_database', return_value=(False, '', []))
    result = qp.query_changes_for_file('me', 1, 1, 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_changes_for_file_is_dir(mocker):
    mocker.patch.object(qp, 'query_change_from_database', return_value=(True, '/some/dir', []))
    mocker.patch('os.path.isdir', return_value=True)
    result = qp.query_changes_for_file('me', 1, 1, 1)
    assert result['code'] == 0
    assert result['file'] == ''
    assert result['changes'] == []


def test_query_changes_for_file_success(tmp_path, mocker):
    p = tmp_path / "f.py"
    p.write_text("hello")
    mocker.patch.object(qp, 'query_change_from_database', return_value=(True, str(p), []))
    mocker.patch('os.path.isdir', return_value=False)
    mocker.patch.object(qp, 'query_original_file_from_git', return_value=(True, 'orig'))
    result = qp.query_changes_for_file('me', 1, 1, 1)
    assert result['code'] == 0
    assert result['file'] == 'hello'
    assert result['original_file'] == 'orig'


def test_query_changes_for_file_git_failed(tmp_path, mocker):
    p = tmp_path / "f.py"
    p.write_text("hello")
    mocker.patch.object(qp, 'query_change_from_database', return_value=(True, str(p), []))
    mocker.patch('os.path.isdir', return_value=False)
    mocker.patch.object(qp, 'query_original_file_from_git', return_value=(False, ''))
    result = qp.query_changes_for_file('me', 1, 1, 1)
    assert result['code'] == 0
    assert result['original_file'] == ''


# ------------------- query_generate_for_file -------------------

def test_query_generate_for_file_failed(mocker):
    mocker.patch.object(qp, 'query_missing_file_from_database',
                        return_value=(False, [], []))
    result = qp.query_generate_for_file('me', 1, 1, 1, 'm', [], 'uuid', 'fmt')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_generate_for_file_success(mocker):
    mocker.patch.object(qp, 'query_missing_file_from_database',
                        return_value=(True, '/some/path', []))
    mocker.patch.object(qp, 'create_ai_agent_file',
                        return_value={'code': 0})
    result = qp.query_generate_for_file('me', 1, 1, 1, 'm', [], 'uuid', 'fmt')
    assert result == {'code': 0}


# ------------------- query_dependence_generate_for_file -------------------

def test_query_dependence_generate_for_file_returns_default():
    """该函数返回固定结构"""
    result = qp.query_dependence_generate_for_file('me', 1, 1, 1, 5, 'uid')
    assert result == {"code": 0, "msg": ResponseCode.OK, "file": "123"}


# ------------------- query_missing_file_from_database exception -------------------

def test_query_missing_file_from_database_exception(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, file_path, arch_data = qp.query_missing_file_from_database('me', 1, 1, 1)
    assert status is False
    assert file_path == []
    assert arch_data == []


def test_query_missing_file_from_database_not_found(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, file_path, arch_data = qp.query_missing_file_from_database('me', 1, 1, 1)
    assert status is False


def test_query_missing_file_from_database_value_error(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, file_path, arch_data = qp.query_missing_file_from_database('me', 1, 1, 1)
    assert status is False


def test_query_missing_file_from_database_success(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ('/some/file', )
    mock_cursor.fetchall.return_value = [('/arch/path', 0)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, file_path, arch_data = qp.query_missing_file_from_database('me', 1, 1, 1)
    assert status is True
    assert file_path == '/some/file'
    assert arch_data == [('/arch/path', 0)]


# ------------------- query_change_from_database -------------------

def test_query_change_from_database_success_original(mocker):
    """file_source == ORIGINAL 时无 suggestion"""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ('/some/file', 'original', 0, None)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, file_path, suggestions = qp.query_change_from_database('me', 1, 1, 1)
    assert status is True
    assert file_path == '/some/file'
    assert suggestions == []


def test_query_change_from_database_success_changed(mocker):
    """file_source != ORIGINAL 时查询 suggestions"""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ('/some/file', 'changed', 0, None)
    mock_cursor.fetchall.return_value = [(1, 5, 0, 'fix me', 1, 2, 0)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, file_path, suggestions = qp.query_change_from_database('me', 1, 1, 1)
    assert status is True
    assert file_path == '/some/file'
    assert len(suggestions) == 1


def test_query_change_from_database_exception(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, file_path, suggestions = qp.query_change_from_database('me', 1, 1, 1)
    assert status is False
    assert file_path == ''
    assert suggestions == []


def test_query_change_from_database_db_not_exist(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, file_path, suggestions = qp.query_change_from_database('me', 1, 1, 1)
    assert status is False


# ------------------- query_dependence_changes_for_file -------------------

def test_query_dependence_changes_for_file_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_change_from_database',
                        return_value=(False, [], []))
    result = qp.query_dependence_changes_for_file('me', 1, 1, 1, 5)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_dependence_changes_for_file_no_file(tmp_path, mocker):
    """文件不存在时返回空 content"""
    mocker.patch.object(qp, 'query_dependence_change_from_database',
                        return_value=(True, '/no/such/file', []))
    mocker.patch('os.path.exists', return_value=False)
    result = qp.query_dependence_changes_for_file('me', 1, 1, 1, 5)
    assert result['code'] == 0
    assert result['file'] == ''


def test_query_dependence_changes_for_file_success(tmp_path, mocker):
    p = tmp_path / "d.py"
    p.write_text("dep content")
    mocker.patch.object(qp, 'query_dependence_change_from_database',
                        return_value=(True, str(p), []))
    mocker.patch('os.path.exists', return_value=True)
    result = qp.query_dependence_changes_for_file('me', 1, 1, 1, 5)
    assert result['code'] == 0
    assert result['file'] == 'dep content'


# ------------------- query_dependence_change_from_database -------------------

def test_query_dependence_change_from_database_value_error(mocker):
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, file_path, suggestions = qp.query_dependence_change_from_database(
        'me', 1, 1, 1, 5)
    assert status is False
    assert file_path == []


def test_query_dependence_change_from_database_db_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                        side_effect=qp.DatabaseException("boom"))
    status, file_path, suggestions = qp.query_dependence_change_from_database(
        'me', 1, 1, 1, 5)
    assert status is False
    assert file_path == []


def test_query_dependence_change_from_database_success(mocker):
    mock_file_dep = MagicMock()
    mock_file_dep.file_path = '/dep/file'
    mock_session = MagicMock()
    # file_dependence 查询
    mock_session.query.return_value.filter.return_value.first.return_value = mock_file_dep
    # suggestions 查询
    mock_suggestion = MagicMock()
    mock_suggestion.start_line_number = 1
    mock_suggestion.end_line_number = 5
    mock_suggestion.append_or_replace = 0
    mock_suggestion.suggestion = 'fix'
    mock_suggestion.change_id = 1
    mock_suggestion.type = 2
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_suggestion]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, file_path, suggestions = qp.query_dependence_change_from_database(
        'me', 1, 1, 1, 5)
    assert status is True
    assert file_path == '/dep/file'
    assert len(suggestions) == 1


# ------------------- query_original_file_processor -------------------

def test_query_original_file_processor_success(tmp_path, mocker):
    p = tmp_path / "f.py"
    p.write_text("content")
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.join', return_value=str(p))
    mocker.patch.object(qp, 'get_codemig_data_path', return_value='/data')
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = 'content'
        # 直接走文件读取路径
        result = qp.query_original_file_processor('me', 1, 1, 'f.py')
        assert result['code'] == 0


def test_query_original_file_processor_not_exist(mocker):
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch.object(qp, 'get_codemig_data_path', return_value='/data')
    result = qp.query_original_file_processor('me', 1, 1, 'f.py')
    assert result == {"code": -1, "msg": "File not found"}


# ------------------- query_file_tree_processor -------------------

def test_query_file_tree_processor_empty(mocker):
    mocker.patch.object(qp, 'build_file_tree', return_value=[])
    result = qp.query_file_tree_processor('me', 'uid', 1, 1)
    assert result == {"code": -1, "msg": "File tree not found"}


def test_query_file_tree_processor_success(mocker):
    mocker.patch.object(qp, 'build_file_tree', return_value=[('p1', ['a'])])
    result = qp.query_file_tree_processor('me', 'uid', 1, 1)
    assert result['code'] == 0
    assert result['file_tree'] == [('p1', ['a'])]


# ------------------- create_response_for_task -------------------

def test_create_response_for_task(mocker):
    """根据 (dir_id, file_id, file_path) 构造响应"""
    mocker.patch.object(qp, 'find_parent_and_file_name',
                        return_value=('/parent', 'fname'))
    result = qp.create_response_for_task(1, [(10, 11, '/parent/fname')])
    assert len(result) == 1
    parent, items = result[0]
    assert parent == '/parent'
    assert items[0] == (1, 10, 11, 'fname', 'changed')


# ------------------- query_dependence_file_tree_processor -------------------

def test_query_dependence_file_tree_processor_empty(mocker):
    mocker.patch.object(qp, 'build_dependence_file_tree', return_value=[])
    result = qp.query_dependence_file_tree_processor('me', 1, 5, 'uid')
    assert result == {"code": -1, "msg": "File tree not found"}


def test_query_dependence_file_tree_processor_success(mocker):
    mocker.patch.object(qp, 'build_dependence_file_tree',
                        return_value=[('/parent', [('info')])])
    result = qp.query_dependence_file_tree_processor('me', 1, 5, 'uid')
    assert result['code'] == 0
    assert result['file_tree'] == [('/parent', [('info')])]


# ------------------- query_dependence_file_tree_from_database -------------------

def test_query_dependence_file_tree_from_database_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, rows = qp.query_dependence_file_tree_from_database('me', 1, 5, 'uid')
    assert status is False
    assert rows == []


def test_query_dependence_file_tree_from_database_success(mocker):
    mock_result = MagicMock()
    mock_result.dir_id = 1
    mock_result.file_id = 11
    mock_result.file_path = '/dep/file'
    mock_session = MagicMock()
    mock_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_result]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, rows = qp.query_dependence_file_tree_from_database('me', 1, 5, 'uid')
    assert status is True
    assert rows == [(1, 11, '/dep/file')]


# ------------------- query_software -------------------

def test_query_software_dir_failed(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(False, None))
    result = qp.query_software('me', 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_software_sql_failed(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mocker.patch.object(qp, 'query_software_sql', return_value=(False, []))
    result = qp.query_software('me', 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_software_success(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mocker.patch.object(qp, 'query_software_sql', return_value=(True, []))
    mocker.patch.object(qp, 'create_software', return_value={'sw': []})
    result = qp.query_software('me', 1)
    assert result['code'] == 0


# ------------------- query_software_sql -------------------

def test_query_software_sql_db_not_exist(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, rows = qp.query_software_sql('me', 1)
    assert status is False
    assert rows == []


def test_query_software_sql_exception(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, rows = qp.query_software_sql('me', 1)
    assert status is False
    assert rows == []


def test_query_software_sql_success(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1, '/p', 'x86', 'suggest')]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, rows = qp.query_software_sql('me', 1)
    assert status is True
    assert rows == [(1, '/p', 'x86', 'suggest')]


# ------------------- create_software -------------------

def test_create_software():
    rows = [(1, '/path/a.so', 'x86', 'fix me')]
    out = qp.create_software(rows, task_id=10, dir_id=20)
    assert 'software' in out
    assert len(out['software']) == 1


# ------------------- query_missing_files -------------------

def test_query_missing_files_dir_failed(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(False, None))
    result = qp.query_missing_files('me', 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_missing_files_sql_failed(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(False, []))
    result = qp.query_missing_files('me', 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_missing_files_success(mocker):
    mocker.patch.object(qp, 'query_dir_id_by_task_id', return_value=(True, 2))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(True, []))
    mocker.patch.object(qp, 'create_missing_files', return_value={'mf': []})
    result = qp.query_missing_files('me', 1)
    assert result['code'] == 0


# ------------------- query_missing_files_sql -------------------

def test_query_missing_files_sql_db_not_exist(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, rows = qp.query_missing_files_sql('me', 1)
    assert status is False


def test_query_missing_files_sql_success(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1, '/a', 0)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, rows = qp.query_missing_files_sql('me', 1)
    assert status is True
    assert rows == [(1, '/a', 0)]


def test_query_missing_files_sql_exception(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, rows = qp.query_missing_files_sql('me', 1)
    assert status is False


# ------------------- create_missing_files -------------------

def test_create_missing_files():
    rows = [(1, '/a', 0)]
    out = qp.create_missing_files(rows, 10, 20)
    assert 'missing_files_rows' in out


# ------------------- generate_file_tree -------------------

def test_generate_file_tree(tmp_path):
    """构造目录后生成树结构"""
    (tmp_path / "f1.py").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f2.py").write_text("")
    tree = qp.generate_file_tree(str(tmp_path), relative=False)
    assert tree['type'] == 'dir'
    assert 'children' in tree


def test_generate_file_tree_os_error(mocker):
    """遍历抛 OSError 时跳过"""
    mock_path = MagicMock()
    mock_iter = MagicMock()
    mock_iter.iterdir.side_effect = OSError("permission denied")
    with patch('pathlib.Path.iterdir', side_effect=OSError("permission denied")):
        tree = qp.generate_file_tree('/whatever', relative=False)
        assert tree['children'] == []


# ------------------- create_existing_arch_data -------------------

def test_create_existing_arch_data_dir_type(mocker):
    """type=1 时使用 generate_file_tree"""
    mocker.patch.object(qp, 'generate_file_tree', return_value={'name': 'tree'})
    data = qp.create_existing_arch_data([('/path', 1)], file_id=11, task_id=22, dir_id=33)
    assert len(data) == 1
    assert data[0][3] == {'name': 'tree'}


def test_create_existing_arch_data_file_type(mocker):
    """type=0 时使用相对路径"""
    mocker.patch.object(qp, 'create_relative_file_path', return_value='/rel')
    data = qp.create_existing_arch_data([('/path', 0)], file_id=11, task_id=22, dir_id=33)
    assert data == [(22, 33, 11, '/rel', 0)]


# ------------------- query_existing_arch -------------------

def test_query_existing_arch_failed(mocker):
    mocker.patch.object(qp, 'query_existing_arch_data', return_value=(False, []))
    result = qp.query_existing_arch('me', 1, 1, 1)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_existing_arch_success(mocker):
    mocker.patch.object(qp, 'query_existing_arch_data',
                        return_value=(True, [('/arch', 0)]))
    mocker.patch.object(qp, 'create_existing_arch_data', return_value=[])
    result = qp.query_existing_arch('me', 1, 1, 1)
    assert result['code'] == 0


# ------------------- query_existing_arch_data -------------------

def test_query_existing_arch_data_db_not_exist(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    status, data = qp.query_existing_arch_data('me', 1, 1)
    assert isinstance(data, dict)  # 返回 dict 表示 db 不存在
    assert 'msg' in data


def test_query_existing_arch_data_exception(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    import sqlcipher3
    mocker.patch.object(qp, 'get_conn', side_effect=sqlcipher3.dbapi2.DatabaseError("err"))
    status, data = qp.query_existing_arch_data('me', 1, 1)
    assert status is False
    assert data == []


def test_query_existing_arch_data_success(mocker):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mocker.patch.object(qp, 'get_database_path', return_value=mock_path)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [('/arch', 0)]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch.object(qp, 'get_conn', return_value=mock_conn)
    status, data = qp.query_existing_arch_data('me', 1, 1)
    assert status is True
    assert data == [('/arch', 0)]


# ------------------- query_dependence_software -------------------

def test_query_dependence_software_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_software_sql',
                        return_value=(False, []))
    result = qp.query_dependence_software('me', 1, 5, 'uid')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_dependence_software_success(mocker):
    mocker.patch.object(qp, 'query_dependence_software_sql',
                        return_value=(True, []))
    mocker.patch.object(qp, 'create_dependence_software', return_value={'dep_sw': []})
    result = qp.query_dependence_software('me', 1, 5, 'uid')
    assert result['code'] == 0


# ------------------- query_dependence_software_sql -------------------

def test_query_dependence_software_sql_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, rows = qp.query_dependence_software_sql('me', 1, 5, 'uid')
    assert status is False


def test_query_dependence_software_sql_success(mocker):
    mock_result = MagicMock()
    mock_result.task_id = 1
    mock_result.dir_id = 2
    mock_result.file_id = 3
    mock_result.file_path = '/p'
    mock_result.support_architecture = 'x86'
    mock_result.suggestion = 'fix'
    mock_session = MagicMock()
    mock_session.query.return_value.join.return_value.join.return_value \
        .filter.return_value.order_by.return_value.all.return_value = [mock_result]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, rows = qp.query_dependence_software_sql('me', 1, 5, 'uid')
    assert status is True
    assert rows == [(1, 2, 3, '/p', 'x86', 'fix')]


# ------------------- create_dependence_software -------------------

def test_create_dependence_software():
    rows = [(1, 2, 3, '/path/lib.so', 'x86', 'suggest')]
    out = qp.create_dependence_software(rows)
    assert 'dependence_software_rows' in out


# ------------------- create_dependence_missing_files -------------------

def test_create_dependence_missing_files():
    rows = [(1, 2, 3, '/a')]
    out = qp.create_dependence_missing_files(rows)
    assert 'dependence_missing_files' in out
    assert len(out['dependence_missing_files']) == 1


# ------------------- query_dependence_missing_files -------------------

def test_query_dependence_missing_files_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_missing_files_sql',
                        return_value=(False, []))
    result = qp.query_dependence_missing_files('me', 1, 5, 'uid')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_dependence_missing_files_success(mocker):
    mocker.patch.object(qp, 'query_dependence_missing_files_sql',
                        return_value=(True, []))
    mocker.patch.object(qp, 'create_dependence_missing_files',
                        return_value={'dep_mf': []})
    result = qp.query_dependence_missing_files('me', 1, 5, 'uid')
    assert result['code'] == 0


# ------------------- query_dependence_missing_files_sql -------------------

def test_query_dependence_missing_files_sql_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, rows = qp.query_dependence_missing_files_sql('me', 1, 5, 'uid')
    assert status is False


def test_query_dependence_missing_files_sql_success(mocker):
    mock_result = MagicMock()
    mock_result.task_id = 1
    mock_result.dir_id = 2
    mock_result.file_id = 3
    mock_result.file_path = '/a'
    mock_session = MagicMock()
    mock_session.query.return_value.join.return_value.filter.return_value \
        .order_by.return_value.all.return_value = [mock_result]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, rows = qp.query_dependence_missing_files_sql('me', 1, 5, 'uid')
    assert status is True
    assert rows == [(1, 2, 3, '/a')]


# ------------------- query_dependence_existing_arch -------------------

def test_query_dependence_existing_arch_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_existing_arch_data',
                        return_value=(False, []))
    mocker.patch.object(qp, 'USE_ABSOLUTE_PATH', False)
    mocker.patch.object(qp, 'create_dependence_existing_arch_data', return_value=[])
    result = qp.query_dependence_existing_arch(1, 5)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_dependence_existing_arch_success(mocker):
    mocker.patch.object(qp, 'query_dependence_existing_arch_data',
                        return_value=(True, [(1, '/arch')]))
    mocker.patch.object(qp, 'USE_ABSOLUTE_PATH', False)
    mocker.patch.object(qp, 'create_dependence_existing_arch_data', return_value=[(1, '/rel')])
    result = qp.query_dependence_existing_arch(1, 5)
    assert result['code'] == 0


def test_query_dependence_existing_arch_absolute(mocker):
    mocker.patch.object(qp, 'USE_ABSOLUTE_PATH', True)
    mocker.patch.object(qp, 'query_dependence_existing_arch_data',
                        return_value=(True, [(1, '/arch')]))
    result = qp.query_dependence_existing_arch(1, 5)
    assert result['code'] == 0


# ------------------- query_dependence_existing_arch_data -------------------

def test_query_dependence_existing_arch_data_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, data = qp.query_dependence_existing_arch_data(1, 5)
    assert status is False
    assert data == []


def test_query_dependence_existing_arch_data_success(mocker):
    mock_result = MagicMock()
    mock_result.file_id = 1
    mock_result.architecture_path = '/arch'
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_result]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, data = qp.query_dependence_existing_arch_data(1, 5)
    assert status is True
    assert data == [(1, '/arch')]


# ------------------- create_dependence_existing_arch_data -------------------

def test_create_dependence_existing_arch_data(mocker):
    mocker.patch.object(qp, 'create_relative_file_path', return_value='/rel')
    out = qp.create_dependence_existing_arch_data([(1, '/abs')])
    assert out == [(1, '/rel')]


# ------------------- query_user_task_dependence_files -------------------

def test_query_user_task_dependence_files_failed(mocker):
    mocker.patch.object(qp, 'query_user_task_dependence_files_from_database',
                        return_value=(False, None))
    result = qp.query_user_task_dependence_files('me', 1, 5, 'uid')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_query_user_task_dependence_files_success(mocker):
    mocker.patch.object(qp, 'query_user_task_dependence_files_from_database',
                        return_value=(True, ('tname', 'ctime', [], [], [], 'dep', 'v1')))
    mocker.patch.object(qp, 'create_dependence_files_data', return_value={'d': 1})
    result = qp.query_user_task_dependence_files('me', 1, 5, 'uid')
    assert result['code'] == 0


# ------------------- query_user_task_dependence_files_from_database -------------------

def test_query_user_task_dependence_files_from_database_task_not_found(mocker):
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, data = qp.query_user_task_dependence_files_from_database('me', 1, 5, 'uid')
    assert status is True
    assert data is None


def test_query_user_task_dependence_files_from_database_dep_not_found(mocker):
    """任务存在但依赖包不存在 -> (True, None)"""
    mock_task = MagicMock()
    mock_task.task_name = 'tname'
    mock_task.created_at = None

    mock_session = MagicMock()
    # 第一次查 task，第二次查 dependence_package 都返回 None
    first_q = MagicMock()
    first_q.filter.return_value.first.return_value = mock_task
    second_q = MagicMock()
    second_q.filter.return_value.first.return_value = None
    mock_session.query.side_effect = [first_q, second_q]
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, data = qp.query_user_task_dependence_files_from_database('me', 1, 5, 'uid')
    assert status is True
    assert data is None


def test_query_user_task_dependence_files_from_database_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, data = qp.query_user_task_dependence_files_from_database('me', 1, 5, 'uid')
    assert status is False


# ------------------- query_dependence_file_path_from_database -------------------

def test_query_dependence_file_path_from_database_exception(mocker):
    mocker.patch.object(qp, 'db_session_scope',
                       side_effect=qp.DatabaseException("boom"))
    status, path = qp.query_dependence_file_path_from_database(1)
    assert status is False
    assert path is None


def test_query_dependence_file_path_from_database_success(mocker):
    mock_file_dep = MagicMock()
    mock_file_dep.file_path = '/dep/file'
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_file_dep
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, path = qp.query_dependence_file_path_from_database(1)
    assert status is True
    assert path == '/dep/file'


def test_query_dependence_file_path_from_database_not_found(mocker):
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mocker.patch.object(qp, 'db_session_scope',
                        return_value=MagicMock(__enter__=MagicMock(return_value=mock_session),
                                               __exit__=MagicMock(return_value=None)))
    status, path = qp.query_dependence_file_path_from_database(1)
    assert status is True
    assert path is None


# ------------------- create_dependence_files_data -------------------

def test_create_dependence_files_data(mocker):
    data = ('tname', 'ctime', [], [], [(1, 2, 3, '/a/b.py', 5)], 'dep', 'v1')
    mocker.patch.object(qp, 'convert_summary', return_value=[])
    out = qp.create_dependence_files_data(data)
    assert out['task_name'] == 'tname'
    assert out['dependence_name'] == 'dep'
    assert out['version'] == 'v1'
    assert len(out['files']) == 1


# ------------------- check_file_exists_handler -------------------

def test_check_file_exists_handler_dependence_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_file_path_from_database',
                        return_value=(False, None))
    result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=5)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_check_file_exists_handler_file_failed(mocker):
    mocker.patch.object(qp, 'query_file_path_from_database',
                        return_value=(False, None))
    result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=None)
    assert result == {"code": -1, "msg": "Database Error!"}


def test_check_file_exists_handler_not_exist(mocker):
    mocker.patch.object(qp, 'query_file_path_from_database',
                        return_value=(True, '/no/such'))
    mocker.patch('os.path.exists', return_value=False)
    result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=None)
    assert result['code'] == 0
    assert result['file_exists'] is False


def test_check_file_exists_handler_is_dir(mocker):
    mocker.patch.object(qp, 'query_file_path_from_database',
                        return_value=(True, '/some/dir'))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=True)
    result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=None)
    assert result['code'] == 0
    assert result['file_exists'] is True
    assert result['file_content'] == ''


def test_check_file_exists_handler_success(tmp_path, mocker):
    p = tmp_path / "f.py"
    p.write_text("hi")
    mocker.patch.object(qp, 'query_file_path_from_database',
                        return_value=(True, str(p)))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)
    result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=None)
    assert result['code'] == 0
    assert result['file_content'] == 'hi'


def test_check_file_exists_handler_read_error(mocker):
    mocker.patch.object(qp, 'query_file_path_from_database',
                        return_value=(True, '/some/file'))
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)
    with patch('builtins.open', side_effect=PermissionError("denied")):
        result = qp.check_file_exists_handler('me', 1, 1, 1, dependence_id=None)
        assert result['code'] == -1


# ------------------- save_file_content_handler -------------------

def test_save_file_content_handler_dependence_failed(mocker):
    mocker.patch.object(qp, 'query_dependence_file_path_from_database',
                        return_value=(False, None))
    result = qp.save_file_content_handler('me', 1, 1, 1, 5, 'x')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_save_file_content_handler_file_info_failed(mocker):
    mocker.patch.object(qp, 'commit_git_repo', return_value=(False, 'msg'))
    mocker.patch.object(qp, 'query_file_info_from_database',
                        return_value=(False, None))
    result = qp.save_file_content_handler('me', 1, 1, 1, None, 'x')
    assert result == {"code": -1, "msg": "Database Error!"}


def test_save_file_content_handler_is_dir(mocker):
    mocker.patch.object(qp, 'commit_git_repo', return_value=(True, None))
    mocker.patch.object(qp, 'query_file_info_from_database',
                        return_value=(True, ('/path', None, None, 0)))
    result = qp.save_file_content_handler('me', 1, 1, 1, None, 'x')
    assert result == {"code": -1, "msg": "This is a dir!"}


def test_save_file_content_handler_success(tmp_path, mocker):
    p = tmp_path / "f.py"
    p.write_text("old")
    mocker.patch.object(qp, 'commit_git_repo', return_value=(True, None))
    mocker.patch.object(qp, 'query_file_info_from_database',
                        return_value=(True, (str(p), None, None, 1)))
    result = qp.save_file_content_handler('me', 1, 1, 1, None, 'new content')
    assert result['code'] == 0
    assert result['saved'] is True


def test_save_file_content_handler_write_error(mocker):
    mocker.patch.object(qp, 'commit_git_repo', return_value=(True, None))
    mocker.patch.object(qp, 'query_file_info_from_database',
                        return_value=(True, ('/some/file', None, None, 1)))
    mocker.patch('os.makedirs')
    with patch('builtins.open', side_effect=PermissionError("denied")):
        result = qp.save_file_content_handler('me', 1, 1, 1, None, 'x')
        assert result['code'] == -1


def test_save_file_content_handler_dependence_success(tmp_path, mocker):
    """dependence_id 存在时跳过 git 操作"""
    p = tmp_path / "d.py"
    p.write_text("old")
    mocker.patch.object(qp, 'query_dependence_file_path_from_database',
                        return_value=(True, str(p)))
    result = qp.save_file_content_handler('me', 1, 1, 1, 5, 'new')
    assert result['code'] == 0


# ------------------- create_dir_path -------------------

def test_create_dir_path_absolute(mocker):
    mocker.patch.object(qp, 'USE_ABSOLUTE_PATH', True)
    mocker.patch.object(qp, 'get_codemig_data_path', return_value='/data')
    out = qp.create_dir_path('me', 1)
    assert out == os.path.join('/data', 'me', '1', 'changed')


def test_create_dir_path_relative(mocker):
    mocker.patch.object(qp, 'USE_ABSOLUTE_PATH', False)
    out = qp.create_dir_path('me', 1)
    assert out == os.path.join('.', 'me', '1', 'changed')


# ------------------- query_project_migrate_extra_files -------------------

_ABS = '/data/codemig/me/7/changed'


def test_extra_files_generated_query_failed(mocker):
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(False, None))
    assert qp.query_project_migrate_extra_files('me', 7)['code'] == -1


def test_extra_files_missing_query_failed(mocker):
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(True, []))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(False, []))
    assert qp.query_project_migrate_extra_files('me', 7)['code'] == -1


def test_extra_files_full_flow(mocker):
    """generated 目录行与 test//mca/ 前缀被排除；已有 generated 同路径的 missing 被隐藏"""
    gen_rows = [
        # 缺失文件的生成补齐（应隐藏对应 missing、出现在 generated）
        (11, f'{_ABS}/6v_mad/foo_riscv64.S', 1),
        # ② 功能验证产物（排除）
        (12, f'{_ABS}/test/foo/main.c', 1),
        # 历史残留的性能优化产物目录（同样排除）
        (13, f'{_ABS}/mca/foo/report.md', 1),
        # generated 父目录行（排除）
        (14, f'{_ABS}/6v_mad', 0),
    ]
    miss_rows = [
        # 已有 generated 同路径 → 不显示
        (5, f'{_ABS}/6v_mad/foo_riscv64.S', 0),
        # 无 generated → 显示
        (6, f'{_ABS}/vec/bar_riscv64.c', 0),
    ]
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(True, gen_rows))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(True, miss_rows))
    res = qp.query_project_migrate_extra_files('me', 7)
    assert res['code'] == 0
    assert [m['file_id'] for m in res['data']['missing']] == [6]
    assert [g['file_id'] for g in res['data']['generated']] == [11]


def test_extra_files_relative_path_storage(mocker):
    """USE_ABSOLUTE_PATH=False 的旧库相对路径存储（./me/7/changed/...）同样可过滤"""
    gen_rows = [(21, './me/7/changed/test/foo/main.c', 1),
                (22, './me/7/changed/src/new_rvv.c', 1)]
    miss_rows = [(8, './me/7/changed/src/old_riscv64.c', 0)]
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(True, gen_rows))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(True, miss_rows))
    res = qp.query_project_migrate_extra_files('me', 7)
    assert res['code'] == 0
    assert [g['file_id'] for g in res['data']['generated']] == [22]
    assert [m['file_id'] for m in res['data']['missing']] == [8]


def test_extra_files_filters_internal_artifacts(mocker):
    """.prompt.txt 与 .skills/*/SKILL.md（含历史脏数据路径变体）不进①清单"""
    gen_rows = [
        # 仓库根 .prompt.txt（容器内 /app/.prompt.txt 对应）
        (31, f'{_ABS}/.prompt.txt', 1),
        # .skills/<name>/SKILL.md（三阶段 skill 落盘）
        (32, f'{_ABS}/.skills/projectmigrate/SKILL.md', 1),
        (33, f'{_ABS}/.skills/uttest/SKILL.md', 1),
        # 正常迁移产物（应保留）
        (34, f'{_ABS}/6v_mad/new_file.S', 1),
        # .skills 父目录行（is_file=0，本就被目录过滤拦下）
        (35, f'{_ABS}/.skills', 0),
    ]
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(True, gen_rows))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(True, []))
    res = qp.query_project_migrate_extra_files('me', 7)
    assert res['code'] == 0
    assert [g['file_id'] for g in res['data']['generated']] == [34]


def test_extra_files_filters_build_artifacts(mocker):
    """编译中间产物（.o/.d 等）与验证工作区不进①清单，源文件保留"""
    gen_rows = [
        # 编译中间产物（扩展名精确匹配：.d 不误杀 .md）
        (41, f'{_ABS}/build/foo.o', 1),
        (42, f'{_ABS}/src/dep.d', 1),
        (43, f'{_ABS}/src/obj.gcno', 1),
        (44, f'{_ABS}/src/libfoo.so', 1),
        (45, f'{_ABS}/src/libbar.a', 1),
        # ① 阶段验证工作区残留
        (52, f'{_ABS}/.migrate_verify/foo/main.c', 1),
        # cmake / 扫描产物
        (46, f'{_ABS}/CMakeFiles/x.dir/y.c', 1),
        (47, f'{_ABS}/CMakeCache.txt', 1),
        (48, f'{_ABS}/scan_result.json', 1),
        # 构建输出目录（build-*/cmake-* 前缀：里面的 .log/Makefile 与文件树
        # is_build_temp_file 同判为构建产物，① 清单不显示）
        (53, f'{_ABS}/build-riscv64/bin/hs-rel-h2.log', 1),
        (54, f'{_ABS}/build-riscv64/Makefile', 1),
        (55, f'{_ABS}/cmake-check/toolchain.cmake', 1),
        # 源文件与文档（应保留）
        (49, f'{_ABS}/6v_mad/new_impl.S', 1),
        (50, f'{_ABS}/docs/report.md', 1),
        (51, f'{_ABS}/run.sh', 1),
    ]
    mocker.patch.object(qp, 'query_generated_files_from_database', return_value=(True, gen_rows))
    mocker.patch.object(qp, 'query_missing_files_sql', return_value=(True, []))
    res = qp.query_project_migrate_extra_files('me', 7)
    assert res['code'] == 0
    # .a/.so 归档与中间产物全部滤除，仅源文件与文档保留
    assert [g['file_id'] for g in res['data']['generated']] == [49, 50, 51]
