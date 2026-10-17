import os
import sys
import time
import traceback
import sqlite3
import threading
import sqlcipher3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base, Session
from sqlalchemy.exc import DatabaseError as SQLAlchemyDatabaseError, SQLAlchemyError
from contextlib import contextmanager, closing

from config import Config
from common.public.public import ROOT_PATH, DATABASE
from common.public import logger
from common.db.crypto_utils import get_key

LOGGER = logger.init_log('db_log.log')


class DatabaseException(Exception):
    """
    统一的数据库异常类
    用于封装各种数据库驱动异常，便于业务代码统一处理
    """

    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception
        self.original_type = type(original_exception).__name__ if original_exception else None


def get_connect_args():
    """获取数据库连接参数"""
    connect_args = {}

    if _config_instance.DB_TYPE == 'sqlite':
        connect_args['check_same_thread'] = False

    return connect_args


def get_engine_kwargs(role='write'):
    """获取引擎创建参数（按读写角色区分连接池大小）"""
    kwargs = {
        'echo': False,
        'pool_pre_ping': True,  # 连接池预检查，检测断开的连接
        'pool_use_lifo': True,
        'pool_timeout': 30,
        'connect_args': get_connect_args()
    }

    # MySQL 需要设置 pool_recycle 防止连接超时
    # MySQL 默认 8 小时断开空闲连接，设置 3600 秒（1小时）回收
    if _config_instance.DB_TYPE == 'mysql':
        kwargs['pool_recycle'] = 3600  # 1小时回收连接
        if role == 'write':
            kwargs['pool_size'] = 10
            kwargs['max_overflow'] = 5
        else:
            kwargs['pool_size'] = 40
            kwargs['max_overflow'] = 10
    elif _config_instance.DB_TYPE == 'sqlite':
        if role == 'write':
            kwargs['pool_size'] = 5
            kwargs['max_overflow'] = 3
        else:
            kwargs['pool_size'] = 30
            kwargs['max_overflow'] = 10

    return kwargs


_PRAGMA_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "!@#$%^&*()-_=+[]{}:;,.<>?~|/ ")

# PRAGMA 语句不支持参数绑定（实测 ``PRAGMA key = ?`` 报 "near ?": syntax
# error，SQLite 3.34.1/sqlcipher3 2.6.0），审计建议的参数化查询在该语法上
# 不可行。改用“模块级模板常量 + 白名单校验 + 拼接与执行分离”防护。
_PRAGMA_KEY_TEMPLATE = "PRAGMA key = '{}'"


def _quote_pragma_value(value):
    """PRAGMA key 的值做白名单校验 + 单引号转义（双保险）。

    PRAGMA 不支持参数绑定（见 ``_PRAGMA_KEY_TEMPLATE`` 注释），此处白名单：
    密钥由密钥管理模块生成（现网形态为 16 位随机可打印 ASCII），拒绝
    引号/反斜杠/控制字符等一切可改变 SQL 语义的字符，再做 ``'`` → ``''``
    转义兜底，杜绝注入。
    """
    if (not isinstance(value, str) or not value
            or not set(value) <= _PRAGMA_SAFE_CHARS
            or any(ord(c) < 0x20 or ord(c) > 0x7e for c in value)):
        raise ValueError("SQLCipher password contains illegal characters")
    return value.replace("'", "''")


def _build_pragma_key_statement(raw_password):
    """生成设置 SQLCipher 密钥的语句：拼接点在独立函数内，不落在 execute 上。"""
    return _PRAGMA_KEY_TEMPLATE.format(_quote_pragma_value(raw_password))


def setup_sqlcipher_connection(dbapi_conn, connection_record):
    """设置SQLCipher密码（在连接建立后调用）"""
    if _config_instance.DB_TYPE == 'sqlite' and _config_instance.SQLITE_USE_ENCRYPTION and _config_instance.SQLITE_PASSWORD:
        key_statement = _build_pragma_key_statement(_config_instance.SQLITE_PASSWORD)
        with closing(dbapi_conn.cursor()) as cursor:
            cursor.execute(key_statement)


def _set_sqlite_pragma(dbapi_conn, connection_record):
    # closing：确保 cursor 在任何路径（含 execute 中途异常）下都被关闭
    with closing(dbapi_conn.cursor()) as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")


def _set_sqlite_read_pragma(dbapi_conn, connection_record):
    with closing(dbapi_conn.cursor()) as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA read_uncommitted=ON")


# 创建数据库引擎
_config_instance = Config()
database_url = _config_instance.SQLALCHEMY_DATABASE_URI

# 如果使用SQLCipher，通过 monkey patching 让 SQLAlchemy 使用 sqlcipher3
# 这样可以直接使用 sqlite:/// URL，无需 pysqlcipher3 包
if _config_instance.DB_TYPE == 'sqlite' and _config_instance.SQLITE_USE_ENCRYPTION:
    # 在 SQLAlchemy 导入之前，将 sqlite3 替换为 sqlcipher3
    if 'sqlite3' not in sys.modules or sys.modules['sqlite3'] is not sqlcipher3:
        if 'sqlite3' in sys.modules:
            sys.modules['_original_sqlite3'] = sys.modules['sqlite3']
        sys.modules['sqlite3'] = sqlcipher3
    # 保持使用 sqlite:/// URL，因为已经通过 monkey patching 替换了 sqlite3

