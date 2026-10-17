import os
import sys
import multiprocessing
import time
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.append(os.path.dirname(__file__))
from codemig_bp.bp import codemig_bp
from codemig_task_manager.request_processor import delete_user
from codemig_task_manager.codemig_backend_task import permanent_delete
from codemig_task_manager.codemig_backend_task import init_codemig_task
from dependence_process.dependence_task import dep_process
from codemig_config.config import ConfigManager

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public.public import get_codemig_data_path

func_map = {
    "codemig_task": {
        'remove_for_user': delete_user,
    }
}


def get_func_map():
    return func_map


def get_blueprint():
    return codemig_bp


def init_data_directory():
    codemig_data_path = get_codemig_data_path()
    if not os.path.exists(codemig_data_path):
        os.makedirs(codemig_data_path)


init_data_directory()

ENABLE_CRON_PERMANENT_DELETE = True


def start_cron_permanent_delete():
    scheduler = BackgroundScheduler()
    scheduler.add_job(permanent_delete, 'cron', hour=18)  # 每天 4:00 AM 执行一次数据库检查删除
    scheduler.start()


def backend_process():
    def run_tasks():
        scheduler = None
        # 调用后台定时清理任务
        if ENABLE_CRON_PERMANENT_DELETE:
            start_cron_permanent_delete()
        # 调用 依赖库处理后台任务
        try:
            while True:
                time.sleep(120)  # 每分钟检查一次
        except KeyboardInterrupt:
            if scheduler:
                scheduler.shutdown()

    init_codemig_task()
    if ConfigManager.get_enable_dependence():
        dep_process()

    if ENABLE_CRON_PERMANENT_DELETE:
        process = multiprocessing.Process(target=run_tasks, name="CodemigBackend")
        process.daemon = True
        process.start()


backend_process()
