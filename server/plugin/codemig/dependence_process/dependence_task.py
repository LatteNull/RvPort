import sys

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.db.SQLOperation import db_session_scope, DatabaseException
from sqlalchemy import and_
from plugin.codemig.dependence_process.models import DependenceTask
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.codemig_task_manager.task_common import TaskDependenceStatus
from plugin.codemig.dependence_process.python_dependence_process import PythonDependenceProcessor
from plugin.codemig.dependence_process.go_dependence_process import GoDependenceProcessor
from plugin.codemig.dependence_process.dependence_info import DependenceInfo
from plugin.codemig.dependence_process.go_mod_file import parse_go_dep
from plugin.codemig.dependence_process.req_file import parse_python_req

background_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="Dependence")

LOGGER = logger.init_log('codemig')


def submit_dependence_task(source_path, dep: DependenceInfo, dir_id, task_id, user_id):
    if dep.scan == 0:
        return
    # 依赖包处理
    if dep.lang == "python":
        status, msg, packages = parse_python_req(source_path, task_id, user_id, dir_id)
        if not status:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.FAILED.value,
                                                  "Parse go mod file failed")
        elif msg == 0:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.SUCCESS.value, None)
        else:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.PROCESSING.value,
                                                  None)
            insert_dep_task(task_id, dep, packages)

    elif dep.lang == "go":
        status, msg, packages = parse_go_dep(source_path, task_id, user_id, dir_id)
        if not status:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.FAILED.value,
                                                  "Parse go mod file failed")
        elif msg == 0:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.SUCCESS.value, None)
        else:
            CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.PROCESSING.value,
                                                  None)
            insert_dep_task(task_id, dep, packages)
    else:
        CodemigTasks.update_dependence_status(task_id, TaskDependenceStatus.FAILED.value,
                                              "只支持python和go依赖包")


task_list = set()


def insert_dep_task(task_id, dep, packages):
    to_process = []
    for item in packages:
        # packages 可能是4个元素 (task_id, dir_id, pkg, version) 或5个元素 (task_id, dir_id, pkg, version, local_path)
        _, dir_id, pkg, version = item[:4]
        local_path = item[4] if len(item) > 4 else ''
        to_process.append((dir_id, pkg, version, local_path, 0, None))
    if len(to_process) == 0:
        return
    if dep.lang == "python":
        processor = PythonDependenceProcessor(
            config=(dep.python, dep.python_config),
            to_process=to_process,
            task_id=task_id
        )
        background_executor.submit(processor.process)

    elif dep.lang == "go":
        processor = GoDependenceProcessor(
            config=(dep.go, dep.go_config),
            to_process=to_process,
            task_id=task_id
        )
        background_executor.submit(processor.process)


def init_dep_task():
    tasks = None
    try:
        with db_session_scope() as session:
            # 使用 ORM 查询需要处理的依赖任务
            task_objects = session.query(CodemigTasks).filter(
                and_(
                    CodemigTasks.is_scan_dependence == 1,
                    CodemigTasks.dependence_status == 1
                )
            ).order_by(CodemigTasks.task_id).all()

            # 转换为元组列表，保持与原始格式一致
            tasks = [
                (
                    task.task_id,
                    task.python_interpreter,
                    task.python_image_source,
                    task.go_install_path,
                    task.go_environment
                )
                for task in task_objects
            ]
    except (DatabaseException, OSError, IOError) as e:
        LOGGER.error(f"get dep task from db error:{str(e)}")
        tasks = None

    # 检查 tasks 是否为 None 或空
    if not tasks:
        LOGGER.info("No tasks to process")
        return

    for task in tasks:
        # 使用 ORM 查询依赖任务包信息
        pkgs = DependenceTask.get_packages_by_task_ids([task[0]])
        if pkgs is None:
            continue
        task_id, python, python_config, go, go_config = task
        to_process = []
        for index, dir_id, pkg, version, local_path, status, dep_id in pkgs:
            to_process.append((dir_id, pkg, version, local_path, status, dep_id))
        if python:
            processor = PythonDependenceProcessor(
                config=(python, python_config),
                to_process=to_process,
                task_id=task_id
            )
            background_executor.submit(processor.process)

        elif go:
            processor = GoDependenceProcessor(
                config=(go, go_config),
                to_process=to_process,
                task_id=task_id
            )
            background_executor.submit(processor.process)


def init_task():
    time.sleep(10)
    init_dep_task()


def dep_process():
    try:
        init_dep_task_thread = threading.Thread(target=init_task)
        init_dep_task_thread.start()
    except Exception as e:
        LOGGER.error(f"running dependence task error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    init_dep_task()
