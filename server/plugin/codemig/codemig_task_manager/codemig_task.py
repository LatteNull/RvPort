# 标准库导入
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import defaultdict
from contextlib import closing
from pathlib import Path

# 第三方库导入
import sqlcipher3

# 项目路径设置
MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# 项目导入 - common 模块
from common.db.SQLOperation import DatabaseException, db_session_scope, get_conn
from common.public import logger
from common.public.public import get_codemig_data_path
from common.response.response_code import ResponseCode

# 项目导入 - framework 模块
from framework.config_manager.config import ConfigKeys, SysConfig
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from framework.log_manager.operation_log import record_operation_log

# 项目导入 - plugin.codemig 模块
from plugin.codemig.codemig_common.codemig_common_utils import (
    BATCH_SIZE,
    BEGIN_TRANSACTION,
    extract_file,
    FileSource,
    get_database_path,
)
from plugin.codemig.codemig_common.common_git import commit_git_repo,get_repo_path
from plugin.codemig.codemig_common.common_sql import (
    CREATE_TASK_AI_TABLE_SQL,
    CREATE_TASK_DIRECTORY_EXISTING_ARCHITECTURE_TABLE_SQL,
    CREATE_TASK_DIRECTORY_FILE_SUGGESTION_TABLE_SQL,
    CREATE_TASK_DIRECTORY_FILE_TABLE_SQL,
    CREATE_TASK_DIRECTORY_SOFTWARE_SUGGESTION_TABLE_SQL,
    INSERT_CHANGED_FILE_SQL,
    INSERT_EXISTING_ARCHITECTURE_DIR_SQL,
    INSERT_EXISTING_ARCHITECTURE_SQL,
    INSERT_FILE_SQL,
    INSERT_SUGGESTION_SOFTWARE_SQL,
    INSERT_SUGGESTION_SQL,
    TASK_DIRECTORY_EXISTING_ARCHITECTURE_KEY_INDEX,
    TASK_DIRECTORY_FILE_KEY_INDEX,
    TASK_DIRECTORY_FILE_SUGGESTION_KEY_INDEX,
    TASK_DIRECTORY_FILE_TYPE_KEY_INDEX,
    TASK_DIRECTORY_SOFTWARE_SUGGESTION_KEY_INDEX,
    UPDATE_CHANGED_FILE_SQL,
    SELECT_FILE_BY_PATH_SQL,
    TASK_AI_KEY_INDEX,
)
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_config.models import UserConfiguration
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage
from plugin.codemig.codemig_task_manager.arch_missing_process import detect_arch, group_files
from plugin.codemig.codemig_task_manager.models import CodemigTaskDirectory, CodemigTasks
from plugin.codemig.codemig_task_manager.task_common import TaskStatus
from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.dependence_process.dependence_task import submit_dependence_task
from plugin.codemig.main.codemig_processor import CodemigProcessor

LOGGER = logger.init_log('codemig')

def update_config(user_id, dep_info, session):
    """
    更新用户配置（UPSERT 操作）
    
    Args:
        user_id: 用户ID
        dep_info: 依赖信息对象
        session: 数据库会话
    """
    if dep_info.scan != 1:
        return
    
    # 查询现有配置
    config = session.query(UserConfiguration).filter(
        UserConfiguration.user_id == user_id
    ).first()
    
    if config:
        # 更新现有配置
        if dep_info.lang == "python":
            config.python_interpreter = dep_info.python
            config.python_image_source = dep_info.python_config
            # 保留 go 配置（如果存在）
            if dep_info.go:
                config.go_install_path = dep_info.go
            if dep_info.go_config:
                config.go_environment = dep_info.go_config
        elif dep_info.lang == "go":
            config.go_install_path = dep_info.go
            config.go_environment = dep_info.go_config
            # 保留 python 配置（如果存在）
            if dep_info.python:
                config.python_interpreter = dep_info.python
            if dep_info.python_config:
                config.python_image_source = dep_info.python_config
    else:
        # 插入新配置
        new_config = UserConfiguration(
            user_id=user_id,
            python_interpreter=dep_info.python if dep_info.lang == "python" else None,
            python_image_source=dep_info.python_config if dep_info.lang == "python" else None,
            go_install_path=dep_info.go if dep_info.lang == "go" else None,
            go_environment=dep_info.go_config if dep_info.lang == "go" else None
        )
        session.add(new_config)


