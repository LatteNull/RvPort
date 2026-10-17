# Standard library imports
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Third-party imports
import sqlcipher3
from sqlalchemy import func

# Local application imports
from common.db.SQLOperation import get_conn, db_session_scope, DatabaseException
from common.public import logger
from common.public.public import get_codemig_data_path
from common.response.response_code import ResponseCode

from plugin.codemig.ai_assistant.query_ai_handler import create_ai_agent_file
from plugin.codemig.codemig_common.common_git import (
    commit_git_repo,
    get_repo_path,
    query_original_file_from_git
)
from plugin.codemig.codemig_common.common_sql import SELECT_FILE_PATH_SQL, SELECT_FILE_INFO_SQL
from plugin.codemig.codemig_common.codemig_common_utils import (
    USE_ABSOLUTE_PATH,
    FileSource,
    add_dot_slash,
    create_relative_file_path,
    query_file_tree_from_database,
    query_file_by_path_from_database,
    query_file_path_from_database,
    query_file_info_from_database,
    get_database_path,
    query_all_file_from_database,
    save_new_file_to_database,
    query_missing_file_tree_from_database,
    save_generated_file_to_database,
    query_generated_files_from_database,
)
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_task_manager.models import CodemigTasks, CodemigTaskDirectory
from plugin.codemig.dependence_process.models import (
    CodemigTaskDependence,
    DependencePackages,
    FileDependence,
    FileDependenceSuggestion,
    SoftwareDependenceSuggestion,
    DependenceExistingArchitecture
)
from plugin.codemig.solver.solvers_mapping import SolverType

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

LOGGER = logger.init_log('codemig_task_manager_query_processor', 'codemig.log')

SELECT_FILE_SQL = ("""
                   SELECT File.file_id                AS file_id,
                          File.file_path              AS file_path,
                          COUNT(Suggestion.change_id) AS num_changed_lines
                   FROM codemig_task_directory_file AS File
                            LEFT JOIN codemig_task_directory_file_suggestion AS Suggestion
                                      ON File.file_id = Suggestion.file_id
                   WHERE File.has_removed = 0
                     AND File.type = 0
                     AND (File.file_source = 'changed' OR File.file_source = 'missing')
                     AND Suggestion.ignored = 0
                     AND Suggestion.is_manual = 0
                   GROUP BY File.dir_id, File.file_id
                   ORDER BY File.file_path ASC
                   """)

SELECT_SUMMARY_SQL = ("""
                      SELECT Suggestion.type                                                    AS suggestion_type,
                             COUNT(Suggestion.change_id)                                        AS num_changes,
                             SUM(Suggestion.end_line_number - Suggestion.start_line_number + 1) AS num_changed_lines
                      FROM codemig_task_directory_file AS File
                               JOIN codemig_task_directory_file_suggestion AS Suggestion
                                    ON File.file_id = Suggestion.file_id
                      WHERE File.has_removed = 0
                        AND File.type = 0
                        AND Suggestion.ignored = 0
                      GROUP BY Suggestion.type
                      ORDER BY Suggestion.type ASC
                      """)

SELECT_TASK_FILE_SUMMARY_SQL = ("""
                                SELECT type           AS file_type,
                                       COUNT(file_id) AS number_files
                                FROM codemig_task_directory_file
                                WHERE type > 0
                                GROUP BY type
                                ORDER BY type ASC
                                """)

SELECT_SUGGESTION_SQL = ("""
                         SELECT start_line_number,
                                end_line_number,
                                append_or_replace,
                                suggestion,
                                change_id,
                                type,
                                ignored,
                                is_manual
                         FROM codemig_task_directory_file_suggestion
                         WHERE file_id = ?
                           AND ignored = 0
                           AND is_manual = 0
                         ORDER BY start_line_number,
                                  append_or_replace,
                                  suggestion ASC
                         """)

SELECT_SOFTWARE_SQL = ("""
                       SELECT File.file_id                            AS file_id,
                              File.file_path                          AS file_path,
                              SoftwareSuggestion.support_architecture AS support_architecture,
                              SoftwareSuggestion.suggestion           AS suggestion
                       FROM codemig_task_directory_file AS File
                                JOIN codemig_task_directory_software_suggestion AS SoftwareSuggestion
                                     ON File.file_id = SoftwareSuggestion.file_id
                       WHERE File.type = 1
                         AND File.has_removed = 0
                       ORDER BY File.file_path ASC
                       """)

SELECT_MISSING_FILE_SQL = ("""
                           SELECT f.file_id, f.file_path, MAX(m.type) AS type
                           FROM codemig_task_directory_file AS f
                                    JOIN codemig_task_directory_existing_architecture as m
                                         ON f.file_id = m.file_id
                           WHERE f.type = 2
                           GROUP BY f.file_id, f.file_path
                           ORDER BY file_path ASC
                           """)

SELECT_EXIST_ARCH_BY_MISSING_FILE_ID_SQL = ("""
                                            SELECT architecture_path, type
                                            FROM codemig_task_directory_existing_architecture AS File
                                            WHERE file_id = ?
                                            ORDER BY architecture_path ASC
                                            """)


def query_user_tasks(user_id):
    status, result = query_task_from_database(user_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {"code": 0, "msg": ResponseCode.OK, "data": result}


def query_task_from_database(user_id):
    task_map = {}
    dependencies = []
    try:
        with db_session_scope() as session:
            # 使用 ORM 查询用户任务（status != 4, 即未删除的任务）
            task_objects = session.query(CodemigTasks).filter(
                CodemigTasks.user_id == user_id,
                CodemigTasks.status != 4
            ).order_by(CodemigTasks.task_id.asc()).all()

            # 转换为元组列表, 保持与原始格式一致
            tasks = [
                (task.task_id, task.task_name, task.is_scan_dependence)
                for task in task_objects
            ]

            # 过滤出需要扫描依赖的任务ID
            task_ids = [
                task_id for task_id, task_name, is_scan_dependence in tasks
                if is_scan_dependence == 1
            ]

            # 如果有需要扫描依赖的任务, 查询依赖信息
            if task_ids:
                # 使用 ORM 查询依赖信息
                dependence_results = session.query(
                    DependencePackages.dependence_id,
                    DependencePackages.dependence_package,
                    DependencePackages.version,
                    CodemigTaskDependence.task_id
                ).join(
                    CodemigTaskDependence,
                    CodemigTaskDependence.dependence_id == DependencePackages.dependence_id
                ).filter(
                    CodemigTaskDependence.task_id.in_(task_ids)
                ).order_by(
                    DependencePackages.dependence_package_path.asc()
                ).all()

                # 转换为元组列表, 保持与原始格式一致
                dependencies = [
                    (result.dependence_id, result.dependence_package,
                     result.version, result.task_id)
                    for result in dependence_results
                ]
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []

    for task_id, task_name, is_scan_dependence in tasks:
        task_map[task_id] = (task_name, is_scan_dependence, [])

    for dependence_id, dependence_package, version, task_id in dependencies:
        task_map[task_id][2].append(
            (dependence_id, dependence_package, version))

    result = [(task_id, task_name, is_scan, deps) for task_id, (task_name, is_scan, deps) in
              task_map.items()]

    return True, result


def query_user_task_files(user_name, task_id, user_id):
    status, data = query_user_task_files_from_database(
        user_name, task_id, user_id)
    if not status:
        return {"code": -1, "msg": data}
    return {"code": 0, "msg": ResponseCode.OK, "data": create_data(user_name, data)}


def query_dir_id_by_task_id(task_id):
    """
    获取任务的dir_id
    Args:
        task_id: 任务ID
    Returns:
        tuple: (status, dir_id)
            status: True 表示成功, False 表示失败
            dir_id: 目录ID
    """
    try:
        with db_session_scope() as session:
            task_dir = session.query(CodemigTaskDirectory).filter(
                CodemigTaskDirectory.task_id == task_id
            ).first()
            return True, task_dir.dir_id if task_dir else None
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"Query dir_id by task_id error: {str(err)}")
        return False, None


