import sys

import os
from collections import defaultdict

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.db.SQLOperation import db_session_scope, DatabaseException
from plugin.codemig.dependence_process.models import (
    DependencePackages, FileDependence,
    FileDependenceSuggestion, SoftwareDependenceSuggestion,
    DependenceExistingArchitecture, CodemigTaskDependence
)
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.main.dir_solver import DirSolver
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.main.codemig_processor import CodemigProcessor
from plugin.codemig.codemig_task_manager.task_common import DependencePackagesStatus, \
    TaskDependenceStatus
from plugin.codemig.codemig_task_manager.arch_missing_process import detect_arch, group_files

LOGGER = logger.init_log('codemig')
BATCH_SIZE = 1000

UPDATE_DEPENDENCE_TASK_STATUS = ("UPDATE codemig_tasks SET dependence_status = ?, fail_reason = ?"
                                 " WHERE task_id = ?")

INSERT_CODEMIG_TASK_DEPENDENCE_SQL = ("INSERT INTO codemig_task_dependence "
                                      "(user_id, task_id, dir_id, dependence_id) VALUES (?, ?, ?, ?)")


def create_changes_and_copy_file(file_solvers_result, file_path):
    file_type_and_changes: defaultdict[MigrationClass, list] = defaultdict(list)
    for solver, result_lit in file_solvers_result.items():
        if not result_lit:
            continue
        change_list, _ = result_lit
        if not change_list:
            continue
        file_type = solver.migration_class()
        insert_values = create_insert_values(file_path, solver, change_list)
        file_type_and_changes[file_type].extend(insert_values)
    return file_type_and_changes


def create_insert_values(file_path, solver, change_list):
    file_type = solver.migration_class()
    if file_type == MigrationClass.TEXT:
        solver_type = solver.get_solver_type()
        append_or_replace = solver.append_or_replace()
        return [(file_path, solver_type, append_or_replace, start_lineno, end_lineno,
                 suggestion, code_too_long, mycode)
                for start_lineno, end_lineno, suggestion, code_too_long, mycode in change_list]
    if file_type == MigrationClass.DYNAMIC_LINK_LIBRARY:
        return [(file_path, arch, suggestion) for arch, suggestion in change_list]
    return None


def save_changes_to_database(pkg_name, version, target_dir, my_files, text_file_changes,
                             lib_file_changes, missing_file_data, missing_dir):
    """
    保存变更到数据库（使用 ORM，保持事务性）

    Args:
        my_files: 文件列表，每个元素是 (dependence_id, type, file_path) 元组
        text_file_changes: 文本文件变更列表
        lib_file_changes: 库文件变更列表
        missing_file_data: 缺失文件数据字典，key是文件路径，value是架构路径列表
        dependence_id: 依赖ID

    Returns:
        bool: 成功返回 False，失败返回 True
    """
    file_path_to_file_id = {}
    try:
        with db_session_scope() as session:
            dependence_id = DependencePackages.record_package(pkg_name, version, target_dir,
                                                              DependencePackagesStatus.SUCCESS.value,
                                                              None)
            if not dependence_id:
                return False, f"存储 {pkg_name}-{version} 失败!", None
            # 第一部分：文件级数据存储
            # 插入 file_dependence 记录
            for my_file in my_files:
                file_type, file_path = my_file
                file_dep = FileDependence(
                    dependence_id=dependence_id,
                    type=file_type,
                    file_path=file_path
                )
                session.add(file_dep)
                session.flush()  # 获取 file_id
                file_path_to_file_id[my_file] = file_dep.file_id

            # 准备并插入文本文件变更
            prepared_text_file_changes = create_prepared_text_changes(file_path_to_file_id,
                                                                      text_file_changes)
            for change in prepared_text_file_changes:
                (file_id, solver_type, append_or_replace, start_lineno, end_lineno,
                 suggestion, code_too_long, mycode) = change
                text_suggestion = FileDependenceSuggestion(
                    dependence_id=dependence_id,
                    file_id=file_id,
                    type=solver_type,
                    append_or_replace=append_or_replace,
                    start_line_number=start_lineno,
                    end_line_number=end_lineno,
                    suggestion=suggestion,
                    code_too_long=code_too_long,
                    code=mycode
                )
                session.add(text_suggestion)

            # 准备并插入库文件变更
            prepared_lib_file_changes = create_prepared_lib_changes(file_path_to_file_id,
                                                                    lib_file_changes)
            for change in prepared_lib_file_changes:
                (file_id, support_architecture, suggestion) = change
                lib_suggestion = SoftwareDependenceSuggestion(
                    dependence_id=dependence_id,
                    file_id=file_id,
                    support_architecture=support_architecture,
                    suggestion=suggestion
                )
                session.add(lib_suggestion)

            # 第二部分：目录级数据存储
            if missing_file_data:
                for missing_path_key, arch_paths in missing_file_data.items():
                    # 插入主表 file_dependence
                    missing_file_dep = FileDependence(
                        dependence_id=dependence_id,
                        type=MigrationClass.MISSING_ARCH_FILE.value,
                        file_path=missing_path_key
                    )
                    session.add(missing_file_dep)
                    session.flush()  # 获取 file_id
                    parent_file_id = missing_file_dep.file_id

                    # 批量插入子表 dependence_existing_architecture
                    for arch_path in arch_paths:
                        arch_record = DependenceExistingArchitecture(
                            dependence_id=dependence_id,
                            file_id=parent_file_id,
                            architecture_path=arch_path
                        )
                        session.add(arch_record)

            # 第二部分：目录级数据存储
            if missing_dir:
                for missing_path_key, arch_paths in missing_dir.items():
                    # 插入主表 file_dependence
                    missing_file_dep = FileDependence(
                        dependence_id=dependence_id,
                        type=MigrationClass.MISSING_ARCH_FILE.value,
                        file_path=missing_path_key
                    )
                    session.add(missing_file_dep)
                    session.flush()  # 获取 file_id
                    parent_file_id = missing_file_dep.file_id

                    # 批量插入子表 dependence_existing_architecture
                    for arch_path in arch_paths:
                        arch_record = DependenceExistingArchitecture(
                            dependence_id=dependence_id,
                            file_id=parent_file_id,
                            architecture_path=arch_path,
                            type=1
                        )
                        session.add(arch_record)

            # 事务会在 with 块结束时自动提交，如果出现异常会自动回滚
            return True, None, dependence_id

    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, "Database operation failed", None