def check_user_task_limit(user_id):
    status, task_limit, _ = SysConfig.query_system_configuration(ConfigKeys.TASK_PER_USER)
    count = -1
    try:
        task_limit = int(task_limit)
    except (ValueError, TypeError, AttributeError):
        LOGGER.error(f"Error parsing task limit for config TASK_PER_USER: {task_limit}")
        task_limit = -1
    if not status:
        task_limit = 30
    if task_limit > 0:
        try:
            with db_session_scope() as session:
                # 使用 ORM 查询用户任务数量（status != 4，即未删除的任务）
                count = session.query(CodemigTasks).filter(
                    CodemigTasks.user_id == user_id,
                    CodemigTasks.status != 4
                ).count()
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error(f"check user task count error of db error: {str(err)}")
            return True
        if count >= task_limit:
            return False
    return True


def insert_task_db(user_id, task_name, dep_info, dir_id):
    """
    插入任务到数据库
    
    Args:
        user_id: 用户ID
        task_name: 任务名称
        dep_info: 依赖信息对象
        dir_id: 目录ID    
    Returns:
        tuple: (success: bool, task_id: int or None) 成功返回 (True, task_id)，失败返回 (False, None)
    """
    try:
        with db_session_scope() as session:
            # 更新用户配置
            update_config(user_id, dep_info, session)
            
            # 创建新任务
            new_task = CodemigTasks(
                user_id=user_id,
                task_name=task_name,
                is_scan_dependence=dep_info.scan,
                python_interpreter=dep_info.python,
                python_image_source=dep_info.python_config,
                go_install_path=dep_info.go,
                go_environment=dep_info.go_config
            )
            session.add(new_task)
            session.flush()  # 获取自增ID
            task_id = new_task.task_id
            
            # 批量插入任务目录关联
            task_dir_objects = [
                CodemigTaskDirectory(
                    task_id=task_id,
                    dir_id=dir_id
                )
            ]
            session.bulk_save_objects(task_dir_objects)
            
            # 批量更新目录的 has_linked_task 状态
            # dir_list 格式为 [(dir_id,), ...]
            session.query(CodemigDirectoryStorage).filter(
                CodemigDirectoryStorage.dir_id == dir_id
            ).update({
                CodemigDirectoryStorage.has_linked_task: 1
            }, synchronize_session=False)
            
            # 事务会在 db_session_scope 退出时自动提交
            return True, task_id
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f"{user_id} create {task_name} failed: %s", err)
        return False, None




def raise_error_for_wrong_file_type(file_type):
    error_msg = f"Error: Unsupported file type: {file_type}."
    LOGGER.error(error_msg)
    raise ValueError(error_msg)


def create_insert_values(file_path, user_id, task_id, dir_id, solver,
                         change_list):
    file_type = solver.migration_class()
    if file_type == MigrationClass.TEXT:
        solver_type = solver.get_solver_type()
        append_or_replace = solver.append_or_replace()
        return [(file_path, user_id, task_id, dir_id, solver_type,
                 append_or_replace, start_lineno, end_lineno, suggestion,
                 code_too_long, mycode) for start_lineno, end_lineno,
                suggestion, code_too_long, mycode in change_list]
    if file_type == MigrationClass.DYNAMIC_LINK_LIBRARY:
        return [(file_path, user_id, task_id, dir_id, arch, suggestion)
                for arch, suggestion in change_list]
    raise_error_for_wrong_file_type(file_type)
    return None

def create_changes(user_id, task_id, dir_id, file_solvers_result, file_path):
    file_type_and_changes: defaultdict[MigrationClass, list] = defaultdict(list)
    for solver, result_list in file_solvers_result.items():
        if not result_list:
            continue
        change_list, _ = result_list
        if not change_list:
            continue
        file_type = solver.migration_class()
        insert_values = create_insert_values(file_path, user_id, task_id, dir_id, solver,
                                             change_list)
        file_type_and_changes[file_type].extend(insert_values)
    return file_type_and_changes

