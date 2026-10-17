import sys
import time
import os

from concurrent.futures.thread import ThreadPoolExecutor

from multiprocessing import Process, Lock

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from framework.user_manager.user_db import UserManager

LOGGER = logger.init_log('usermanager')
background_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix='user_session')


class LogoutCache:
    _cache = {}
    lock = Lock()

    @classmethod
    def update(cls, user_id, now):
        with cls.lock:
            cls._cache[user_id] = now

    @classmethod
    def pop(cls, user_id):
        with cls.lock:
            now = cls._cache.pop(user_id)
            return now


def _update_last_logout(user_id, now):
    try_num = 10
    sleep_time = 0.5
    while try_num > 0:
        now = LogoutCache.pop(user_id)
        if not now:
            break
        status = UserManager.update(user_id, last_logout=now)
        if not status:
            LOGGER.warning(f'update user last logout failed, try again {try_num} times later.')
            time.sleep(sleep_time)
            try_num -= 1
            continue
        try_num = 0


def refresh_last_logout(user_id, now):
    LogoutCache.update(user_id, int(now))
    try:
        background_executor.submit(_update_last_logout, user_id, int(now))
    except RuntimeError as e:
        if "cannot schedule new futures" in str(e):
            LOGGER.error("线程池已关闭")