def create_prepared_text_changes(file_path_to_file_id, text_file_changes):
    prepared_text_file_changes = []
    for change in text_file_changes:
        (file_path, solver_type, append_or_replace, start_lineno, end_lineno,
         suggestion, code_too_long, mycode) = change
        lookup_key = (MigrationClass.TEXT.value, file_path)
        if lookup_key not in file_path_to_file_id:
            raise DatabaseException(f"Error finding file Id with key: {lookup_key}")
        file_id = file_path_to_file_id[lookup_key]
        prepared_text_file_changes.append((file_id, solver_type, append_or_replace,
                                           start_lineno, end_lineno, suggestion,
                                           code_too_long.value, mycode))
    return prepared_text_file_changes


def create_prepared_lib_changes(file_path_to_file_id, lib_file_changes):
    prepared_lib_file_changes = []
    for change in lib_file_changes:
        (file_path, support_architecture, suggestion) = change
        lookup_key = (MigrationClass.DYNAMIC_LINK_LIBRARY.value, file_path)
        if lookup_key not in file_path_to_file_id:
            raise DatabaseException(f"Error finding file Id with key: {lookup_key}")
        file_id = file_path_to_file_id[lookup_key]
        prepared_lib_file_changes.append((file_id, support_architecture, suggestion))
    return prepared_lib_file_changes


def insert_task_dependence_update_status(task_id, dependence_ids):
    """
    插入任务依赖关系并更新任务状态

    Args:
        task_id: 任务ID
        dependence_ids: 依赖ID列表，格式为 [(dir_id, dependence_id), ...]

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        with db_session_scope() as session:
            # 先查询 user_id
            task = session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).first()

            if not task:
                LOGGER.error(f"未找到对应的任务，任务可能已删除task_id:{task_id}")
                return False

            user_id = task.user_id

            # 批量插入依赖关系
            insert_objects = [
                CodemigTaskDependence(
                    user_id=user_id,
                    task_id=task_id,
                    dir_id=dir_id,
                    dependence_id=dependence_id
                )
                for (dir_id, dependence_id) in dependence_ids
            ]
            session.bulk_save_objects(insert_objects)

            # 更新任务依赖状态
            session.query(CodemigTasks).filter(
                CodemigTasks.task_id == task_id
            ).update({
                CodemigTasks.dependence_status: TaskDependenceStatus.SUCCESS.value,
                CodemigTasks.fail_reason: None
            })

            # 事务会在 db_session_scope 退出时自动提交
            LOGGER.info("插入成功")
            return True

    except (DatabaseException, OSError, IOError) as err:
        # 数据库操作异常，记录错误并返回失败
        LOGGER.error(f"依赖任务插入数据库失败:{task_id}: {str(err)}")
        return False


def process_extracted_dir(extract_path):
    return DirSolver.solve(extract_path)


def scan_packages(pkg_name, version, target_dir, pkg_spec):
    # 记录有内容的文件
    my_files, text_file_changes, lib_file_changes, missing_file = [], [], [], {}
    skip_dir, missing_dir = [], {}
    for root, dirs, files in os.walk(target_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in ['.git', '.github']]
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
            file_solvers_result = CodemigProcessor.process_file(file_path)
            file_type_and_changes = create_changes_and_copy_file(file_solvers_result,
                                                                 file_path)
            useful = False
            for file_type, changes in file_type_and_changes.items():
                if not changes:
                    continue
                useful = True
                my_files.append((file_type.value, file_path))
                if file_type == MigrationClass.TEXT:
                    text_file_changes.extend(changes)
                elif file_type == MigrationClass.DYNAMIC_LINK_LIBRARY:
                    lib_file_changes.extend(changes)

    # 目录级处理
    # missing_file_data = process_extracted_dir(target_dir)

    status, msg, dependence_id = save_changes_to_database(pkg_name, version, target_dir, my_files,
                                                          text_file_changes, lib_file_changes,
                                                          missing_file, missing_dir)
    if not status:
        return False, msg, dependence_id
    return True, f"安装 {pkg_spec} 成功!", dependence_id


def record_fail_package_info(pkg_name, version, target_dir, error_msg):
    dependence_id = DependencePackages.record_package(pkg_name, version, target_dir,
                                                      DependencePackagesStatus.FAILED.value,
                                                      error_msg)
    if not dependence_id:
        return None
    return dependence_id