def process_target_file(file_path, user_id, task_id, dir_id, my_files, text_file_changes,
                        lib_file_changes):
    file_solvers_result = CodemigProcessor.process_file(file_path)
    file_type_and_changes = create_changes(user_id, task_id, dir_id,
                                           file_solvers_result, file_path)
    for file_type, changes in file_type_and_changes.items():
        if not changes:
            continue
        my_files.append((user_id, task_id, dir_id, file_path, file_type.value))
        if file_type == MigrationClass.TEXT:
            text_file_changes.extend(changes)
        elif file_type == MigrationClass.DYNAMIC_LINK_LIBRARY:
            lib_file_changes.extend(changes)
        else:
            raise_error_for_wrong_file_type(file_type)


def process_extracted_path(user_id, task_id, dir_id, extract_path):
    my_files, text_file_changes, lib_file_changes, missing_file = [], [], [], {}
    skip_dir, missing_dir = [], {}
    for root, dirs, files in os.walk(extract_path, topdown=True):
        grouped_dirs = detect_arch(dirs)
        for missing, other_list in grouped_dirs['missing'].items():
            missing_dir[os.path.join(root, missing)] = [os.path.join(root, dir) for dir in
                                                        other_list[0]]
            skip_dir.extend(other_list[0])
        for found, other_list in grouped_dirs['found'].items():
            skip_dir.extend(other_list[0])
            skip_dir.extend(found)

        dirs[:] = [d for d in dirs if d not in ['.git', '.github'] and d not in skip_dir]

        miss, found, skip = group_files(files)
        for m, other_list in miss.items():
            missing_file[os.path.join(root, m)] = [os.path.join(root, other) for other in
                                                   other_list]
        for file_name in files:
            if file_name in skip:
                continue
            file_path = os.path.join(root, file_name)
            process_target_file(file_path, user_id, task_id, dir_id, my_files, text_file_changes,
                                lib_file_changes)
    return my_files, text_file_changes, lib_file_changes, missing_file, missing_dir


def process_extracted_dir(miss_files, user_id, dir_id):
    # results = DirSolver.solve(extract_path)
    new_results = {}
    for missing_path, arch_paths in miss_files.items():
        missing_path_key = (missing_path, user_id, dir_id)
        for arch_path in arch_paths:
            if missing_path_key in new_results:
                new_results[missing_path_key].append((arch_path, user_id, dir_id))
            else:
                new_results[missing_path_key] = [(arch_path, user_id, dir_id)]
    return new_results


def process_missing_dir(miss_dirs, user_id, dir_id):
    new_results = {}
    for missing_path, arch_paths in miss_dirs.items():
        missing_path_key = (missing_path, user_id, dir_id)
        for arch_path in arch_paths:
            if missing_path_key in new_results:
                new_results[missing_path_key].append((arch_path, user_id, dir_id))
            else:
                new_results[missing_path_key] = [(arch_path, user_id, dir_id)]
    return new_results


def create_processing_data(user_id, task_id, dir_id, source_path, dep_info):
    my_files, text_file_changes, lib_changes, missing_files, missing_dirs = [], [], [], {}, {}

    submit_dependence_task(source_path, dep_info, dir_id, task_id, user_id)

    # 文件级数据处理
    tmp_files, tmp_text, tmp_lib, miss_file, miss_dir = process_extracted_path(user_id,
                                                                                task_id, dir_id,
                                                                                source_path)

    my_files.extend(tmp_files)
    text_file_changes.extend(tmp_text)
    lib_changes.extend(tmp_lib)
    # 目录级数据处理
    missing_file_data = process_extracted_dir(miss_file, user_id, dir_id)
    missing_path_data = process_missing_dir(miss_dir, user_id, dir_id)
    missing_files.update(missing_file_data)
    missing_dirs.update(missing_path_data)
    return (my_files, text_file_changes, lib_changes, missing_files, missing_dirs)


def create_prepared_text_changes(file_path_to_file_id, text_file_changes):
    prepared_text_file_changes = []
    for change in text_file_changes:
        (file_path, user_id, task_id, dir_id, solver_type, append_or_replace,
         start_lineno, end_lineno, suggestion, code_too_long, mycode) = change
        lookup_key = (user_id, task_id, dir_id, file_path, MigrationClass.TEXT.value)
        if lookup_key not in file_path_to_file_id:
            raise sqlite3.Error(f"Error finding file Id with key: {lookup_key}")
        file_id = file_path_to_file_id[lookup_key]
        prepared_text_file_changes.append(
            (file_id, solver_type, append_or_replace, start_lineno,
             end_lineno, suggestion, code_too_long.value, mycode))
    return prepared_text_file_changes