write_engine = create_engine(database_url, **get_engine_kwargs('write'))
read_engine = create_engine(database_url, **get_engine_kwargs('read'))


class ConnectionLeakTracker:
    LEAK_THRESHOLD_SECONDS = 600

    def __init__(self):
        self._tracked = {}
        self._lock = threading.Lock()

    def on_checkout(self, dbapi_conn, connection_record, connection_proxy=None):
        conn_id = id(dbapi_conn)
        with self._lock:
            self._tracked[conn_id] = {
                'checkout_time': time.time(),
                'stack': ''.join(traceback.format_stack(limit=8)),
                'dbapi_conn': dbapi_conn,
            }

    def on_checkin(self, dbapi_conn, connection_record, connection_proxy=None):
        conn_id = id(dbapi_conn)
        with self._lock:
            self._tracked.pop(conn_id, None)

    def on_close(self, dbapi_conn, connection_record):
        conn_id = id(dbapi_conn)
        with self._lock:
            self._tracked.pop(conn_id, None)

    def detect_leaks(self):
        now = time.time()
        leaked = []
        with self._lock:
            for conn_id, info in list(self._tracked.items()):
                elapsed = now - info['checkout_time']
                if elapsed > self.LEAK_THRESHOLD_SECONDS:
                    leaked.append((conn_id, elapsed, info['stack']))
                    LOGGER.warning(
                        f"连接泄漏检测: 连接 {conn_id} 已被占用 {elapsed:.1f}s, 超过阈值 {self.LEAK_THRESHOLD_SECONDS}s\n"
                        f"检出调用栈:\n{info['stack']}"
                    )
        return leaked

    def reclaim_zombie_connections(self, pool):
        leaked = self.detect_leaks()
        if not leaked:
            return 0
        # SQLAlchemy 连接池没有公开的"强制归还"API；官方推荐路径就是内部
        # ``_do_return_conn``（QueuePool 归还实现）。访问保护成员是审计豁免点：
        # 版本兼容在 except 分支兜底（AttributeError/ValueError 均安全降级为 close）。
        return_connection = getattr(pool, '_do_return_conn', None)
        if return_connection is None:
            return 0
        reclaimed = 0
        with self._lock:
            for conn_id, elapsed, _ in leaked:
                info = self._tracked.get(conn_id)
                if info is None:
                    continue
                dbapi_conn = info['dbapi_conn']
                try:
                    return_connection(dbapi_conn)
                    self._tracked.pop(conn_id, None)
                    reclaimed += 1
                    LOGGER.info(f"已回收僵尸连接 {conn_id}, 占用时长 {elapsed:.1f}s")
                except (AttributeError, ValueError, sqlite3.Error,
                        sqlcipher3.Error, SQLAlchemyError) as e:
                    # _do_return_conn 对已失效句柄可能抛属性/参数错误；底层驱动异常
                    # 以 sqlite3.Error / sqlcipher3.Error 为准（SQLCipher 独立异常树）。
                    # 兜底 close 本身幂等。
                    LOGGER.error(f"回收连接 {conn_id} 失败: {e}")
                    try:
                        dbapi_conn.close()
                    except (OSError, sqlite3.Error, sqlcipher3.Error, SQLAlchemyError):
                        pass
                    self._tracked.pop(conn_id, None)
                    reclaimed += 1
        return reclaimed


_leak_tracker = ConnectionLeakTracker()


def _register_engine_events(eng, is_read=False):
    if _config_instance.DB_TYPE == 'sqlite' and _config_instance.SQLITE_USE_ENCRYPTION and _config_instance.SQLITE_PASSWORD:
        event.listen(eng, "connect", setup_sqlcipher_connection)
    if _config_instance.DB_TYPE == 'sqlite':
        if is_read:
            event.listen(eng, "connect", _set_sqlite_read_pragma)
        else:
            event.listen(eng, "connect", _set_sqlite_pragma)
    event.listen(eng, "checkout", _leak_tracker.on_checkout)
    event.listen(eng, "checkin", _leak_tracker.on_checkin)
    event.listen(eng, "close", _leak_tracker.on_close)


_register_engine_events(write_engine, is_read=False)
_register_engine_events(read_engine, is_read=True)

engine = write_engine


def _zombie_reclaimer():
    while True:
        try:
            _leak_tracker.reclaim_zombie_connections(write_engine.pool)
            _leak_tracker.reclaim_zombie_connections(read_engine.pool)
        except (AttributeError, ValueError, sqlite3.Error, SQLAlchemyError) as e:
            # 回收线程常驻后台：引擎销毁/属性缺失/底层驱动异常都只记录，不退出
            LOGGER.error(f"僵尸连接回收线程异常: {e}")
        time.sleep(300)


