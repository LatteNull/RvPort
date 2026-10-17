import time
from threading import Lock


class UserSessionCache:
    _instance = None  # 用于保存单例实例
    _lock = Lock()  # 线程锁，确保线程安全
    _cache = {}  # 静态缓存存储

    def __new__(cls, *args, **kwargs):
        """
        重写 __new__ 方法，实现单例模式
        """
        if not cls._instance:
            with cls._lock:  # 确保多线程安全
                if not cls._instance:
                    cls._instance = super(UserSessionCache, cls).__new__(cls)
        return cls._instance


    @classmethod
    def set_user_session(cls, user_id, token, ip = None, role=0):
        """设置用户会话"""
        with cls._lock:
            cls._cache[user_id] = {'token': token, 'last_time': int(time.time()), 'ip': ip, 'role':role}

    @classmethod
    def delete_user_session(cls, user_id):
        """删除用户会话"""
        with cls._lock:
            cls._cache.pop(user_id, None)

    @classmethod
    def update_user_last_time(cls, user_id, timestamp):
        """更新用户的最后访问时间"""
        with cls._lock:
            if user_id in UserSessionCache._cache:
                cls._cache[user_id]['last_time'] = int(timestamp)

    @classmethod
    def get_user_last_time(cls, user_id):
        """获取用户的最后访问时间"""
        with cls._lock:
            user_data = cls._cache.get(user_id)
            return user_data['last_time'] if user_data else None

    @classmethod
    def get_user_token(cls, user_id):
        """获取用户的 token"""
        with cls._lock:
            user_data = cls._cache.get(user_id)
            return user_data['token'] if user_data else None

    @classmethod
    def get_online_users(cls, exp_time):
        """
        获取在线用户列表，过滤条件为 last_time >= exp_time
        """
        with cls._lock:
            return [user_id for user_id, data in cls._cache.items() if
                    data['last_time'] >= exp_time and data['role'] == 0]

    @classmethod
    def get_online_users_all_roles(cls, exp_time):
        """
        获取在线用户列表（含管理员与普通用户），过滤条件为 last_time >= exp_time
        """
        with cls._lock:
            return [user_id for user_id, data in cls._cache.items() if
                    data['last_time'] >= exp_time]

    @classmethod
    def kick_ip(cls, ip):
        with cls._lock:
            # 找到所有匹配IP的用户ID
            users_to_remove = [
                user_id for user_id, data in cls._cache.items()
                if data.get('ip') == ip
            ]

            # 批量移除
            for user_id in users_to_remove:
                cls._cache.pop(user_id, None)

            removed_count = len(users_to_remove)

            return removed_count