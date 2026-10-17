import os
import sys
from portalocker import Lock, LockFlags, AlreadyLocked, LockException
from contextlib import contextmanager

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.public.public import get_codemig_data_path
from plugin.codemig.codemig_task_manager.query_processor import query_task_id_by_dir_id

LOGGER = logger.init_log('codemig')

def get_task_lock_file_path(user_name, dir_id, task_id=None):
    """
    获取任务相关的锁文件路径
    同一任务的所有接口操作使用同一个锁文件，确保串行执行
    Args:
        user_name: 用户名
        dir_id: 目录ID
        task_id: 任务ID（如果提供，则使用任务级别的锁；否则尝试从 dir_id 获取 task_id）
    Returns:
        str: 锁文件路径
    """
    base_path = get_codemig_data_path()
    if task_id:
        # 使用任务ID作为锁文件名，确保同一任务的所有操作使用同一个锁
        lock_file = os.path.join(base_path, user_name, str(dir_id), f"task_{task_id}.lock")
    else:
        # 如果没有 task_id，尝试从 dir_id 获取
        _, task_id_from_dir = query_task_id_by_dir_id(dir_id)
        if task_id_from_dir:
            lock_file = os.path.join(base_path, user_name, str(dir_id), f"task_{task_id_from_dir}.lock")
        else:
            # 如果无法获取 task_id，使用目录级别的锁
            lock_file = os.path.join(base_path, user_name, str(dir_id), "dir.lock")
    return lock_file

@contextmanager
def task_file_lock(user_name, dir_id, task_id=None, blocking=True, timeout=None):
    """
    任务文件锁上下文管理器，确保同一任务的操作串行执行。
    Args:
        user_name: 用户名
        dir_id: 目录ID
        task_id: 任务ID（优先使用）
        blocking: 是否阻塞等待锁
        timeout: 超时时间（秒），blocking=False 时强制为 0    
    Yields:
        None
    Raises:
        RuntimeError: 无法获取锁
    """
    lock_file_path = get_task_lock_file_path(user_name, dir_id, task_id)
    os.makedirs(os.path.dirname(lock_file_path), exist_ok=True)

    actual_timeout = 0 if not blocking else timeout
    fail_when_locked = not blocking

    try:
        with Lock(
            filename=lock_file_path,
            mode='a',
            timeout=actual_timeout,
            fail_when_locked=fail_when_locked,
            flags=LockFlags.EXCLUSIVE | LockFlags.NON_BLOCKING
        ):
            yield
    except AlreadyLocked:
        # 非阻塞模式下锁被占用，或超时
        msg = f"Task is busy: {lock_file_path} (blocking={blocking}, timeout={actual_timeout})"
        LOGGER.warning(msg)
        raise RuntimeError("Other Modify Task is running, please try again later.") from None
    except LockException as e:
        msg = f"Lock system error on {lock_file_path}: {e}"
        LOGGER.error(msg)
        raise RuntimeError("Failed to acquire system lock") from e
    except OSError as e:
        msg = f"OS error when locking {lock_file_path}: {e}"
        LOGGER.error(msg)
        raise RuntimeError("OS-level lock failure") from e
    except (ValueError, TypeError) as e:
        LOGGER.critical(f"Unexpected error in lock acquisition: {e}", exc_info=True)
        raise RuntimeError("Unexpected lock error") from e