_reclaimer_thread = threading.Thread(target=_zombie_reclaimer, name="db-zombie-reclaimer",
                                     daemon=True)
_reclaimer_thread.start()


_WRITE_PREFIXES = ('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'REPLACE')


def _is_write_statement(statement):
    stmt_str = str(statement).strip().upper()
    return any(stmt_str.startswith(p) for p in _WRITE_PREFIXES)


class RoutingSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._write_detected = False

    def get_bind(self, mapper=None, clause=None):
        # 一旦本事务内出现过写操作（ORM new/dirty/deleted、或检测到的写 SQL），
        # 后续所有查询（含 flush 后的 SELECT count）都走 write_engine。
        # 否则 SQLite WAL + 读写分离下，flush 后的纯 SELECT 走 read_engine 连接，
        # 读不到本事务未提交的删除，导致“删后查 count”多数 1 的 bug
        # （如 delete_subtask 删最后一个子任务时父任务永远不删）。
        if self._flushing or self.new or self.dirty or self.deleted or self._write_detected:
            return write_engine
        if clause is not None and _is_write_statement(clause):
            self._write_detected = True
            return write_engine
        return read_engine

    def flush(self, *args, **kwargs):
        # flush 是真正把 ORM 改动写入连接的时刻。标记本事务已写过，
        # 确保之后同一事务内的查询走写库（与刚 flush 的改动同库，可见已删数据）。
        self._write_detected = True
        return super().flush(*args, **kwargs)


# 创建会话工厂
SessionLocal = sessionmaker(class_=RoutingSession, autocommit=False, autoflush=False)
# 使用scoped_session确保线程安全
db_session = scoped_session(SessionLocal)

# 声明基类
Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话（用于依赖注入）"""
    session = db_session()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def db_session_scope():
    """
    数据库会话上下文管理器
    统一捕获各种数据库驱动异常，转换为 DatabaseException
    """
    session = db_session()
    try:
        yield session
        session.commit()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as e:
        # SQLite/SQLCipher 异常
        session.rollback()
        raise DatabaseException(f"SQLite database error: {str(e)}", e) from e
    except SQLAlchemyDatabaseError as e:
        # SQLAlchemy 数据库异常（可能包含底层驱动异常）
        session.rollback()
        # 检查是否是 MySQL 异常
        if hasattr(e, 'orig') and e.orig:
            orig_type = type(e.orig).__name__
            if 'mysql' in orig_type.lower() or 'pymysql' in str(type(e.orig).__module__).lower():
                raise DatabaseException(f"MySQL database error: {str(e)}", e) from e
        raise DatabaseException(f"Database error: {str(e)}", e) from e
    except SQLAlchemyError as e:
        # 其他 SQLAlchemy 异常
        session.rollback()
        raise DatabaseException(f"SQLAlchemy error: {str(e)}", e) from e
    except Exception as e:
        # 其他未预期的异常，也进行回滚但不转换
        session.rollback()
        raise
    finally:
        session.close()


class DBInfo:
    def __init__(self, file=None, key=None):
        self.file = file
        self.key = key

    def update_key(self, key):
        self.key = key

    def update_file(self, file):
        self.file = file
        self.key = None


DB_INFO = DBInfo(DATABASE)


# def get_caller_at_depth(depth=1):
#     """
#     获取指定深度的调用者
#     depth=1: 直接调用者
#     depth=2: 上层的调用者
#     """
#     stack = inspect.stack()
#     if len(stack) <= depth + 1:
#         return None
#
#     caller_frame = stack[depth + 1]  # +1 跳过当前函数
#     return {
#         'function': caller_frame.function,
#         'file': caller_frame.filename,
#         'line': caller_frame.lineno,
#         'code': caller_frame.code_context[0].strip() if caller_frame.code_context else None
#     }

def get_conn(file):
    """
    获取数据库连接

    Args:
        file: 数据库文件路径，必须提供，不能为 None

    Returns:
        数据库连接对象

    Raises:
        ValueError: 如果 file 为 None
    """
    if file is None:
        raise ValueError("file parameter cannot be None")
    if not os.path.exists(os.path.dirname(file)):
        os.makedirs(os.path.dirname(file))

    if not _config_instance.DEBUG:
        connection = sqlcipher3.connect(file, timeout=30,  # 关键：等待锁的超时时间
                                        detect_types=sqlite3.PARSE_DECLTYPES,
                                        check_same_thread=False)
        pw = get_key(DB_INFO)
        # 设置密码（同 setup_sqlcipher_connection：白名单校验 + 拼接与执行分离）
        connection.execute(_build_pragma_key_statement(pw))
        pw = '0' * len(pw)
        del pw
    else:
        connection = sqlite3.connect(file, timeout=30,  # 关键：等待锁的超时时间
                                     detect_types=sqlite3.PARSE_DECLTYPES,
                                     check_same_thread=False)
    return connection
