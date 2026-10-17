# 标准库导入
import os
import shutil
import sqlite3
import sys
from pathlib import Path

# 第三方库导入
import sqlcipher3

# 项目路径设置
MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# 项目导入 - common 模块
from common.db.SQLOperation import DatabaseException, db_session_scope, get_conn
from common.public import logger
from common.public.public import get_codemig_data_path
from common.response.response_code import ResponseCode

# 项目导入 - framework 模块
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from framework.log_manager.operation_log import record_operation_log

# 项目导入 - plugin.codemig 模块
from plugin.codemig.codemig_common.common_git import (
    commit_git_repo,
    get_repo_path,
    revert_to_last_commit,
)
from plugin.codemig.codemig_common.common_sql import (
    DELETE_SUGGESTION_BY_CHANGE_ID_SQL,
    INSERT_SUGGESTION_WITH_IGNORE_SQL,
    REMOVE_SUGGESTION_OF_FILE_SQL,
    SELECT_ALL_SUGGESTIONS_BY_FILE_SQL,
    SELECT_IGNORED_SUGGESTIONS_BY_FILE_ID_SQL,
    UPDATE_SUGGESTION_LINE_SQL,
)
from plugin.codemig.codemig_common.codemig_common_utils import (
    BEGIN_TRANSACTION,
    FileSource,
    build_line_offset_table,
    create_new_path,
    get_database_path,
    map_range,
    move_file_to_new_path,
    query_file_path_from_database,
    save_new_file_to_database,
    update_directory_removed_recursively_to_database,
    update_file_removed_to_database,
    update_suggestion_ignored,
    query_file_info_from_database,
)
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage
from plugin.codemig.codemig_task_manager.models import CodemigTaskDirectory, CodemigTasks
from plugin.codemig.codemig_task_manager.task_common import TaskStatus
from plugin.codemig.main.codemig_processor import CodemigProcessor

LOGGER = logger.init_log('codemig')

def save_updated_file_with_content(user_name, dir_id, file_id, content):
    status, file_path = query_file_path_from_database(user_name, dir_id, file_id)
    if not status or file_path is None:
        return {"code": -1, "msg": "Database query error!!!"}

    status, msg = commit_git_repo(
        user_name, dir_id,
        "manual", "before",
        src="codemig-file-change-view",
        reason="user-save",
    )
    if not status:
        LOGGER.warning(f"Failed to save git state before saving file content: {msg}")

    temp_path = create_new_path(file_path, "tmp")
    write_temp_file(temp_path, content)
    my_changes = process_updated_file(file_id, temp_path)
    status = update_file_suggestion_to_database(user_name, dir_id,
                                                file_id, my_changes)
    if not status:
        return {"code": -1, "msg": "Database update or insert error!!!"}
    remove_file_and_move_edited_file(file_path, temp_path)
    status, msg = commit_git_repo(
        user_name, dir_id,
        "manual", "after",
        src="codemig-file-change-view",
        reason="user-save",
    )
    if not status:
        LOGGER.warning(f"Failed to save git state after saving file content: {msg}")
    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "new_file_id": file_id
    }


def save_project_file_with_content(user_name, dir_id, file_id, content):
    """一键迁移手动修改代码的保存（v4.2：保存时行号重绑定）

    与 v4.1 差异：
      - 在 git commit after 之后增加行号重绑定步骤：
        1) 用 difflib 算 old_content → content 的行号偏移表
        2) 对该 file 的所有 suggestion（AI + manual）调 map_range 算新行号
        3) UPDATE kept/shifted 的行号；DELETE invalid 的行
        4) 把映射结果通过 response.line_mapping 返回给前端
      - 不动 git commit、不动 file I/O 主逻辑
      - 重绑定任何异常都被吞掉，不影响保存主流程
    """
    status, file_path = query_file_path_from_database(user_name, dir_id, file_id)
    if not status or file_path is None:
        return {"code": -1, "msg": "Database query error!!!"}

    # ── 0) 读保存前的内容（用于行号映射）；失败时跳过重绑定 ──
    old_content = None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        LOGGER.warning(
            f"[project-manual] 读取旧文件失败，跳过行号重绑定: file_id={file_id} err={e}"
        )

    # ── 1) git commit before ──
    status, msg = commit_git_repo(
        user_name, dir_id,
        "project-manual", "before",
        src="codemig-project-migrate-view",
        reason="user-edit-save",
    )
    if not status:
        LOGGER.warning(f"[project-manual] Failed to save git state before: {msg}")

    # ── 2) 写新内容到磁盘 ──
    temp_path = create_new_path(file_path, "tmp")
    write_temp_file(temp_path, content)
    remove_file_and_move_edited_file(file_path, temp_path)

    # ── 3) git commit after ──
    status, msg = commit_git_repo(
        user_name, dir_id,
        "project-manual", "after",
        src="codemig-project-migrate-view",
        reason="user-edit-save",
    )
    if not status:
        LOGGER.warning(f"[project-manual] Failed to save git state after: {msg}")

    # ── 4) 行号重绑定（v4.2 新增）──
    line_mapping = []
    if old_content is not None and old_content != content:
        try:
            line_mapping = _remap_suggestion_lines(
                user_name, dir_id, file_id, old_content, content
            )
        except (ValueError, TypeError, IndexError) as e:
            LOGGER.error(
                f"[project-manual] 行号重绑定失败（已忽略）: file_id={file_id} err={e}"
            )
            line_mapping = []

    return {
        "code": 0,
        "msg": ResponseCode.OK,
        "new_file_id": file_id,
        "line_mapping": line_mapping,
    }