def query_task_id_by_dir_id(dir_id):
    """
    从 dir_id 获取 task_id
    Args:
        dir_id: 目录ID
    Returns:
        tuple: (status, task_id)
            status: True 表示成功, False 表示失败
            task_id: 任务ID
    """
    try:
        with db_session_scope() as session:
            task_dir = session.query(CodemigTaskDirectory).filter(
                CodemigTaskDirectory.dir_id == dir_id
            ).first()
            return True, task_dir.task_id if task_dir else None
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"Query task_id by dir_id error: {str(err)}")
        return False, None

def query_task_name_from_database(task_id):
    """
    获取任务的名称
    Args:
        task_id: 任务ID
    Returns:
        tuple: (status, task_name)
            status: True 表示成功, False 表示失败
            task_name: 任务名称
    """
    try:
        with db_session_scope() as session:
            task = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).first()
            if not task:
                LOGGER.warning(f"Task not found: task_id={task_id}")
                return False, None
            return True, task.task_name
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"query task name error of db error: {str(err)}")
        return False, None


def query_task_info_from_database(task_id):
    """
    获取任务的名称、创建时间、是否扫描依赖
    Args:
        task_id: 任务ID
    Returns:
        tuple: (status, task_name, created_time, is_scan_dependence)
            status: True 表示成功, False 表示失败
            task_name: 任务名称
            created_time: 创建时间
            is_scan_dependence: 是否扫描依赖
    """
    try:
        with db_session_scope() as session:
            task = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).first()
            if not task:
                LOGGER.warning(f"Task not found: task_id={task_id}")
                return False, None
            return True, (task.task_name, task.created_at, task.is_scan_dependence)
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"query task info error of db error: {str(err)}")
        return False, None


def query_user_task_files_from_database(user_name, task_id, user_id):
    LOGGER.info(f"Querying the files for user {user_name} task_id {task_id}.")
    status, task_info = query_task_info_from_database(task_id)
    if not status:
        return False, "Error: Task not found!!"
    task_name, created_time, is_scan_dependence = task_info

    status, dir_id = query_dir_id_by_task_id(task_id)
    if not status:
        return False, "Error: Task not found!!"
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, f"Error: Database {db_path} not found!"

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_SUMMARY_SQL)
        summary = cursor.fetchall()
        cursor.execute(SELECT_TASK_FILE_SUMMARY_SQL)
        task_file_summary = cursor.fetchall()
        cursor.execute(SELECT_FILE_SQL)
        file_rows = cursor.fetchall()
        # 将查询结果转换为 create_data 期望的格式
        # create_data 期望: (task_id, dir_id, file_id, file_path, num_changed_lines)
        select_file_info = []
        for row in file_rows:
            file_id, file_path, num_changed_lines = row
            select_file_info.append((task_id, dir_id, file_id, file_path, num_changed_lines or 0))
        return True, (task_name, created_time, summary, task_file_summary, select_file_info,
                      is_scan_dependence)
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, "Database Error!"
    finally:
        if conn:
            conn.close()


def create_dir_path(user_name, dir_id):
    str_dir_id = str(dir_id)
    if USE_ABSOLUTE_PATH:
        data_path = get_codemig_data_path()
        return os.path.join(data_path, user_name, str_dir_id, FileSource.CHANGED.value)
    return os.path.join(".", user_name, str_dir_id, FileSource.CHANGED.value)


def convert_summary(summary, task_file_summary):
    rows = []
    for solver_type, num_changes, num_lines in summary:
        suggestion_desc = SolverType(solver_type).description
        rows.append((suggestion_desc, num_changes, num_lines))
    for file_type, number_files in task_file_summary:
        file_type_desc = MigrationClass(file_type).description
        rows.append((file_type_desc, number_files, None))
    return rows


def create_data(user_name, data):
    (task_name, created_time, summary, task_file_summary, select_file_info,
     is_scan_dependence) = data
    dir_id_set = set()
    files = []
    for i, row in enumerate(select_file_info):
        task_id, dir_id, file_id, file_path, num_changed_lines = row
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)
        dir_id_set.add(dir_id)
        file_index = i + 1
        file_name = os.path.basename(file_path)
        if num_changed_lines == 0:
            continue
        files.append(
            (file_index, task_id, dir_id, file_id, file_name, file_path, num_changed_lines))
    directories = [create_dir_path(user_name, dir_id)
                   for dir_id in sorted(dir_id_set)]
    return {
        "task_name": task_name,
        "created_time": created_time,
        "directories": directories,
        "files": files,
        "summary": convert_summary(summary, task_file_summary),
        "is_scan_dependence": is_scan_dependence,
    }


def query_changes_for_file(user_name, task_id, dir_id, file_id):
    status, file_path, changes = query_change_from_database(user_name,
                                                            task_id, dir_id, file_id, )
    if not status:
        return {"code": -1, "msg": "Database Error!"}

    if os.path.isdir(file_path):
        return {
            "code": 0,
            "msg": ResponseCode.OK,
            "original_file": "",
            "file": "",
            "changes": []
        }

    # 获取文件初始版本的内容（新增文件在初始提交中不存在时，返回空字符串）
    status, original_file = query_original_file_from_git(user_name, dir_id, file_id)
    if not status:
        LOGGER.error(f"Failed to get original file from git")

    file_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            file_content = file.read()

    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "file_path": file_path or "",
        "original_file": original_file,
        "file": file_content,
        "changes": changes
    }


def query_generate_for_file(user_name, task_id, dir_id, file_id, model, 
                            reference_arch_paths, request_uuid, api_format):
    LOGGER.info(f"Querying the missing file for user {user_name} task_id \
        {task_id} dir_id {dir_id} file_id {file_id}.")
    status, file_path, _ = query_missing_file_from_database(user_name, task_id,
                                                            dir_id, file_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}

    return create_ai_agent_file(file_path, dir_id, reference_arch_paths, model, api_format,
                                user_name, file_id, request_uuid)


def query_dependence_generate_for_file(user_name, task_id, dir_id, file_id, dependence_id, user_id):
    LOGGER.info(f"Querying the missing file for user {user_name} task_id \
        {task_id} dir_id {dir_id} file_id {file_id} user_id {user_id} dependence_id {dependence_id}.")
    return {"code": 0, "msg": ResponseCode.OK, "file": "123"}


