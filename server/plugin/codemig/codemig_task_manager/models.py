"""
Codemig 任务管理 ORM 模型
对应数据库表: codemig_tasks, codemig_task_directory, codemig_task_directory_file
"""
import os
import sys

from datetime import datetime
from common.db.SQLOperation import Base, DatabaseException, db_session_scope
from common.public import logger
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint

LOGGER = logger.init_log('codemig')

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from plugin.codemig.codemig_task_manager.task_common import TaskStatus


class CodemigTasks(Base):
    """
    任务 ORM 类
    对应数据库表: codemig_tasks
    status: 0 -> created, 1 -> processing, 2 -> success, 3 -> failed, 4 -> deleted
    dependence_status: 0 -> created, 1 -> processing, 2 -> success, 3 -> failed
    is_scan_dependence: 0 -> no, 1 -> yes
    """
    __tablename__ = 'codemig_tasks'
    __table_args__ = (
        CheckConstraint('is_scan_dependence IN (0, 1)', name='ck_codemig_tasks_is_scan_dependence'),
        CheckConstraint('LENGTH(task_name) <= 128', name='ck_codemig_tasks_task_name_length'),
        {'extend_existing': True}
    )

    user_id = Column(String(64), nullable=False)
    task_id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(Text, nullable=False)
    status = Column(Integer, nullable=False, default=0)
    is_scan_dependence = Column(Integer, nullable=False, default=0)
    dependence_status = Column(Integer, nullable=False, default=0)
    fail_reason = Column(Text)
    python_interpreter = Column(Text)
    python_image_source = Column(Text)
    go_install_path = Column(Text)
    go_environment = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def update_dependence_status(task_id, dependence_status, fail_reason):
        """
        更新任务的依赖状态
        
        Args:
            task_id: 任务ID
            dependence_status: 依赖状态值（0 -> created, 1 -> processing, 2 -> success, 3 -> failed）
            fail_reason: 失败原因（可选）
            
        Returns:
            bool: 成功返回 False，失败返回 True（保持与原始函数返回值一致）
        """
        try:
            with db_session_scope() as session:
                result = session.query(CodemigTasks).filter(
                    CodemigTasks.task_id == task_id
                ).update({
                    CodemigTasks.dependence_status: dependence_status,
                    CodemigTasks.fail_reason: fail_reason
                })
                
                if result == 0:
                    LOGGER.warning(f"Task {task_id} not found when updating dependence status")
                
                return False  # 成功返回 False
                
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"Database operation failed: {e}")
            return True  # 失败返回 True

    @staticmethod
    def get_task_name(user_id, task_id):
        """
        根据任务ID查询任务名称
        
        Args:
            task_id: 任务ID
            
        Returns:
            str or None: 任务名称，如果未找到或发生错误则返回 None
        """
        try:
            with db_session_scope() as session:
                task = session.query(CodemigTasks).filter(
                    CodemigTasks.task_id == task_id,
                    CodemigTasks.user_id == user_id
                ).first()
                
                if not task:
                    LOGGER.warning(f"Task not found: task_id={task_id}")
                    return None
                
                return task.task_name
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return None

    @staticmethod
    def update_task_status(task_id, task_status):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            task_status: 任务状态（TaskStatus 枚举值）
            
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        LOGGER.info(f"Updating the task status to {task_status}.")
        try:
            with db_session_scope() as session:
                # 使用 ORM 更新任务状态
                result = session.query(CodemigTasks).filter(
                    CodemigTasks.task_id == task_id
                ).update({
                    CodemigTasks.status: task_status.value
                })
                
                if result == 0:
                    LOGGER.warning(f"Task {task_id} not found when updating status")
                
                # 事务会在 db_session_scope 退出时自动提交
                return True
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return False


class CodemigTaskDirectory(Base):
    """
    任务目录关联 ORM 类
    对应数据库表: codemig_task_directory
    """
    __tablename__ = 'codemig_task_directory'
    __table_args__ = {'extend_existing': True}

    task_id = Column(Integer, ForeignKey('codemig_tasks.task_id'), nullable=False)
    dir_id = Column(Integer, ForeignKey('codemig_directory_storage.dir_id'), nullable=False)
    task_dir_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now)