def _remap_suggestion_lines(user_name, dir_id, file_id, old_content, new_content):
    """对 file 的所有 suggestion 做行号重绑定，返回 mapping 列表

    Returns:
        list of dict:
          {
            'change_id': int,
            'is_manual': int (0=AI, 1=manual),
            'old_start_line': int,
            'old_end_line': int,
            'new_start_line': int | None,
            'new_end_line': int | None,
            'status': 'kept' | 'shifted' | 'invalid',
          }
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return []

    # 1) 算偏移表
    offset_table = build_line_offset_table(old_content, new_content)
    new_lines_count = len(new_content.splitlines())

    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        # 2) 查所有 suggestions
        cursor.execute(SELECT_ALL_SUGGESTIONS_BY_FILE_SQL, (file_id,))
        rows = cursor.fetchall()
        # rows: [(change_id, start_line, end_line, is_manual), ...]

        mapping = []
        to_update = []   # (new_start, new_end, change_id)
        to_delete = []   # [change_id, ...]
        for change_id, old_start, old_end, is_manual in rows:
            new_start, new_end, status = map_range(
                offset_table, int(old_start), int(old_end), new_lines_count
            )
            mapping.append({
                "change_id": int(change_id),
                "is_manual": int(is_manual),
                "old_start_line": int(old_start),
                "old_end_line": int(old_end),
                "new_start_line": new_start,
                "new_end_line": new_end,
                "status": status,
            })
            if status == "invalid":
                to_delete.append(int(change_id))
            else:
                to_update.append((new_start, new_end, int(change_id)))

        # 3) 写 DB
        if to_update or to_delete:
            cursor.execute(BEGIN_TRANSACTION)
            for ns, ne, cid in to_update:
                cursor.execute(UPDATE_SUGGESTION_LINE_SQL, (ns, ne, cid))
            if to_delete:
                cursor.executemany(
                    DELETE_SUGGESTION_BY_CHANGE_ID_SQL,
                    [(change_id,) for change_id in to_delete],
                )
            conn.commit()
            LOGGER.info(
                f"[project-manual] 行号重绑定完成: file_id={file_id} "
                f"updated={len(to_update)} deleted={len(to_delete)}"
            )
        return mapping
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error(f"行号重绑定 DB 操作失败: {err}")
        if conn:
            conn.rollback()
        return []
    finally:
        if conn:
            conn.close()


def remove_file_and_move_edited_file(file_path, temp_path):
    if os.path.exists(file_path):
        os.remove(file_path)
    move_file_to_new_path(temp_path, file_path)
    shutil.rmtree(create_tmp_parent(temp_path))


def create_tmp_parent(temp_path):
    relpath = Path(os.path.relpath(temp_path, get_codemig_data_path()))
    path_parts = list(relpath.parts)
    new_path_parts = path_parts[:3]
    return os.path.join(get_codemig_data_path(), Path(*new_path_parts).as_posix())


def process_updated_file(file_id, temp_path):
    file_solvers_result = CodemigProcessor.process_file(temp_path)
    my_changes = []
    for solver, result_list in file_solvers_result.items():
        if not result_list:
            continue
        change_list, _ = result_list
        if not change_list:
            continue
        solver_type = solver.get_solver_type()
        append_or_replace = solver.append_or_replace()
        insert_values = [(file_id, solver_type,
                          append_or_replace, start_lineno, end_lineno,
                          suggestion, code_too_long.value, mycode, 0)
                         for start_lineno, end_lineno, suggestion,
                         code_too_long, mycode in change_list]
        my_changes.extend(insert_values)
    return my_changes


def write_temp_file(temp_path, content):
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    if os.path.exists(temp_path):
        os.remove(temp_path)
    with open(temp_path, 'w', encoding='utf-8') as file:
        file.write(content)


def _match_ignored_suggestion(my_changes, ignored_suggestions):
    if len(my_changes) < 1 or len(ignored_suggestions) < 1:
        return
    for row in ignored_suggestions:
        start_i = row[0]
        end_i = row[1]
        suggestion_i = row[2]
        code_i = row[3]

        for info in my_changes:
            file_id, solver_type, append_or_replace, start_lineno, end_lineno,\
            suggestion, code_too_long, mycode, ignored = info
            # if start_i == start_lineno and end_i == end_lineno and \
            if suggestion_i == suggestion and code_i == mycode and ignored == False:
                info_new = (file_id, solver_type, append_or_replace, start_lineno, end_lineno,\
                            suggestion, code_too_long, mycode, True)
                my_changes.remove(info)
                my_changes.append(info_new)
                break

def update_file_suggestion_to_database(user_name, dir_id, file_id, my_changes):
    """
    更新文件的建议，删除旧的、保存新的
    Returns:
        tuple: (status, new_file_id)
            status: True 表示成功，False 表示失败
    """
    LOGGER.info("Update the file suggestion to the database.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(BEGIN_TRANSACTION)
        cursor.execute(REMOVE_SUGGESTION_OF_FILE_SQL, (file_id,))
        if my_changes:
            cursor.execute(SELECT_IGNORED_SUGGESTIONS_BY_FILE_ID_SQL, (file_id,))
            result = cursor.fetchall()
            if result:
                _match_ignored_suggestion(my_changes, result)
            cursor.executemany(INSERT_SUGGESTION_WITH_IGNORE_SQL, my_changes)
        conn.commit()
        return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def mark_as_deleted(task_id, request):
    LOGGER.info("Delete the task related information.")
    # 删除数据库中数据
    result = OpLogResult.SUCCESS
    detail = ''
    try:
        with db_session_scope() as session:
            # 1. 更新表codemig_tasks，将删除任务对应status字段置为4
            # 使用 ORM 更新任务状态，同时检查 user_id
            affected_rows = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id,
                CodemigTasks.user_id == request.user_id
            ).update({
                CodemigTasks.status: 4  # 4 表示已删除
            })
            
            if affected_rows == 0:
                result = OpLogResult.FAILED
                detail = f'code migration task not found: {task_id}.'
                return {'code': '-1', 'msg': "task not found"}

            # 2. 查询任务关联的所有目录ID
            task_directories = session.query(CodemigTaskDirectory.dir_id).filter(
                CodemigTaskDirectory.task_id == task_id
            ).all()
            
            dir_ids = [dir_id for (dir_id,) in task_directories]
            
            # 3. 更新表codemig_directory_storage，将删除任务对应has_removed字段置为1
            if dir_ids:
                session.query(CodemigDirectoryStorage).filter(
                    CodemigDirectoryStorage.dir_id.in_(dir_ids)
                ).update({
                    CodemigDirectoryStorage.has_removed: 1
                }, synchronize_session=False)
            
            # 4. 查询任务信息获取 task_name
            task = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).first()
            
            if task:
                detail = f'delete code migration task: {task.task_name}.'
            else:
                detail = f'delete code migration task: {task_id}.'
            
            # 事务会在 db_session_scope 退出时自动提交
            return {'code': '0', 'msg': "ok"}
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        CodemigTasks.update_task_status(task_id, TaskStatus.FAILED)
        result = OpLogResult.FAILED
        detail = f'delete task:{task_id} database error: {str(err)}'
        return {'code': '-1', 'msg': "delete failed"}
    finally:
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Delete Code Migration Task', result,
                             detail)


def delete_user(user_id):
    """
    删除用户相关的所有任务和目录（软删除）
    
    Args:
        user_id: 用户ID
        
    Returns:
        None
    """
    try:
        with db_session_scope() as session:
            # 1. 更新 codemig_directory_storage 表，将 has_removed 字段置为 1
            session.query(CodemigDirectoryStorage).filter(
                CodemigDirectoryStorage.user_id == user_id
            ).update({
                CodemigDirectoryStorage.has_removed: 1
            }, synchronize_session=False)
            
            # 2. 更新 codemig_tasks 表，将 status 字段置为 4（已删除）
            session.query(CodemigTasks).filter(
                CodemigTasks.user_id == user_id
            ).update({
                CodemigTasks.status: 4  # 4 表示已删除
            }, synchronize_session=False)

            # 事务会在 db_session_scope 退出时自动提交
            LOGGER.info(f"Delete the task of {user_id}.")
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)


def create_file_or_directory_handler(user_name, user_id, dir_id,
                                     file_path, is_directory):
    # 构建完整路径：{data_path}/{user_name}/{dir_id}/changed/{file_path}
    base_path = get_repo_path(user_name, dir_id)
    # 处理相对路径（移除开头的./）
    if file_path.startswith('./'):
        file_path = file_path[2:]
    elif file_path.startswith('/'):
        file_path = file_path[1:]
    full_path = base_path / file_path
    if os.path.exists(full_path) and os.path.isdir(full_path) == is_directory:
        return {'code': -1, 'msg': 'This path already exists'}

    try:
        if is_directory:
            full_path.mkdir(parents=True, exist_ok=True)
            LOGGER.info(f"创建目录成功: {full_path}")
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if not full_path.exists():
                full_path.touch()
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write('')
            LOGGER.info(f"创建文件成功: {full_path}")
    except (OSError, PermissionError, IsADirectoryError, ValueError, TypeError) as e:
        LOGGER.error(f"创建文件或目录失败: {str(e)}")
        return {"code": -1, "msg": f"创建文件或目录失败: {str(e)}"}

    status, _ = save_new_file_to_database(user_name, user_id, dir_id,
                            full_path.as_posix(), FileSource.CHANGED.value,
                            not is_directory)
    if not status:
        return {"code": -1, "msg": "数据库操作失败"}

    return {"code": 0, "msg": ResponseCode.OK}



def delete_file_or_directory_handler(user_name, dir_id, file_id):
    """删除文件或目录"""
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return {"code": -1, "msg": "Database not found!"}

    status, file_info = query_file_info_from_database(user_name, dir_id, file_id)
    if not status:
        return {"code": -1, "msg": "Database query error!!!"}
    file_path, file_sources, _, _ = file_info
    if file_sources == FileSource.ORIGINAL.value or file_sources == FileSource.MISSING.value:
        return {"code": -2, "msg": f"删除文件或目录的类型是: {file_sources}"}

    status = False
    if os.path.exists(file_path):
        try:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
                status = update_directory_removed_recursively_to_database(user_name, dir_id, file_path)
            else:
                os.remove(file_path)
                status = update_file_removed_to_database(user_name, dir_id, file_id)
        except (OSError, PermissionError, IsADirectoryError, ValueError, TypeError) as e:
            LOGGER.error(f"删除文件或目录失败: {str(e)}")
            return {"code": -1, "msg": f"删除文件或目录失败: {str(e)}"}
    else:
        try:
            status = update_directory_removed_recursively_to_database(user_name, dir_id, file_path)
        except (OSError, PermissionError, IsADirectoryError, ValueError, TypeError) as e:
            LOGGER.error(f"删除文件或目录失败: {str(e)}")
            return {"code": -1, "msg": f"删除文件或目录失败: {str(e)}"}

    if not status:
        return {"code": -1, "msg": "Database update error!!!"}
    return {"code": 0, "msg": ResponseCode.OK}

def update_suggestion_ignored_handler(user_name, dir_id, file_id, change_id, ignored):
    status = update_suggestion_ignored(user_name, dir_id, file_id, change_id, ignored)
    if not status:
        LOGGER.error("Database update suggestion ignored error!!!")
        return {"code": -1, "msg": "Database update error!!!"}
    return {"code": 0, "msg": ResponseCode.OK}

def file_rollback_handler(user_name, dir_id, file_id):
    """
    文件回滚
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return {"code": -1, "msg": "Database not found!", "content": ""}

    status, file_path = query_file_path_from_database(user_name, dir_id, file_id)
    if not status:
        return {"code": -1, "msg": "Database query error!!!", "content": ""}
    if not os.path.exists(file_path):
        return {"code": -1, "msg": "File not found!!!", "content": ""}
    if os.path.isdir(file_path):
        return {"code": -1, "msg": "This is a directory!!!", "content": ""}

    status, msg, content = revert_to_last_commit(user_name, dir_id, Path(file_path))
    if not status or len(content) == 0:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"code": -1, "msg": msg, "content": content}

    my_changes = process_updated_file(file_id, file_path)
    status = update_file_suggestion_to_database(user_name, dir_id,
                                                file_id, my_changes)
    if not status:
        LOGGER.error("Update suggestion failed when rolling back file.")

    return {"code": 0, "msg": ResponseCode.OK, "content": content}