def create_prepared_lib_changes(file_path_to_file_id, lib_file_changes):
    prepared_lib_file_changes = []
    for change in lib_file_changes:
        (file_path, user_id, task_id, dir_id, support_architecture, suggestion) = change
        lookup_key = (user_id, task_id, dir_id, file_path,
                      MigrationClass.DYNAMIC_LINK_LIBRARY.value)
        if lookup_key not in file_path_to_file_id:
            raise sqlite3.Error(f"Error finding file Id with key: {lookup_key}")
        file_id = file_path_to_file_id[lookup_key]
        prepared_lib_file_changes.append(
            (file_id, support_architecture, suggestion))
    return prepared_lib_file_changes

def save_changes_to_database(user_name, dir_id, my_files, 
            text_file_changes, lib_file_changes, missing_files, missing_dirs):
    LOGGER.info("Saving the changes to the database.")

    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, "Error: Database not found!!"

    file_path_to_file_id = {}
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(BEGIN_TRANSACTION)
            # 第一部分：文件级数据存储
            if my_files:
                for my_file in my_files:
                    info = (FileSource.CHANGED.value, my_file[4], my_file[3])
                    try:
                        cursor.execute(UPDATE_CHANGED_FILE_SQL, info)
                        cursor.execute(SELECT_FILE_BY_PATH_SQL, (my_file[3],))
                        result = cursor.fetchone()
                        if result:
                            id = result[0]
                        else:
                            LOGGER.error("Get file id failed for file path: %s", my_file[3])
                            continue
                    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
                        LOGGER.error("Database operation failed: %s", err)
                        continue
                    file_path_to_file_id[my_file] = id
                prepared_text_file_changes = create_prepared_text_changes(file_path_to_file_id,
                                                                          text_file_changes)
                for i in range(0, len(prepared_text_file_changes), BATCH_SIZE):
                    cursor.executemany(INSERT_SUGGESTION_SQL,
                                       prepared_text_file_changes[i:i + BATCH_SIZE])
                prepared_lib_file_changes = create_prepared_lib_changes(file_path_to_file_id,
                                                                        lib_file_changes)
                for i in range(0, len(prepared_lib_file_changes), BATCH_SIZE):
                    cursor.executemany(INSERT_SUGGESTION_SOFTWARE_SQL,
                                       prepared_lib_file_changes[i:i + BATCH_SIZE])
            # 第二部分：目录级数据存储
            if missing_files:
                for missing_path_key, arch_paths in missing_files.items():
                    # 插入主表
                    cursor.execute(INSERT_CHANGED_FILE_SQL,
                                   (missing_path_key[1], missing_path_key[2],
                                    missing_path_key[0], MigrationClass.MISSING_ARCH_FILE.value,
                                    FileSource.MISSING.value, True))
                    parent_file_id = cursor.lastrowid
                    arch_data = [(parent_file_id, arch_path[0]) for
                                 arch_path in arch_paths]
                    # 批量插入子表
                    cursor.executemany(INSERT_EXISTING_ARCHITECTURE_SQL, arch_data)
            if missing_dirs:
                for missing_path_key, arch_paths in missing_dirs.items():
                    # 插入主表
                    cursor.execute(INSERT_CHANGED_FILE_SQL,
                                   (missing_path_key[1], missing_path_key[2],
                                    missing_path_key[0], MigrationClass.MISSING_ARCH_FILE.value,
                                    FileSource.MISSING.value, False))
                    parent_file_id = cursor.lastrowid
                    arch_data = [(parent_file_id, arch_path[0]) for
                                 arch_path in arch_paths]
                    # 批量插入子表
                    cursor.executemany(INSERT_EXISTING_ARCHITECTURE_DIR_SQL, arch_data)
            conn.commit()
            return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False


