import sys
import os
import shutil
from pathlib import Path

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.db.SQLOperation import db_session_scope, DatabaseException
from common.public.public import get_codemig_data_path
from common.public import logger
from plugin.codemig.codemig_dir_manager.codemig_dir_processor import _remove_migrate_volumes
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage
from plugin.codemig.codemig_task_manager.models import CodemigTasks, CodemigTaskDirectory
from plugin.codemig.codemig_task_manager.task_common import TaskStatus
from plugin.codemig.dependence_process.models import CodemigTaskDependence

#  remove 文件
LOGGER = logger.init_log('codemig')


def permanent_delete():
    LOGGER.info("Execute hard deletion task.")
    # 删除数据库中数据
    to_remove_dir = None
    nolink_dir = None
    try:
        with db_session_scope() as session:
            # 使用 ORM 方法查询已删除的目录
            to_remove_dir = CodemigDirectoryStorage.get_removed_directories(session=session)
            # 使用 ORM 方法查询未关联任务的目录
            nolink_dir = CodemigDirectoryStorage.get_no_link_directories(session=session)
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
        to_remove_dir = None
        nolink_dir = None
    # 删除文件
    LOGGER.info("Delete the marked file.")
    # 处理 None 值的情况
    if to_remove_dir is None:
        to_remove_dir = []
    if nolink_dir is None:
        nolink_dir = []
    to_remove_dir = to_remove_dir + nolink_dir
    if to_remove_dir:
        base_path = Path(get_codemig_data_path())
        delete_file_path = [base_path / user_name / str(dir_id) for dir_id, user_name in
                            to_remove_dir if user_name]
        for folder_path in delete_file_path:
            try:
                if folder_path.exists():
                    shutil.rmtree(folder_path)
            except OSError as e:
                LOGGER.warning(f"[cleanup] 删除目录 {folder_path} 失败（忽略）: {e}")
        # 同步清理一键迁移的 docker 命名卷（best-effort，失败不阻塞）
        for dir_id, user_name in to_remove_dir:
            if user_name:
                _remove_migrate_volumes(user_name, dir_id)
        no_user = [str(dir_id) for dir_id, user_name in to_remove_dir if user_name is None]
        for user_dir in os.listdir(base_path):
            deleted = []
            for dir_id in no_user:
                test_delete = base_path / user_dir / dir_id
                try:
                    if test_delete.exists():
                        shutil.rmtree(test_delete)
                        deleted.append(dir_id)
                except OSError as e:
                    LOGGER.warning(f"[cleanup] 删除目录 {test_delete} 失败（忽略）: {e}")
            no_user = list(set(no_user) - set(deleted))
    LOGGER.info("File deleted successfully")
    
    # 准备要删除的目录ID列表
    dir_ids = None
    if nolink_dir:
        dir_ids = [dir_id for dir_id, _ in nolink_dir]
    
    try:
        with db_session_scope() as session:
            # 查询已删除的任务ID（status = 4）
            deleted_tasks = session.query(CodemigTasks.task_id).filter(
                CodemigTasks.status == TaskStatus.DELETED.value
            ).all()
            task_ids = [task_id[0] for task_id in deleted_tasks]
            
            # 删除任务为空时结束
            if task_ids:
                # 扫描结果数据已随每个目录的独立 sqlcipher 库文件一起物理删除（见上方文件删除），
                # 此处只需清理主库的关联记录。

                # 删除 codemig_task_directory（使用 ORM）
                session.query(CodemigTaskDirectory).filter(
                    CodemigTaskDirectory.task_id.in_(task_ids)
                ).delete(synchronize_session=False)
                
                # 删除 codemig_task_dependence（使用 ORM）
                session.query(CodemigTaskDependence).filter(
                    CodemigTaskDependence.task_id.in_(task_ids)
                ).delete(synchronize_session=False)
                
                # 删除 codemig_tasks（使用 ORM）
                session.query(CodemigTasks).filter(
                    CodemigTasks.task_id.in_(task_ids)
                ).delete(synchronize_session=False)
                
                # 删除已标记为删除的目录（使用 ORM）
                session.query(CodemigDirectoryStorage).filter(
                    CodemigDirectoryStorage.has_removed == 1
                ).delete(synchronize_session=False)
            
            # 删除未关联的目录（使用 ORM）
            if dir_ids:
                session.query(CodemigDirectoryStorage).filter(
                    CodemigDirectoryStorage.dir_id.in_(dir_ids)
                ).delete(synchronize_session=False)
            
            # 事务会在 db_session_scope 退出时自动提交
            LOGGER.info("Database deletion completed successfully.")

    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)


def init_codemig_task():
    try:
        with db_session_scope() as session:
            tasks = session.query(CodemigTasks.task_id).filter(
                CodemigTasks.status == TaskStatus.PROCESSING.value
            ).all()

            for task in tasks:
                task_id = task[0]
                result = session.query(CodemigTasks).filter(
                    CodemigTasks.task_id == task_id
                ).update({
                    CodemigTasks.status: TaskStatus.FAILED.value
                })

                if result == 0:
                    LOGGER.warning(f"Task {task_id} not found when updating status")

    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error("Database operation failed: %s", err)
