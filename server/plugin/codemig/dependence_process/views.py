import sys
import os

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.response.response_code import ResponseCode
from common.db.SQLOperation import db_session_scope, DatabaseException
from plugin.codemig.dependence_process.models import CodemigTaskDependence, FileDependence, DependenceTask
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from sqlalchemy import func, case

LOGGER = logger.init_log('codemig')






def query_dependence_sql(user_name, task_id, user_id):
    LOGGER.info(f"Querying the dependence for user {user_name} task_id {task_id}.")
    try:
        with db_session_scope() as session:
            # 查询任务配置信息
            task = session.query(CodemigTasks).filter(
                CodemigTasks.user_id == user_id,
                CodemigTasks.task_id == task_id
            ).first()
            
            if not task:
                return False, None, "task not found"
            
            if task.is_scan_dependence == 0:
                return False, None, "task didn't scan dependence"
            
            # 构建任务信息元组，保持与原始格式一致
            task_info = (
                task.is_scan_dependence,
                task.python_interpreter,
                task.python_image_source,
                task.go_install_path,
                task.go_environment,
                task.dependence_status,
                task.fail_reason
            )
            
            # 如果依赖状态未完成（< 2），查询依赖任务统计信息
            if task.dependence_status < 2:
                # 查询总数量和未完成数量（status=0）
                count_result = session.query(
                    func.count(DependenceTask.task_id).label('total_count'),
                    func.count(case((DependenceTask.status == 0, 1), else_=None)).label('unfinished_count')
                ).filter(
                    DependenceTask.task_id == task_id
                ).first()
                
                total_count = count_result.total_count or 0
                unfinished_count = count_result.unfinished_count or 0
                return True, task_info, {'total': total_count, 'processing': unfinished_count}
            
            return True, task_info, None
    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f'Database operation failed: {err}')
        return False, None, 'Database Error'

def query_dependence_sql_summary(user_name, task_id, user_id):
    LOGGER.info(f"Querying the dependence for user {user_name} task_id {task_id}.")
    try:
        with db_session_scope() as session:
            # 查询任务配置信息
            task = session.query(CodemigTasks).filter(
                CodemigTasks.user_id == user_id,
                CodemigTasks.task_id == task_id
            ).first()
            
            if not task:
                return False, None, "task not found"
            
            if task.is_scan_dependence == 0:
                return False, None, "task didn't scan dependence"
            
            # 查询总数量和未完成数量（status=0）
            count_result = session.query(
                func.count(DependenceTask.task_id).label('total_count'),
                func.count(case((DependenceTask.status == 0, 1), else_=None)).label('unfinished_count')
            ).filter(
                DependenceTask.task_id == task_id
            ).first()
            
            total_count = count_result.total_count or 0
            unfinished_count = count_result.unfinished_count or 0
            return True, total_count, None

    except (DatabaseException, OSError, IOError) as err:
        LOGGER.error(f'Database operation failed: {err}')
        return False, None, 'Database Error'

def create_dependence_data(user_name, task_info, task_id, user_id):
    if task_info[5] == 3:
        return {
            "task_info": task_info[1:],
            "success_dependence_data": [],
            "fail_dependence_data": []
        }
    
    success_dependence_data = []
    fail_dependence_data = []
    
    # 使用单个数据库会话执行所有查询，避免多次打开连接
    try:
        with db_session_scope() as session:
            # 查询依赖包信息
            dependence_rows = CodemigTaskDependence.get_dependencies_by_task_id(task_id, session=session)
            if dependence_rows is None:
                dependence_rows = []
            
            if not dependence_rows:
                return {
                    "task_info": task_info[1:],
                    "success_dependence_data": success_dependence_data,
                    "fail_dependence_data": fail_dependence_data
                }
            
            # 提取成功状态的依赖ID列表
            dependence_ids = [dependence_id[0] for dependence_id in dependence_rows if dependence_id[3] == 1]
            
            # 查询汇总信息（使用同一个会话）
            summary_rows = FileDependence.get_summary_by_dependence_ids(dependence_ids, session=session)
            if summary_rows is None:
                summary_rows = []
    except (DatabaseException, OSError, IOError) as e:
        LOGGER.error(f'Error creating dependence data: {e}')
        return {
            "task_info": task_info[1:],
            "success_dependence_data": success_dependence_data,
            "fail_dependence_data": fail_dependence_data
        }
    for i, row in enumerate(dependence_rows, start=1):
        index, pkg, version, status, reason = row
        if status == 1:
            for summary_id, num_changes, num_files in summary_rows:
                if index == summary_id:
                    success_dependence_data.append(
                        (i, index, pkg, version, '', status, reason, task_id, '',
                         int(num_changes) + int(num_files)))
                    break
            else:
                success_dependence_data.append(
                    (i, index, pkg, version, '', status, reason, task_id, '', 0))
        else:
            fail_dependence_data.append((i, index, pkg, version, '', status, reason, task_id, '', 0))
    # 按问题数量降序排序（问题多的排前面）
    success_dependence_data.sort(key=lambda x: x[9], reverse=True)
    return {
        "task_info": task_info[1:],
        "success_dependence_data": success_dependence_data,
        "fail_dependence_data": fail_dependence_data
    }


def query_dependence(user_name, task_id, user_id):
    status, task_info, msg = query_dependence_sql(user_name, task_id, user_id)
    if not status:
        return {"code": -1, "msg": msg}
    if msg:
        return {"code": 0, "msg": ResponseCode.OK,
                "data": {"task_info": task_info[1:], "count": msg}}

    return {"code": 0, "msg": ResponseCode.OK,
            "data": create_dependence_data(user_name, task_info, task_id, user_id)}


def query_dependence_summary(user_name, task_id, user_id):
    status, total, msg = query_dependence_sql_summary(user_name, task_id, user_id)
    if not status:
        return {"code": -1, "msg": msg}
    return {"code": 0, "msg": ResponseCode.OK,
                "data": {"count": total}}