def process_directory(user_name, user_id, task_id, dir_id, source_path, dep_info):
    try:
        processing_data = create_processing_data(user_id, task_id, dir_id, source_path,
                                                 dep_info)
    except (AttributeError, RuntimeError) as e:
        error_msg = f"Processing directory failed: {e}"
        LOGGER.error(error_msg)
        CodemigTasks.update_task_status(task_id, TaskStatus.FAILED)
        return False, error_msg

    my_files, text_file_changes, lib_file_changes, missing_files, miss_dirs = processing_data
    status = save_changes_to_database(user_name, dir_id, my_files, 
                                      text_file_changes, lib_file_changes,
                                      missing_files, miss_dirs)
    if status:
        CodemigTasks.update_task_status(task_id, TaskStatus.SUCCESS)
        return True, None
    else:
        CodemigTasks.update_task_status(task_id, TaskStatus.FAILED)
        return False, "Error: Failed to save changes to database!!!"


def create_database_of_task(user_name, dir_id):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TASK_DIRECTORY_FILE_TABLE_SQL)
            cursor.execute(TASK_DIRECTORY_FILE_KEY_INDEX)
            cursor.execute(TASK_DIRECTORY_FILE_TYPE_KEY_INDEX)
            cursor.execute(CREATE_TASK_DIRECTORY_FILE_SUGGESTION_TABLE_SQL)
            cursor.execute(TASK_DIRECTORY_FILE_SUGGESTION_KEY_INDEX)
            cursor.execute(CREATE_TASK_DIRECTORY_SOFTWARE_SUGGESTION_TABLE_SQL)
            cursor.execute(TASK_DIRECTORY_SOFTWARE_SUGGESTION_KEY_INDEX)
            cursor.execute(CREATE_TASK_DIRECTORY_EXISTING_ARCHITECTURE_TABLE_SQL)
            cursor.execute(TASK_DIRECTORY_EXISTING_ARCHITECTURE_KEY_INDEX)
            cursor.execute(CREATE_TASK_AI_TABLE_SQL)
            cursor.execute(TASK_AI_KEY_INDEX)
            conn.commit()
            return True, "Database created successfully."
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, str(err)


def save_files_to_database(user_name, user_id, dir_id, files_dir_path:Path, source):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, "Database does not exist."
    if not files_dir_path.exists():
        return False, "Files directory does not exist."

    info_list = []
    for root, dirs, files in files_dir_path.walk():
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            info = (user_id, dir_id, dir_path, source, False)
            info_list.append(info)
        for file_name in files:
            file_path = os.path.join(root, file_name)
            info = (user_id, dir_id, file_path, source, True)
            info_list.append(info)

    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(BEGIN_TRANSACTION)
            for i in range(0, len(info_list), BATCH_SIZE):
                cursor.executemany(INSERT_FILE_SQL, info_list[i:i + BATCH_SIZE])
            conn.commit()
            return True, ''
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error(f"save files to database error:{str(err)}")
        return False, str(err)


def create_task(user_name, user_id, task_name, dir_id, zip_name, dep_info: DependenceInfo):
    """
    返回值: 
    status: True or False
    msg: 错误信息
    extract_path_original: 原始文件目录
    """
    LOGGER.info(f"Inserting the task information into the database.")
    status = check_user_task_limit(user_id)
    if not status:
        return False, "The task limit has been reached. Please delete some tasks and try again.", \
            None
    my_path = Path(get_codemig_data_path()) / user_name / str(dir_id)
    file_path = my_path / zip_name
    code_path = get_repo_path(user_name, dir_id)
    if not file_path.exists():
        return False, f"Create task failed: file {file_path} not found.", None

    status = extract_file(file_path, code_path)
    if not status:
        if code_path.exists():
            shutil.rmtree(code_path)
        file_path.unlink()
        return False, f"Create task failed: uncompress upload file {file_path} failed.", None
    # 删除原始压缩文件
    file_path.unlink()

    if not code_path.exists():
        return False, f"Create task failed: extract path {code_path} not found.", None

    status, msg = create_database_of_task(user_name, dir_id)
    if not status:
        LOGGER.error(f"create db error:{msg}")
        return False, f"create db error:{msg}", None

    status, msg = save_files_to_database(user_name, user_id, dir_id, code_path,
                                         FileSource.ORIGINAL.value)
    if not status:
        LOGGER.error(f"save nodes to database error:{msg}")
        return False, f"save nodes to database error:{msg}", None

    # 执行 Git 操作：初始化仓库并提交
    status, git_info = commit_git_repo(
        user_name, dir_id,
        "manual", "init",
        src="codemig-init",
        reason="first-init",
    )
    if not status:
        return False, f"Failed to initialize and commit git repository: {git_info}", None

    status, msg = insert_task_db(user_id, task_name, dep_info, dir_id)
    if not status:
        LOGGER.error(f"{user_id} create {task_name} failed: %s, try again...", msg)
        time.sleep(0.5)
        status2, msg2 = insert_task_db(user_id, task_name, dep_info, dir_id)
        if not status2:
            LOGGER.error(f"{user_id} create {task_name} failed again: %s", msg2)
            return False, f"insert {task_name} into database failed", None
        return True, msg2, code_path
    return True, msg, code_path