def query_missing_file_from_database(user_name, task_id, dir_id, file_id):
    LOGGER.info(f"Querying the missing file for user {user_name} task_id \
        {task_id} dir_id {dir_id} file_id {file_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, [], []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_PATH_SQL, (file_id,))
        fetched_file_path = cursor.fetchone()
        if fetched_file_path is None:
            LOGGER.error("Can't find the file path for given file id: %s", file_id)
            return False, [], []
        cursor.execute(SELECT_EXIST_ARCH_BY_MISSING_FILE_ID_SQL, (file_id,))
        existing_arch_data = cursor.fetchall()
        return True, fetched_file_path[0], existing_arch_data
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, [], []
    finally:
        if conn:
            conn.close()


def query_change_from_database(user_name, task_id, dir_id, file_id):
    """
    Returns:
    tuple: (status, file_path, suggestions)
        status: True 表示成功, False 表示失败
        file_path: 文件路径（成功时）或空列表（失败时）
        suggestions: 建议列表, 每个元素为 (start_line_number, end_line_number,
                     append_or_replace, suggestion, change_id, type, ignored, is_manual)
    """
    LOGGER.info(f"Querying the changes for user {user_name} task_id {str(task_id)} "
                f"dir_id {str(dir_id)} file_id {str(file_id)}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, '', []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_INFO_SQL, (file_id,))
        fetched_file_path, file_source, has_removed, _ = cursor.fetchone()
        if fetched_file_path is None:
            raise ValueError(f"Error: Can't find the file path for given file id: {file_id}.")
        if file_source == FileSource.ORIGINAL.value:
            return True, fetched_file_path, []
        cursor.execute(SELECT_SUGGESTION_SQL, (file_id,))
        return True, fetched_file_path, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, '', []
    finally:
        if conn:
            conn.close()


def query_dependence_changes_for_file(user_name, task_id, dir_id, file_id, dependence_id):
    status, file_path, dependence_changes = query_dependence_change_from_database(user_name,
                                                                                  task_id,
                                                                                  dir_id,
                                                                                  file_id,
                                                                                  dependence_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    else:
        if not os.path.exists(file_path):
            file_content = ""
        else:
            # 依赖文件都是新下载的, 属于原始文件, 没有修改文件
            # 所以 original_file 和 file 都是文件内容
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                file_content = file.read()
        return {
            "code": 0,
            "msg": ResponseCode.OK,
            "original_file": file_content,  # 依赖文件内容作为原始文件
            "file": file_content,  # 依赖文件没有修改版本, 为方便显示设置为原文件
            "changes": dependence_changes
        }


def query_dependence_change_from_database(user_name, task_id, dir_id, file_id, dependence_id):
    """
    查询依赖文件的变更建议

    Args:
        user_name: 用户名
        task_id: 任务ID
        dir_id: 目录ID
        file_id: 文件ID
        dependence_id: 依赖ID

    Returns:
        tuple: (status, file_path, suggestions)
            status: True 表示成功, False 表示失败
            file_path: 文件路径（成功时）或空列表（失败时）
            suggestions: 建议列表, 每个元素为 (start_line_number, end_line_number, append_or_replace, suggestion, change_id, type)
    """
    LOGGER.info(f"Querying the changes for user {user_name} task_id {str(task_id)} "
                f"dir_id {str(dir_id)} file_id {str(file_id)} dependence_id {str(dependence_id)}")
    try:
        with db_session_scope() as session:
            # 1. 查询文件路径
            file_dependence = session.query(FileDependence).filter(
                FileDependence.file_id == file_id
            ).first()

            if not file_dependence:
                raise ValueError(
                    f"Error: Can't find the file path for given file id: {file_id}.")

            file_path = file_dependence.file_path

            # 2. 查询建议
            suggestions = session.query(
                FileDependenceSuggestion.start_line_number,
                FileDependenceSuggestion.end_line_number,
                FileDependenceSuggestion.append_or_replace,
                FileDependenceSuggestion.suggestion,
                FileDependenceSuggestion.id.label('change_id'),
                FileDependenceSuggestion.type
            ).filter(
                FileDependenceSuggestion.dependence_id == dependence_id,
                FileDependenceSuggestion.file_id == file_id
            ).order_by(
                FileDependenceSuggestion.start_line_number.asc(),
                FileDependenceSuggestion.append_or_replace.asc(),
                FileDependenceSuggestion.suggestion.asc()
            ).all()

            # 转换为元组列表, 匹配原始 SQL 返回格式
            suggestions_list = [
                (s.start_line_number, s.end_line_number,
                 s.append_or_replace, s.suggestion, s.change_id, s.type)
                for s in suggestions
            ]

            return True, file_path, suggestions_list
    except ValueError as err:
        LOGGER.error("File not found: %s", err)
        return False, [], []
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, [], []


def query_original_file_processor(user_name, task_id, dir_id, file_path):
    path = os.path.join(get_codemig_data_path(), user_name,
                        str(dir_id), "original", file_path)
    if not os.path.exists(path):
        return {"code": -1, "msg": "File not found"}
    with open(path, 'r', encoding='utf-8', errors='replace') as file:
        file_content = file.read()
    return {"code": 0, "msg": ResponseCode.OK, "file_content": file_content}


def query_file_tree_processor(user_name, user_id, task_id, dir_id):
    # 使用 build_file_tree 构建文件树
    file_tree = build_file_tree(user_name, user_id, task_id, dir_id)
    if len(file_tree) == 0:
        return {"code": -1, "msg": "File tree not found"}
    return {"code": 0, "msg": ResponseCode.OK, "file_tree": file_tree}


# ─── ② 功能验证（ut_test）：测试产物清单 ────────────────────────────
# 背景：uttest skill 让 agent 在 <repo>/test/<目标文件名>/ 下生成
#   main.c / Makefile / run.sh / coverage.txt / expected.out / actual.out 等产物。
#   这些文件已由 insert_generated_files_to_database 落库（file_source='generated'），
#   但前端 ② 功能验证节点此前只渲染静态占位文案，从不展示它们。
#   本接口按 <repo>/test/ 目录扫描分组，供前端 ut_test 节点 items 渲染。

# 测试产物里值得在"测试文件"清单中展示的文件（按用途命名）；
# 其余 .o / .gcda / .gcno / 可执行文件等中间产物不展示。
# 驱动文件按 skill 版本可能叫 main.c 或 test_main.c，统一用 *.c/*.h 通配收进来。
# report.md / run.log / build.log：uttest 提示词 v4.2 起要求 benchmark 路径与
# 兜底路径都生成验证报告与运行/编译日志（见 uttest_prompt_template 产物落位总则），
# 前端文件树需展示，否则 benchmark 命中的工程在 ② 节点看不到任何产物。
UT_TEST_SOURCE_FILES = ('Makefile', 'run.sh', 'coverage.txt',
                        'expected.out', 'actual.out', 'diff_result.txt',
                        'report.md', 'report.txt', 'run.log', 'build.log')


def _is_ut_test_display_file(name):
    """test/<目标>/ 下是否值得展示：白名单产物 + .c/.h 源文件"""
    return name in UT_TEST_SOURCE_FILES or name.endswith(('.c', '.h'))


def query_ut_test_files_processor(user_name, dir_id):
    """
    扫描 <repo>/test/<目标>/ 目录，返回功能验证阶段生成的测试产物清单。

    Returns:
        {"code": 0, "data": {"targets": [{
            "target_name": "gf_3vect_mad_rv64_riscv64",   # test/ 下的子目录名
            "rel_path": "test/gf_3vect_mad_rv64_riscv64", # repo 内相对路径
            "files": [{"name", "path", "file_id", "size"}],# 可展示的源文件/报告
            "has_coverage": True,                          # 是否含 coverage.txt
            "diff_passed": True,                           # actual 与 expected 一致
        }]}}
        目录不存在时返回空 targets（code=0，前端显示"暂无"占位）。
        file_id 来自数据库（insert_generated_files_to_database 已入库），
        前端用它直接走 loadFileDiff 在 diff 编辑器打开；DB 尚未入库时为 null。
    """
    repo_path = get_repo_path(user_name, dir_id)
    test_root = Path(repo_path) / "test"
    if not test_root.is_dir():
        return {"code": 0, "msg": ResponseCode.OK,
                "data": {"targets": []}}

    targets = []
    for target_dir in sorted(p for p in test_root.iterdir() if p.is_dir()):
        # ★ 只展示功能验证的正式产物目录：uttest prompt 要求每个验证目标
        # 必生成 report.md 与 coverage.txt。缺两者的目录是阶段①代码生成的
        # 测试残留（旧版指令曾让①也写 /app/test/），不进前端文件树。
        if not ((target_dir / 'report.md').is_file()
                or (target_dir / 'coverage.txt').is_file()):
            continue
        rel_dir = (target_dir.relative_to(repo_path)).as_posix()
        files = []
        has_coverage = False
        diff_passed = None
        for f in sorted(target_dir.iterdir()):
            if not f.is_file() or not _is_ut_test_display_file(f.name):
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            # 反查 DB 拿 file_id（可能尚未入库，容忍 None）
            status, file_id = query_file_by_path_from_database(
                user_name, dir_id, f.as_posix())
            files.append({"name": f.name, "path": f.as_posix(),
                          "file_id": file_id if status else None,
                          "size": size})
            if f.name == 'coverage.txt':
                has_coverage = True

        # diff 结果判定：expected.out 与 actual.out 内容完全一致 → 通过
        try:
            expected = (target_dir / 'expected.out').read_text(
                encoding='utf-8', errors='replace')
            actual = (target_dir / 'actual.out').read_text(
                encoding='utf-8', errors='replace')
            diff_passed = expected == actual
        except OSError:
            diff_passed = None

        targets.append({
            "target_name": target_dir.name,
            "rel_path": rel_dir,
            "files": files,
            "has_coverage": has_coverage,
            "diff_passed": diff_passed,
        })
    return {"code": 0, "msg": ResponseCode.OK, "data": {"targets": targets}}


def is_build_temp_file(file_path, changed_path):
    """
    判断文件是否是构建临时文件或迁移生成的文件
    """
    # 检查路径中是否包含构建目录
    if '/build-' in file_path or '/cmake-' in file_path:
        return True
    if '/CMakeFiles/' in file_path or '/CMakeCache.txt' in file_path:
        return True
    if '/__pycache__/' in file_path or '/.pytest_cache/' in file_path:
        return True
    
    # 检查文件扩展名是否是构建临时文件
    if (file_path.endswith('.o') or file_path.endswith('.o.d') or 
        file_path.endswith('.make') or file_path.endswith('.marks')):
        return True
    
    # 检查是否在CMake目录中的.txt文件
    if '/CMakeFiles/' in file_path and file_path.endswith('.txt'):
        return True
    
    # 排除迁移过程中生成的文件
    # .skills目录（skill文档）
    if '/.skills/' in file_path or file_path.endswith('/.skills'):
        return True

    # 迁移 prompt 临时文件（写入 /app/.prompt.txt 供 agent 容器内读取）
    if file_path.endswith('/.prompt.txt') or file_path == '.prompt.txt':
        return True

    # 工具链配置文件
    if file_path.endswith('-toolchain.cmake'):
        return True
    
    # 迁移结果文件
    if file_path.endswith('/scan_result.json') or file_path.endswith('\\scan_result.json'):
        return True
    
    # 测试文件（test_开头）
    file_name = os.path.basename(file_path)
    if file_name.startswith('test_'):
        return True
    
    # simde目录（SIMD库）
    if '/simde/' in file_path or file_path.endswith('/simde'):
        return True
    
    return False


def build_file_tree(user_name, user_id, task_id, dir_id):
    """
    构建文件树结构
    文件树列表, 格式：[(parent_path, [(task_id, dir_id, file_id, file_name), ...]), ...]
    """
    # 用于存储文件信息：parent_path -> [(task_id, dir_id, file_id, file_name), ...]
    grouped_data = defaultdict(list)

    changed_list = []
    changed_path = get_repo_path(user_name, dir_id)
    if not os.path.exists(changed_path):
        LOGGER.warning(f"Path does not exist: {changed_path}")
    else:
        # 遍历changed目录下的目录
        for root, dirs, files in os.walk(changed_path):
            # 排除不需要跟踪的目录（构建目录、版本控制目录等）
            dirs_to_remove = []
            for dir_name in dirs:
                # 排除版本控制目录
                if dir_name in ['.git', '.github']:
                    dirs_to_remove.append(dir_name)
                # 排除构建目录（CMake、Make等生成的临时目录）
                elif dir_name.startswith('build-') or dir_name.startswith('cmake-'):
                    dirs_to_remove.append(dir_name)
                # 排除常见的构建输出目录
                elif dir_name in ['CMakeFiles', 'CMakeCache.txt', '__pycache__', '.pytest_cache']:
                    dirs_to_remove.append(dir_name)
                # 排除迁移过程写入的 skill 文档目录（与 is_build_temp_file 保持一致；
                # walk 层排除可同时阻止下方"新文件入库"分支把它写进 DB 并渲染进树）
                elif dir_name == '.skills':
                    dirs_to_remove.append(dir_name)

            # 从遍历列表中移除这些目录
            for dir_name in dirs_to_remove:
                dirs.remove(dir_name)

            # 只记录需要跟踪的目录和文件
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                changed_list.append(dir_path)
            for file_name in files:
                # 排除迁移 prompt 临时文件（agent 容器内 cat /app/.prompt.txt 用，
                # 属于工具内部产物，不应出现在文件树/数据库中）
                if file_name == '.prompt.txt':
                    continue
                # 排除构建生成的临时文件
                if not (file_name.endswith('.o') or file_name.endswith('.o.d') or
                        file_name.endswith('.make') or file_name.endswith('.txt') and
                        'CMake' in root):
                    file_path = os.path.join(root, file_name)
                    changed_list.append(file_path)

    status, trees = query_file_tree_from_database(user_name, dir_id)
    if not status:
        LOGGER.error(f"Query file tree from database failed")
        return []

    missing_set = set()
    missing_data = {}
    status, missing_trees = query_missing_file_tree_from_database(user_name, dir_id)
    if not status:
        LOGGER.error(f"Query missing file tree from database failed")
        return []
    for item in missing_trees:
        file_id, file_path, source, is_file = item
        missing_set.add(file_path)
        parent_path, file_name = find_parent_and_file_name_ex(file_path, changed_path)
        info = (task_id, dir_id, file_id, file_name, source, is_file,)
        grouped_data[parent_path].append(info)
        missing_data[file_path] = info

    tmp_changed_set = set(changed_list)
    for item in trees:
        file_id, file_path, source, is_file, source_file_id = item
        # 排除构建目录中的文件（不产生WARNING）
        if is_build_temp_file(file_path, changed_path):
            continue
        if file_path not in tmp_changed_set:
            LOGGER.warning(f"File not found in changed list: {file_path}")
            continue
        else:
            tmp_changed_set.remove(file_path)
        parent_path, file_name = find_parent_and_file_name_ex(file_path, changed_path)
        missing_file_id = None
        if file_path in missing_set:
            missing_file_id = source_file_id
            if missing_data[file_path] in grouped_data[parent_path]:
                grouped_data[parent_path].remove(missing_data[file_path])
        grouped_data[parent_path].append((
            task_id,
            dir_id,
            file_id,
            file_name,
            source,
            is_file,
            missing_file_id, #与缺失文件路径相同，才提供
        ))

    # TODO: git 添加后 与 init 比较,  新增的文件插入数据库
    if len(tmp_changed_set) < 1:
        return sorted(grouped_data.items(), key=lambda x: x[0])

    all_file_dict = {}
    status, all_files = query_all_file_from_database(user_name, dir_id)
    if not status:
        LOGGER.error(f"Query all file from database failed")
        return sorted(grouped_data.items(), key=lambda x: x[0])

    for file_path, source, is_file, file_id in all_files:
        all_file_dict[file_path] = (is_file, source, file_id)
    for file_path_new in tmp_changed_set:
        # 兜底过滤：迁移内部产物（.skills / .prompt.txt 等）不入库、不进树。
        # 正常情况已在上方 walk 层排除（dirs_to_remove / .prompt.txt continue），
        # 这里防的是 DB 已有历史脏数据、tmp_changed_set 仍含这些路径的边缘场景。
        if is_build_temp_file(file_path_new, changed_path):
            continue
        # 目录 -- 常规文件  其他文件
        is_file_tmp = not os.path.isdir(file_path_new)
        is_file_new = 1 if is_file_tmp else 0
        if file_path_new not in all_file_dict:
            status, file_id_new = save_new_file_to_database(user_name, user_id,
                                                            dir_id, file_path_new,
                                                            FileSource.GENERATE.value,
                                                            is_file_new)
            if not status:
                LOGGER.error(f"Save new file to database failed: {file_path_new}")
                continue
            parent_path, file_name = find_parent_and_file_name_ex(file_path_new, changed_path)
            grouped_data[parent_path].append((
                task_id,
                dir_id,
                file_id_new,
                file_name,
                FileSource.GENERATE.value,
                is_file_new,
            ))
        else:
            if all_file_dict[file_path_new][0] == is_file_new and \
                all_file_dict[file_path_new][1] == FileSource.MISSING.value:
                status, file_id_new = save_generated_file_to_database(user_name, user_id,
                                                            dir_id, file_path_new,
                                                            FileSource.GENERATE.value,
                                                            is_file_new,
                                                            all_file_dict[file_path_new][2])
                if not status:
                    LOGGER.error(f"Save generated file to database failed: {file_path_new}")
                    continue
                parent_path, file_name = find_parent_and_file_name_ex(file_path_new, changed_path)
                grouped_data[parent_path].append((
                    task_id,
                    dir_id,
                    file_id_new,
                    file_name,
                    FileSource.GENERATE.value,
                    is_file_new,
                    all_file_dict[file_path_new][2],
                ))

            elif all_file_dict[file_path_new][0] != is_file_new:
                status, file_id_new = save_new_file_to_database(user_name, user_id,
                                                                dir_id, file_path_new,
                                                                FileSource.CHANGED.value,
                                                                is_file_new)
                if not status:
                    LOGGER.error(f"Update file to database failed: {file_path_new}")
                    continue
                parent_path, file_name = find_parent_and_file_name_ex(file_path_new, changed_path)
                grouped_data[parent_path].append((
                    task_id,
                    dir_id,
                    file_id_new,
                    file_name,
                    FileSource.CHANGED.value,
                    is_file_new,
                ))

    # 转换为列表格式, 按父路径排序
    return sorted(grouped_data.items(), key=lambda x: x[0])


def find_parent_and_file_name_ex(file_path, base_path):
    if USE_ABSOLUTE_PATH:
        my_path = Path(file_path)
        return my_path.parent.as_posix(), my_path.name
    else:
        my_path = Path(os.path.relpath(file_path, base_path))
        return add_dot_slash(my_path.parent.as_posix()), my_path.name


def find_parent_and_file_name(file_path):
    if USE_ABSOLUTE_PATH:
        my_path = Path(file_path)
        return my_path.parent.as_posix(), my_path.name
    my_path = Path(os.path.relpath(file_path, get_codemig_data_path()))
    return add_dot_slash(my_path.parent.as_posix()), my_path.name


def create_response_for_task(task_id, result):
    grouped_data = defaultdict(list)
    for dir_id, file_id, file_path in result:
        parent, file_name = find_parent_and_file_name(file_path)
        # query_dependence_file_tree_processor 使用 file_source = 'changed'
        # TODO: dependence 相关修改
        grouped_data[parent].append(
            (task_id, dir_id, file_id, file_name, FileSource.CHANGED.value))
    return list(grouped_data.items())


def create_response_for_task_with_missing(task_id, result):
    grouped_data = defaultdict(list)
    for dir_id, file_id, file_path, is_missing in result:
        parent, file_name = find_parent_and_file_name(file_path)
        grouped_data[parent].append(
            (task_id, dir_id, file_id, file_name, is_missing))
    return list(grouped_data.items())


def query_dependence_file_tree_processor_old(user_name, task_id, dependence_id, user_id):
    status, result = query_dependence_file_tree_from_database(user_name, task_id, dependence_id,
                                                              user_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {"code": 0, "msg": ResponseCode.OK,
            "file_tree": create_response_for_task(task_id, result)}


def build_dependence_file_tree(user_name, task_id, dependence_id, user_id):
    grouped_data = defaultdict(list)
    dependence_package_path = DependencePackages.get_package_path(
        dependence_id)
    if not dependence_package_path:
        return list(grouped_data.items())
    relative_dependence_package_path = os.path.dirname(dependence_package_path)

    status, result = query_dependence_file_tree_from_database(user_name, task_id, dependence_id,
                                                              user_id)
    if not status:
        return list(grouped_data.items())

    for dir_id, file_id, file_path in result:
        parent, file_name = find_parent_and_file_name_ex(
            file_path, relative_dependence_package_path)
        grouped_data[parent].append(
            (task_id, dir_id, file_id, file_name, FileSource.CHANGED.value, True))

    status, missing_result = query_dependence_missing_files_sql(
        user_name, task_id, dependence_id, user_id)
    if not status:
        return list(grouped_data.items())

    for row in missing_result:
        task_id, dir_id, file_id, file_path = row
        parent, file_name = find_parent_and_file_name_ex(
            file_path, relative_dependence_package_path)
        grouped_data[parent].append(
            (task_id, dir_id, file_id, file_name, FileSource.MISSING.value, True))

    return list(grouped_data.items())


def query_dependence_file_tree_processor(user_name, task_id, dependence_id, user_id):
    file_tree = build_dependence_file_tree(
        user_name, task_id, dependence_id, user_id)
    if len(file_tree) == 0:
        return {"code": -1, "msg": "File tree not found"}
    return {"code": 0, "msg": ResponseCode.OK, "file_tree": file_tree}


def query_dependence_file_tree_from_database(user_name, task_id, dependence_id, user_id):
    """
    查询依赖文件树

    Args:
        user_name: 用户名
        task_id: 任务ID
        dependence_id: 依赖ID
        user_id: 用户ID

    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 文件树列表, 每个元素为 (dir_id, file_id, file_path)
    """
    LOGGER.info(f"Querying the file tree for user {user_name} task_id {task_id} "
                f"dependence_id {dependence_id}.")
    try:
        with db_session_scope() as session:
            results = session.query(
                CodemigTaskDependence.dir_id,
                FileDependence.file_id,
                FileDependence.file_path
            ).join(
                FileDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type == 0
            ).order_by(
                FileDependence.file_path.asc()
            ).all()

            file_tree_rows = [
                (result.dir_id, result.file_id, result.file_path)
                for result in results
            ]

            return True, file_tree_rows
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []


def query_software(user_name, task_id):
    status, dir_id = query_dir_id_by_task_id(task_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    status, software_rows = query_software_sql(user_name, dir_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "data": create_software(software_rows, task_id, dir_id)
    }


def query_software_sql(user_name, dir_id):
    LOGGER.info(f"Querying the software for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_SOFTWARE_SQL)
        software_rows = cursor.fetchall()
        return True, software_rows
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        if conn:
            conn.rollback()
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()


def create_software(software_rows, task_id, dir_id):
    software = []
    for i, row in enumerate(software_rows):
        file_id, file_path, support_architecture, suggestion = row
        file_index = i + 1
        file_name = os.path.basename(file_path)
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)
        software.append(
            (file_index, task_id, dir_id, file_id, file_name, file_path, support_architecture,
             suggestion))
    return {"software": software}


def query_missing_files(user_name, task_id):
    status, dir_id = query_dir_id_by_task_id(task_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    status, missing_files_rows = query_missing_files_sql(user_name, dir_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {"code": 0, "msg": ResponseCode.OK,
            "data": create_missing_files(missing_files_rows, task_id, dir_id)}


def query_missing_files_sql(user_name, dir_id):
    LOGGER.info(f"Querying the missing files for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_MISSING_FILE_SQL)
        missing_files_rows = cursor.fetchall()
        return True, missing_files_rows
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()


def create_missing_files(missing_files_rows, task_id, dir_id):
    missing_files = []
    for i, row in enumerate(missing_files_rows):
        file_id, file_path, miss_type = row
        file_index = i + 1
        file_name = os.path.basename(file_path)
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)
        missing_files.append(
            (file_index, task_id, dir_id, file_id, file_name, file_path, miss_type))
    return {"missing_files_rows": missing_files}


# ─── ① 代码生成节点：缺失文件 + 迁移新增文件清单 ────────────────────────────
# 背景：/task/files（SELECT_FILE_SQL 只查 changed 且按建议数过滤）展示不了
#   type=2 的缺失行与 file_source='generated' 的新增行，前端 ① 节点此前
#   看不到这两类文件。本接口一次返回两份清单，供 ① 节点红/绿配色渲染。
#   ② 阶段产物（test/ 前缀）由该节点的清单接口展示，此处排除。

# ② 功能验证阶段产物在 repo 内的顶层目录（① 节点不展示）；mca/ 为
# 已下线的性能优化阶段历史残留目录，同样不展示。
# .migrate_verify 是 ① 阶段自己的交叉编译验证工作区（提示词要求收尾清理，
# 残留属于临时产物，不展示）
_PROJECT_MIGRATE_EXCLUDED_TOP_DIRS = ('test', 'mca', '.migrate_verify')

# 编译中间产物扩展名（① 清单只展示源文件/文档，.o/.d 等不显示）。
# 注意必须用 os.path.splitext 精确匹配——直接 endswith('.d') 会误杀 .md。
# 与 is_build_temp_file 的扩展名规则对齐并补充 gcc -MMD 的 .d、覆盖率 .gcno/.gcda。
_GENERATED_EXCLUDED_EXTS = ('.o', '.d', '.make', '.marks',
                            '.gcno', '.gcda', '.gcov', '.so', '.a')

# 中间目录段（任意层级）与按基名排除的文件
_GENERATED_EXCLUDED_SEGMENTS = ('.skills', 'CMakeFiles', '__pycache__')
# 构建输出目录前缀（任意层级，与文件树 is_build_temp_file 的
# '/build-'/'/cmake-' 排除对齐：build-riscv64/ 等目录里的 .log/Makefile/
# cmake_install.cmake 同属构建产物，文件树不显示，① 清单也不显示）
_GENERATED_EXCLUDED_SEGMENT_PREFIXES = ('build-', 'cmake-')
_GENERATED_EXCLUDED_BASENAMES = ('.prompt.txt', 'SKILL.md',
                                 'CMakeCache.txt', 'scan_result.json')


def _repo_rel_segments(file_path):
    """
    取 DB 存储路径的 repo 相对路径段。

    兼容两种存储格式：绝对路径（.../data/codemig/<user>/<dir_id>/changed/xxx）
    与相对路径（./<user>/<dir_id>/changed/xxx）。'changed' 是 repo 根目录名，
    其后的段才是 repo 内相对路径；取不到时返回空列表。
    """
    parts = [p for p in str(file_path).replace('\\', '/').split('/') if p]
    try:
        changed_at = len(parts) - 1 - parts[::-1].index('changed')
    except ValueError:
        return []
    return parts[changed_at + 1:]


def _generated_file_is_shown(file_path):
    """generated 文件是否属于 ① 节点展示范围（只展示源文件/文档类产物）。

    排除：
    - test/、mca/、.migrate_verify/ 顶层目录：② 阶段产物、历史残留与
      ① 验证工作区，不归 ① 节点展示；
    - 编译中间产物：.o/.d/.make/.marks/.gcno/.gcda/.gcov/.so/.a
      （splitext 精确匹配，不会误杀 .md）；
    - 内部产物与缓存目录：.skills/、CMakeFiles/、__pycache__/、build-*/、
      cmake-*/（与文件树 is_build_temp_file 对齐）、.prompt.txt、
      SKILL.md、CMakeCache.txt、scan_result.json——插入侧已过滤新数据，
      此处兜底历史脏数据（与 build_file_tree 的 is_build_temp_file 同理）。
    """
    segments = _repo_rel_segments(file_path)
    if not segments or segments[0] in _PROJECT_MIGRATE_EXCLUDED_TOP_DIRS:
        return False
    if any(seg in _GENERATED_EXCLUDED_SEGMENTS for seg in segments):
        return False
    if any(seg.startswith(_GENERATED_EXCLUDED_SEGMENT_PREFIXES) for seg in segments):
        return False
    base = os.path.basename(str(file_path))
    if base in _GENERATED_EXCLUDED_BASENAMES:
        return False
    if os.path.splitext(base)[1] in _GENERATED_EXCLUDED_EXTS:
        return False
    return True


def query_project_migrate_extra_files(user_name, dir_id):
    """
    查询 ① 代码生成节点需要的缺失文件与迁移新增文件清单。

    Returns:
        {"code": 0, "data": {
            "missing":  [{"file_id", "file_name", "file_path", "is_file"}],   # 红色
            "generated": [{"file_id", "file_name", "file_path", "is_file"}],  # 绿色
        }}
        - missing：type=2 扫描出的缺失文件；其中已有同路径 generated 行的
          （迁移后确认补齐，或 agent 认为无需补而未建——统一按"已了结"处理）
          不再返回，满足"迁移完之后发现不需要增加的缺失文件不显示"。
        - generated：agent 生成的新增文件（is_file=1），排除 test/、mca/
          ② 阶段产物目录（mca/ 为历史残留）。
    """
    status, generated_rows = query_generated_files_from_database(user_name, dir_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    generated_paths = set()
    generated_files = []
    for file_id, file_path, is_file in generated_rows:
        generated_paths.add(str(file_path))
        if not is_file:
            continue  # generated 目录行（父目录链路）不进清单
        if not _generated_file_is_shown(file_path):
            continue
        generated_files.append({
            "file_id": file_id,
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "is_file": bool(is_file),
        })

    status, missing_rows = query_missing_files_sql(user_name, dir_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    missing_files = []
    for file_id, file_path, _miss_type in missing_rows:
        # 已有同路径生成文件 → 缺失已了结（补齐或确认不需要），不显示
        if str(file_path) in generated_paths:
            continue
        missing_files.append({
            "file_id": file_id,
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "is_file": True,
        })

    return {"code": 0, "msg": ResponseCode.OK,
            "data": {"missing": missing_files, "generated": generated_files}}


def generate_file_tree(path, max_depth=None, relative=True):
    """生成文件树JSON结构"""

    def walk_directory(current_path, depth=0):
        """递归遍历目录"""
        result = []
        current_path = Path(current_path)

        # 检查深度限制
        if max_depth is not None and depth >= max_depth:
            return result

        try:
            for item in current_path.iterdir():
                # 构建节点
                node = {
                    "type": "dir" if item.is_dir() else "file",
                    "name": item.name
                }

                # 如果是目录, 递归处理子项
                if item.is_dir():
                    children = walk_directory(item, depth + 1)
                    if children:  # 只有有子项时才添加children字段
                        node["children"] = children

                result.append(node)

        except OSError:
            LOGGER.error(f"权限不足, 跳过: {current_path}")
        return result

    # 生成完整树结构
    root_path = Path(path)
    tree = {
        "type": "dir",
        "name": create_relative_file_path(path) if relative else path,
        "children": walk_directory(root_path)
    }

    return tree


def create_existing_arch_data(existing_arch_data, file_id, task_id, dir_id, relative=True):
    my_data = []
    for path, type in existing_arch_data:
        if type == 0:
            file_path = create_relative_file_path(path) if relative else path
            my_data.append((task_id, dir_id, file_id, file_path, 0))
        else:
            file_dict = generate_file_tree(path, relative=True)
            my_data.append((task_id, dir_id, file_id, file_dict, 1))
    return my_data


def query_existing_arch(user_name, file_id, task_id, dir_id):
    status, existing_arch_data = query_existing_arch_data(user_name, file_id, dir_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    my_data = create_existing_arch_data(existing_arch_data, file_id, task_id, dir_id,
                                        not USE_ABSOLUTE_PATH)

    return {"code": 0, "msg": ResponseCode.OK, "data": my_data}


def query_existing_arch_data(user_name, file_id, dir_id):
    LOGGER.info(
        f"Querying the existing_arch data for user {user_name} dir_id {dir_id} file_id {file_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, {"code": -1, "msg": f"Database {db_path} not found"}
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_EXIST_ARCH_BY_MISSING_FILE_ID_SQL,
                       (file_id,))
        existing_arch_data = cursor.fetchall()
        return True, existing_arch_data
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()


def query_dependence_software(user_name, task_id, dependence_id, user_id):
    status, dependence_software_rows = query_dependence_software_sql(user_name, task_id,
                                                                     dependence_id, user_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "data": create_dependence_software(dependence_software_rows)
    }


def query_dependence_software_sql(user_name, task_id, dependence_id, user_id):
    """
    查询依赖软件建议

    Args:
        user_name: 用户名
        task_id: 任务ID
        dependence_id: 依赖ID
        user_id: 用户ID

    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 软件建议列表, 每个元素为 (task_id, dir_id, file_id, file_path, support_architecture, suggestion)
    """
    try:
        with db_session_scope() as session:
            results = session.query(
                CodemigTaskDependence.task_id,
                CodemigTaskDependence.dir_id,
                FileDependence.file_id,
                FileDependence.file_path,
                SoftwareDependenceSuggestion.support_architecture,
                SoftwareDependenceSuggestion.suggestion
            ).join(
                FileDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).join(
                SoftwareDependenceSuggestion,
                (FileDependence.file_id == SoftwareDependenceSuggestion.file_id) &
                (FileDependence.dependence_id ==
                 SoftwareDependenceSuggestion.dependence_id)
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type == 1
            ).order_by(
                FileDependence.file_path.asc()
            ).all()

            dependence_software_rows = [
                (result.task_id, result.dir_id, result.file_id, result.file_path,
                 result.support_architecture, result.suggestion)
                for result in results
            ]

            return True, dependence_software_rows
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []


def create_dependence_software(software_rows):
    dir_id_set = set()
    dependence_software_rows = []
    for i, row in enumerate(software_rows):
        task_id, dir_id, file_id, file_path, support_architecture, suggestion = row
        dir_id_set.add(dir_id)
        file_index = i + 1
        file_name = os.path.basename(file_path)
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)
        dependence_software_rows.append((file_index, task_id, dir_id, file_id, file_name,
                                         file_path, support_architecture, suggestion))
    return {"dependence_software_rows": dependence_software_rows}


def create_dependence_missing_files(dependence_missing_files_rows):
    dependence_missing_files = []
    for i, row in enumerate(dependence_missing_files_rows):
        task_id, dir_id, file_id, file_path = row
        file_index = i + 1
        file_name = os.path.basename(file_path)
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)
        dependence_missing_files.append(
            (file_index, task_id, dir_id, file_id, file_name, file_path))
    return {"dependence_missing_files": dependence_missing_files}


def query_dependence_missing_files(user_name, task_id, dependence_id, user_id):
    status, dependence_missing_files_rows = query_dependence_missing_files_sql(user_name,
                                                                               task_id,
                                                                               dependence_id,
                                                                               user_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "data": create_dependence_missing_files(dependence_missing_files_rows)
    }


def query_dependence_missing_files_sql(user_name, task_id, dependence_id, user_id):
    """
    查询依赖缺失文件

    Args:
        user_name: 用户名
        task_id: 任务ID
        dependence_id: 依赖ID
        user_id: 用户ID

    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 缺失文件列表, 每个元素为 (task_id, dir_id, file_id, file_path)
    """
    LOGGER.info(f"Querying the missing files for user {user_name} task_id {task_id}"
                f" dependence_id {dependence_id}.")
    try:
        with db_session_scope() as session:
            results = session.query(
                CodemigTaskDependence.task_id,
                CodemigTaskDependence.dir_id,
                FileDependence.file_id,
                FileDependence.file_path
            ).join(
                FileDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type == 2
            ).order_by(
                FileDependence.file_path.asc()
            ).all()

            dependence_missing_files_rows = [
                (result.task_id, result.dir_id, result.file_id, result.file_path)
                for result in results
            ]

            return True, dependence_missing_files_rows
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []


def query_dependence_existing_arch(file_id, dependence_id):
    status, existing_arch_data = query_dependence_existing_arch_data(
        file_id, dependence_id)
    my_data = create_dependence_existing_arch_data(
        existing_arch_data) if not USE_ABSOLUTE_PATH else existing_arch_data
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {"code": 0, "msg": ResponseCode.OK, "data": my_data}


def query_dependence_existing_arch_data(file_id, dependence_id):
    """
    查询依赖现有架构数据

    Args:
        file_id: 文件ID
        dependence_id: 依赖ID

    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 现有架构数据列表, 每个元素为 (file_id, architecture_path)
    """
    LOGGER.info(
        f"Querying the existing_arch data for file_id {file_id} dependence_id {dependence_id}.")
    try:
        with db_session_scope() as session:
            results = session.query(
                DependenceExistingArchitecture.file_id,
                DependenceExistingArchitecture.architecture_path
            ).filter(
                DependenceExistingArchitecture.file_id == file_id,
                DependenceExistingArchitecture.dependence_id == dependence_id
            ).order_by(
                DependenceExistingArchitecture.architecture_path.asc()
            ).all()

            existing_arch_data = [
                (result.file_id, result.architecture_path)
                for result in results
            ]

            return True, existing_arch_data
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []


def create_dependence_existing_arch_data(existing_arch_data):
    my_data = []
    for file_id, path in existing_arch_data:
        file_path = create_relative_file_path(path)
        my_data.append((file_id, file_path))
    return my_data


def query_user_task_dependence_files(user_name, task_id, dependence_id, user_id):
    status, data = query_user_task_dependence_files_from_database(user_name, task_id,
                                                                  dependence_id, user_id)
    if not status:
        return {"code": -1, "msg": "Database Error!"}
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "data": create_dependence_files_data(data)
    }


def query_user_task_dependence_files_from_database(user_name, task_id, dependence_id, user_id):
    """
    查询用户任务依赖文件信息

    Args:
        user_name: 用户名
        task_id: 任务ID
        dependence_id: 依赖ID
        user_id: 用户ID

    Returns:
        tuple: (status, data)
            status: True 表示成功, False 表示失败
            data: 成功时返回 (task_name, created_time, summary, task_file_summary,
                  select_file_info, dependence_name, version), 失败时返回 None
    """
    LOGGER.info(f"Querying the dependence files for user {user_name} task_id {task_id} "
                f"dependence_id {dependence_id}.")
    try:
        with db_session_scope() as session:
            # 1. 查询任务信息
            task = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).first()

            if not task:
                LOGGER.warning(f"Task not found: task_id={task_id}")
                return True, None

            task_name = task.task_name
            # 格式化创建时间（添加8小时, 对应原始SQL的 datetime(created_at, '+8 hours')）
            from datetime import timedelta
            created_time = (task.created_at + timedelta(hours=8)
                            ).strftime('%Y-%m-%d %H:%M:%S') if task.created_at else None

            # 2. 查询依赖包信息
            dependence_package = session.query(DependencePackages).filter(
                DependencePackages.dependence_id == dependence_id
            ).first()

            if not dependence_package:
                LOGGER.warning(
                    f"Dependence package not found: dependence_id={dependence_id}")
                return True, None

            dependence_name = dependence_package.dependence_package
            version = dependence_package.version

            # 3. 查询依赖汇总信息
            summary_results = session.query(
                FileDependenceSuggestion.type.label('suggestion_type'),
                func.count(FileDependenceSuggestion.file_id).label(
                    'num_changes'),
                func.sum(FileDependenceSuggestion.end_line_number -
                         FileDependenceSuggestion.start_line_number + 1).label('num_changed_lines')
            ).join(
                FileDependence,
                (FileDependence.dependence_id == FileDependenceSuggestion.dependence_id) &
                (FileDependence.file_id == FileDependenceSuggestion.file_id)
            ).join(
                CodemigTaskDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type == 0
            ).group_by(
                FileDependenceSuggestion.dependence_id,
                FileDependenceSuggestion.type
            ).order_by(
                FileDependenceSuggestion.type.asc()
            ).all()

            # 将 SQLAlchemy 结果对象转换为元组列表，供后续代码使用
            summary = [
                (r.suggestion_type, r.num_changes, r.num_changed_lines)
                for r in summary_results
            ]

            # 4. 查询任务依赖文件汇总
            task_file_summary_results = session.query(
                FileDependence.type.label('file_type'),
                func.count(FileDependence.file_id).label('number_files')
            ).join(
                CodemigTaskDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type > 0
            ).group_by(
                CodemigTaskDependence.user_id,
                CodemigTaskDependence.task_id,
                FileDependence.type
            ).order_by(
                FileDependence.type.asc()
            ).all()

            task_file_summary = [
                (result.file_type, result.number_files)
                for result in task_file_summary_results
            ]

            # 5. 查询依赖文件信息
            file_info_results = session.query(
                CodemigTaskDependence.task_id,
                CodemigTaskDependence.dir_id,
                FileDependence.file_id,
                FileDependence.file_path,
                func.count(FileDependenceSuggestion.file_id).label(
                    'num_changed_lines')
            ).join(
                FileDependence,
                CodemigTaskDependence.dependence_id == FileDependence.dependence_id
            ).outerjoin(
                FileDependenceSuggestion,
                (FileDependence.dependence_id == FileDependenceSuggestion.dependence_id) &
                (FileDependence.file_id == FileDependenceSuggestion.file_id)
            ).filter(
                CodemigTaskDependence.user_id == user_id,
                CodemigTaskDependence.task_id == task_id,
                CodemigTaskDependence.dependence_id == dependence_id,
                FileDependence.type == 0
            ).group_by(
                CodemigTaskDependence.dir_id,
                FileDependence.dependence_id,
                FileDependence.file_id
            ).order_by(
                FileDependence.file_path.asc()
            ).all()

            select_file_info = [
                (result.task_id, result.dir_id, result.file_id,
                 result.file_path, result.num_changed_lines)
                for result in file_info_results
            ]

            return True, (task_name, created_time, summary, task_file_summary,
                           select_file_info, dependence_name, version)
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None


def query_dependence_file_path_from_database(file_id):
    """
    查询依赖文件路径
    Args:
        file_id: 文件ID
    Returns:
        tuple: (status, file_path)
            status: True 表示成功, False 表示失败
            file_path: 文件路径
    """
    LOGGER.info(f"Querying the dependence file path for file_id {file_id}.")
    try:
        with db_session_scope() as session:
            file_dependence = session.query(FileDependence).filter(
                FileDependence.file_id == file_id
            ).first()
            return True, file_dependence.file_path if file_dependence else None
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"Query dependence file path error: {str(err)}")
        return False, None


def create_dependence_files_data(data):
    (task_name, created_time, summary, task_file_summary, select_file_info, dependence_name,
     version) = data
    files = []
    for i, row in enumerate(select_file_info):
        task_id, dir_id, file_id, file_path, num_changed_lines = row
        if not USE_ABSOLUTE_PATH:
            file_path = create_relative_file_path(file_path)

        file_index = i + 1
        file_name = os.path.basename(file_path)
        files.append((file_index, task_id, dir_id, file_id, file_name,
                      file_path, num_changed_lines))
    return {
        "task_name": task_name,
        "created_time": created_time,
        "files": files,
        "dependence_name": dependence_name,
        "version": version,
        "summary": convert_summary(summary, task_file_summary),
    }


def check_file_exists_handler(user_name, task_id, dir_id,
                              file_id, dependence_id):
    """检查文件是否存在并返回文件内容"""
    LOGGER.info(f"Checking file exists for user {user_name} task_id {task_id} \
        dir_id {dir_id} file_id {file_id} dependence_id {dependence_id}")

    if dependence_id:
        status, file_path = query_dependence_file_path_from_database(file_id)
        if not status:
            return {"code": -1, "msg": "Database Error!"}
    else:
        status, file_path = query_file_path_from_database(user_name, dir_id, file_id)
        if not status:
            return {"code": -1, "msg": "Database Error!"}

    # 检查文件是否存在
    if os.path.exists(file_path):
        if os.path.isdir(file_path):
            return {
                "code": 0,
                "msg": ResponseCode.OK,
                "file_exists": True,
                "file_content": ""
            }
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                file_content = file.read()
            return {
                "code": 0,
                "msg": ResponseCode.OK,
                "file_exists": True,
                "file_content": file_content
            }
        except (OSError, IOError, FileNotFoundError, PermissionError) as e:
            LOGGER.error(f"Error reading file {file_path}: {e}")
            return {"code": -1, "msg": f"Error reading file: {str(e)}"}
    else:
        return {
            "code": 0,
            "msg": ResponseCode.OK,
            "file_exists": False,
            "file_content": ""
        }


def save_file_content_handler(user_name, task_id, dir_id, file_id,
                              dependence_id, content):
    """保存文件内容"""
    LOGGER.info(f"Saving file content for user {user_name} task_id {task_id} \
        dir_id {dir_id} file_id {file_id} dependence_id {dependence_id}")
    is_file = 1
    if dependence_id:
        status, file_path = query_dependence_file_path_from_database(file_id)
        if not status:
            return {"code": -1, "msg": "Database Error!"}
    else:
        status, msg = commit_git_repo(
            user_name, dir_id,
            "manual", "before",
            src="codemig-file-change-view",
            reason="user-save",
        )
        if not status:
            LOGGER.warning(f"Failed to save git state after saving file content: {msg}")
        status, file_info = query_file_info_from_database(user_name, dir_id, file_id)
        if not status:
            return {"code": -1, "msg": "Database Error!"}
        file_path, _, _, is_file = file_info

    if not is_file:
        return {"code": -1, "msg": "This is a dir!"}
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 保存文件内容
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        if not dependence_id:
            status, msg = commit_git_repo(
                user_name, dir_id,
                "manual", "after",
                src="codemig-file-change-view",
                reason="user-save",
            )
            if not status:
                LOGGER.warning(f"Failed to save git state after saving file content: {msg}")
        return {"code": 0, "msg": ResponseCode.OK, "saved": True}
    except (OSError, IOError, FileNotFoundError, PermissionError) as e:
        LOGGER.error(f"Error saving file {file_path}: {e}")
        return {"code": -1, "msg": f"Error saving file: {str(e)}"}