def create_and_process_task(user_name, user_id, task_name, dir_id, zip_name,
                            dep_info: DependenceInfo):
    status, msg, source_path = create_task(user_name, user_id, task_name,
                                           dir_id, zip_name, dep_info)
    if not status:
        return {"code": -1, "msg": msg}
    task_id = msg
    status = CodemigTasks.update_task_status(task_id, TaskStatus.PROCESSING)
    if not status:
        return {"code": -1, "msg": "Error: updating the task status to processing!"}
    status, message = process_directory(user_name, user_id, task_id,
                                        dir_id, source_path, dep_info)
    if not status:
        LOGGER.error(f"Error: Has processing task error: {message}.")
        return {"code": -1, "msg": f"Backend Error! {message}"}
    return {"code": 0, "msg": ResponseCode.OK, "task_id": task_id}


def check_taskname(task_name):
    if not isinstance(task_name, str):
        return False, "名称必须是字符串", "Name must be a string"

        # 基本长度检查
    if len(task_name) == 0:
        return False, "名称不能为空", "Name cannot be empty"

    if len(task_name) > 100:
        return False, f"名称长度不能超过100个字符（当前长度：{len(task_name)}）", f"Name length cannot exceed 100 characters (current: {len(task_name)})"

        # 正则表达式：字母开头，只允许字母、数字、连字符、下划线、点号
    pattern = r'^[a-zA-Z][a-zA-Z0-9\-_.]{0,99}$'

    if not re.match(pattern, task_name):
        # 提供更具体的错误信息
        if not task_name[0].isalpha():
            return False, "名称必须以字母开头", "Name must start with a letter"

        # 检查非法字符
        illegal_chars = set()
        for char in task_name:
            if not (char.isalnum() or char in '-_.'):
                illegal_chars.add(char)

        if illegal_chars:
            illegal_str = ', '.join(f"'{c}'" for c in illegal_chars)
            return False, f"包含非法字符：{illegal_str}。只允许字母、数字、-、_、.", f"Contains illegal characters: {illegal_str}. Only letters, numbers, -, _, . are allowed",

        return False, "名称格式不正确", "Name format is incorrect"

    # 检查保留名称（可选）
    # reserved_names = {'www', 'api', 'git', 'admin', 'test'}
    # if task_name.lower() in reserved_names:
    #     return False, f"'{task_name}'是保留名称，请使用其他名称", f"'{task_name}' is a reserved name, please use another name"

    return True, "名称有效", "Name is valid"


def start_task(user_name, task_name, dir_id, zip_name, dep_info: DependenceInfo, request):
    start = time.time()
    code, msg, en_msg = check_taskname(task_name)
    if not code:
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Create Code Migration Task', OpLogResult.FAILED,
                             f'Task Name "{task_name}" illegal: {en_msg}.')
        return {"code": -1, "msg": msg}
    response = create_and_process_task(user_name, request.user_id, task_name,
                                       dir_id, zip_name, dep_info)
    end = time.time()
    LOGGER.info(f"process code migration task {task_name} cost:{end - start}s")
    if response["code"] == 0:
        task_id = response["task_id"]
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Create Code Migration Task', OpLogResult.SUCCESS,
                             f'create code migration task: {task_name}.')
    else:
        message = response["msg"]
        record_operation_log(request.user_id, request.remote_addr, OpLogModule.CODEMIG,
                             'Create Code Migration Task', OpLogResult.FAILED,
                             f'create code migration task failed:{task_name}, error:{message}')

    return response
