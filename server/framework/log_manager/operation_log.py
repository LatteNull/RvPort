import sys
import csv
import os
import random
import signal
import atexit
import string
import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from framework.log_manager.operation_constant import OpLogResult, OpLogModule, OpLogEvent
from framework.user_manager.user_db import UserManager
from common.db.SQLOperation import Base, db_session_scope, DatabaseException
from sqlalchemy import Column, Integer, String, Float, Text, func, or_
from common.public import logger
from common.public.public import DB_DIR
from framework.config_manager.config import ConfigKeys, SysConfig

LOGGER = logger.init_log('oplog', 'operation_log.log')
EXPIRATION_DAYS = 31
MAX_LOG_SIZE = 1000000
WAL_DIR = os.path.join(DB_DIR, 'logmanager')


def _wal_path():
    """WAL 路径按写入时的实际 pid 动态生成。

    模块级常量方案（oplog.{导入时pid}.wal）在 gunicorn 预 fork 模型下有缺陷：
    worker 继承 master 的 pid 段，多个进程会写同一个 WAL 文件互相覆盖。
    """
    return os.path.join(WAL_DIR, f'oplog.{os.getpid()}.wal')


class _LogBuffer:
    FLUSH_INTERVAL = 5
    FLUSH_BATCH_SIZE = 200
    MAX_BUFFER_SIZE = 10000

    _instance = None
    _init_flag = False
    # _ensure_alive 专用的重启互斥：模块加载时创建一次，此后不再替换，
    # 保证任何进程/线程里都指向同一把锁（不能放进 _ensure_alive 重建的对象组里）
    _restart_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if _LogBuffer._init_flag:
            return
        _LogBuffer._init_flag = True
        self._queue = deque()
        self._lock = threading.Lock()
        # 刷盘串行锁：保证 _do_flush 的"取批次-落库-提交"整体互斥，
        # 测试侧可持该锁完成"刷盘+查询"，避免与后台线程的进行中事务竞态
        self._flush_lock = threading.RLock()
        self._flush_event = threading.Event()
        self._stopped = False
        self._owner_pid = os.getpid()
        self._recover_wal()
        self._thread = threading.Thread(target=self._flush_worker, name='oplog-writer', daemon=True)
        self._thread.start()
        atexit.register(self._graceful_shutdown)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _ensure_alive(self):
        """fork 自愈：gunicorn 等 prefork 服务中，worker 进程继承的刷盘线程副本已死，
        且类属性 _init_flag=True 阻止重新初始化，队列将永远没有消费者（日志只进 WAL
        不落库）。在 push 入口检测：owner 不是当前进程或线程已死时，新建全部同步
        原语并重启刷盘线程。新建而非复用，规避 fork 瞬间继承到"已持有"状态的锁
        导致的永久死锁；不重跑 WAL 恢复，避免与父进程的恢复逻辑竞态重复落库。
        """
        if self._owner_pid == os.getpid() and self._thread.is_alive():
            return
        with self._restart_lock:
            if self._owner_pid == os.getpid() and self._thread.is_alive():
                return
            LOGGER.info(f'Flush thread unavailable in pid {os.getpid()} '
                        f'(owner pid {self._owner_pid}), restarting log flusher')
            self._queue = deque()
            self._lock = threading.Lock()
            self._flush_lock = threading.RLock()
            self._flush_event = threading.Event()
            self._stopped = False
            self._owner_pid = os.getpid()
            self._thread = threading.Thread(target=self._flush_worker,
                                            name='oplog-writer', daemon=True)
            self._thread.start()

    def _signal_handler(self, signum, frame):
        self._graceful_shutdown()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _graceful_shutdown(self):
        if self._stopped:
            return
        self._stopped = True
        self._flush_event.set()
        self._thread.join(timeout=10)
        self._do_flush()
        with self._lock:
            if self._queue:
                self._rebuild_wal()
            else:
                wal_path = _wal_path()
                if os.path.exists(wal_path):
                    os.remove(wal_path)

    def _wal_append(self, entry):
        line = json.dumps({
            'user_id': entry.user_id,
            'user_name': entry.user_name,
            'ip': entry.ip,
            'module': entry.module,
            'event': entry.event,
            'result': entry.result,
            'time': entry.time,
            'info': entry.info,
            'detail': entry.detail,
        }, ensure_ascii=False)
        os.makedirs(WAL_DIR, exist_ok=True)
        with open(_wal_path(), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
            f.flush()
            os.fsync(f.fileno())

    def _rebuild_wal(self):
        tmp_path = _wal_path() + '.tmp'
        try:
            os.makedirs(WAL_DIR, exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                for entry in self._queue:
                    line = json.dumps({
                        'user_id': entry.user_id,
                        'user_name': entry.user_name,
                        'ip': entry.ip,
                        'module': entry.module,
                        'event': entry.event,
                        'result': entry.result,
                        'time': entry.time,
                        'info': entry.info,
                        'detail': entry.detail,
                    }, ensure_ascii=False)
                    f.write(line + '\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, _wal_path())
        except (OSError, IOError, ValueError, TypeError) as e:
            LOGGER.error(f'Rebuild WAL failed: {e}')
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _recover_wal(self):
        if not os.path.exists(WAL_DIR):
            return
        wal_files = sorted(
            f for f in os.listdir(WAL_DIR)
            if f.startswith('oplog.') and f.endswith('.wal')
        )
        for wal_file in wal_files:
            wal_path = os.path.join(WAL_DIR, wal_file)
            self._recover_single_wal(wal_path)

    def _recover_single_wal(self, wal_path):
        if not os.path.exists(wal_path):
            return
        recovered = 0
        try:
            with open(wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = OperationLog(
                            user_id=data.get('user_id'),
                            user_name=data.get('user_name'),
                            ip=data.get('ip'),
                            module=data.get('module'),
                            event=data.get('event'),
                            result=data.get('result'),
                            time=data.get('time'),
                            info=data.get('info'),
                            detail=data.get('detail'),
                        )
                        self._queue.append(entry)
                        recovered += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
            if recovered > 0:
                LOGGER.info(f'Recovered {recovered} log entries from {wal_path}')
                self._flush_event.set()
            os.remove(wal_path)
        except (OSError, IOError, DatabaseException) as e:
            LOGGER.error(f'WAL recovery failed for {wal_path}: {e}')

    def push(self, entry):
        self._ensure_alive()
        with self._lock:
            if len(self._queue) >= self.MAX_BUFFER_SIZE:
                dropped = len(self._queue) - self.MAX_BUFFER_SIZE + 1
                for _ in range(dropped):
                    self._queue.popleft()
                LOGGER.warning(f'Log buffer full, dropped {dropped} oldest entries')
            self._queue.append(entry)
        try:
            self._wal_append(entry)
        except (OSError, IOError, TypeError, ValueError) as e:
            LOGGER.error(f'WAL append failed: {e}')
        self._flush_event.set()

    def stop(self):
        self._graceful_shutdown()

    def _flush_worker(self):
        cleanup_counter = 0
        while True:
            self._flush_event.wait(timeout=self.FLUSH_INTERVAL)
            self._flush_event.clear()
            self._do_flush()
            cleanup_counter += 1
            if cleanup_counter >= 12:
                cleanup_counter = 0
                try:
                    OperationLog.del_over_limit_log()
                except (DatabaseException, OSError, IOError, RuntimeError) as e:
                    LOGGER.error(f'Periodic log cleanup failed: {e}')
            if self._stopped:
                self._do_flush()
                break

    def _do_flush(self):
        with self._flush_lock:
            return self._do_flush_locked()

    def _do_flush_locked(self):
        batch = []
        with self._lock:
            while self._queue:
                batch.append(self._queue.popleft())
                if len(batch) >= self.FLUSH_BATCH_SIZE:
                    break
        if not batch:
            return
        self._write_batch(batch)
        with self._lock:
            self._rebuild_wal()
        if len(batch) >= self.FLUSH_BATCH_SIZE:
            self._flush_event.set()

    @staticmethod
    def _write_batch(batch):
        try:
            with db_session_scope() as session:
                session.bulk_save_objects(batch)
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Bulk write operation logs failed ({len(batch)} entries): {e}')
            for entry in batch:
                try:
                    with db_session_scope() as session:
                        session.add(entry)
                except (DatabaseException, OSError, IOError, RuntimeError):
                    # 单条兜底也失败：该条放弃（WAL 已有副本，重启后可恢复）
                    pass


# 注意：log_buffer 必须在 OperationLog 类定义之后实例化。
# _LogBuffer.__init__ 会同步执行 _recover_wal()，其中构造 OperationLog(...) ORM 对象；
# 若在 OperationLog 定义前实例化，恢复遗留 WAL 时会触发 NameError: name 'OperationLog' is not defined。
class OperationLog(Base):
    """
    操作日志 ORM 类
    对应数据库表: operation
    """
    __tablename__ = 'operation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64))
    user_name = Column(String(64))
    ip = Column(String(64))
    module = Column(String(32))
    event = Column(String(255))
    result = Column(String(128))
    time = Column(Float)  # REAL 类型对应 Float
    info = Column(String(255))
    detail = Column(Text)

    @staticmethod
    def get_count(user_id=None, filter_params=None, session=None):
        """
        使用 ORM 获取操作日志记录数量

        Args:
            user_id: 可选的用户 ID 过滤条件
            filter_params: 可选的过滤参数字典，支持的键: user_name, ip, result, module
                          值可以是单个值或逗号分隔的多个值（用于 OR 查询）
            session: 可选的 SQLAlchemy 会话对象，如果提供则使用该会话，否则创建新会话

        Returns:
            int: 记录数量
        """
        try:
            with db_session_scope() as session:
                return OperationLog._get_count(session, user_id, filter_params)
        except (DatabaseException, OSError, IOError, RuntimeError, ValueError) as e:
            LOGGER.error(f'Error getting operation log count: {e}')
            return 0

    @staticmethod
    def _get_count(session, user_id=None, filter_params=None):
        """
        使用 ORM 获取操作日志记录数量

        Args:
            user_id: 可选的用户 ID 过滤条件
            filter_params: 可选的过滤参数字典，支持的键: user_name, ip, result, module
                          值可以是单个值或逗号分隔的多个值（用于 OR 查询）
            session: 可选的 SQLAlchemy 会话对象，如果提供则使用该会话，否则创建新会话

        Returns:
            int: 记录数量
        """
        # 使用提供的会话
        base_query = OperationLog._build_query(session, user_id, filter_params)
        count = base_query.with_entities(func.count(OperationLog.id)).scalar()
        return count if count else 0

    @staticmethod
    def _build_query(session, user_id=None, filter_params=None):
        """
        构建 ORM 查询对象（内部辅助方法）

        Args:
            session: SQLAlchemy 会话对象
            user_id: 可选的用户 ID 过滤条件
            filter_params: 可选的过滤参数字典

        Returns:
            Query: SQLAlchemy 查询对象
        """
        query = session.query(OperationLog)

        # 应用 user_id 过滤
        if user_id is not None:
            query = query.filter(OperationLog.user_id == user_id)

        # 应用 filter_params 过滤
        if filter_params:
            VALID_FILTER_KEY = ['user_name', 'ip', 'result', 'module']
            for key, value in filter_params.items():
                if key not in VALID_FILTER_KEY:
                    raise ValueError(f'invalid filter param: {key}')
                if not value:
                    continue

                # 处理逗号分隔的多个值
                tmp_value = value.split(',')
                tmp_value = [v.strip() for v in tmp_value if v.strip()]

                if not tmp_value:
                    continue

                if len(tmp_value) > 1:
                    # 多个值：使用 OR 条件
                    if key in ['result', 'module']:
                        # 精确匹配
                        conditions = [getattr(OperationLog, key) == val for val in tmp_value]
                    else:
                        # 模糊匹配（LIKE）
                        conditions = [getattr(OperationLog, key).like(f'%{val}%') for val in
                                      tmp_value]
                    query = query.filter(or_(*conditions))
                else:
                    # 单个值
                    if key in ['result', 'module']:
                        # 精确匹配
                        query = query.filter(getattr(OperationLog, key) == tmp_value[0])
                    else:
                        # 模糊匹配（LIKE）
                        query = query.filter(getattr(OperationLog, key).like(f'%{tmp_value[0]}%'))

        return query

    @staticmethod
    def list_operation_log(user_id=None, limit=None, offset=None, filter_params=None):
        """
        使用 ORM 列出操作日志

        Args:
            user_id: 可选的用户 ID 过滤条件
            limit: 可选的结果数量限制
            offset: 可选的偏移量
            filter_params: 可选的过滤参数字典，支持的键: user_name, ip, result, module

        Returns:
            tuple: (success, error_code, result_dict)
                success: bool, 是否成功
                error_code: int, 错误代码（成功时为 0）
                result_dict: dict, 包含 total_log_count 和 operation_log_list
        """
        try:
            with db_session_scope() as session:
                # 建查询
                query = OperationLog._build_query(session, user_id=user_id,
                                                  filter_params=filter_params)
                count = query.with_entities(func.count(OperationLog.id)).scalar()
                total = count if count else 0
                # 按时间降序排序
                query = query.order_by(OperationLog.time.desc())
                index = 1
                # 应用分页
                if limit is not None:
                    if offset is None:
                        offset = 0
                    # 如果 offset 超过了 total，则显示最后一页
                    if total > 0 and offset >= total:
                        # 计算最后一页的 offset 和 index
                        # 最后一页的 index = ceil(total / limit)
                        last_page_index = (total + limit - 1) // limit if limit > 0 else 1
                        # 最后一页的 offset = (last_page_index - 1) * limit
                        offset = (last_page_index - 1) * limit
                        index = last_page_index
                    elif total == 0:
                        # 如果没有数据，重置 offset 和 index
                        offset = 0
                        index = 1
                    else:
                        # 正常情况，计算当前页
                        if limit and offset >= 0:
                            index = (offset // limit) + 1
                    query = query.limit(limit).offset(offset)

                # 执行查询
                logs = query.all()

                # 转换为字典格式
                out = []
                for log in logs:
                    out.append({
                        'id': log.id,
                        'user_id': log.user_id,
                        'user_name': log.user_name,
                        'ip': log.ip,
                        'module': log.module,
                        'event': log.event,
                        'result': log.result,
                        'time': datetime.fromtimestamp(log.time).strftime(
                            "%Y-%m-%d %H:%M:%S") if log.time else '',
                        'info': log.info if log.info else '',
                        'detail': log.detail if log.detail else ''
                    })

                return True, 0, {'total_log_count': total, 'operation_log_list': out,
                                 'current_page': index}
        except (DatabaseException, OSError, IOError, RuntimeError, ValueError) as e:
            LOGGER.error(f'list Operation DB Error: {e}')
            return False, str(e), None

    @staticmethod
    def insert(user_id, user_name, login_ip, module, event, result, detail=None):
        """
        使用 ORM 插入操作日志记录

        Args:
            user_id: 用户 ID
            user_name: 用户名
            login_ip: IP 地址
            module: 模块名（可以是字符串或 OpLogModule 枚举）
            event: 事件名（可以是字符串或 OpLogEvent 枚举）
            result: 结果（可以是字符串或 OpLogResult 枚举）
            detail: 详细信息（可选）

        Returns:
            OperationLog: 创建的日志记录对象，失败返回 None
        """
        try:
            with db_session_scope() as session:
                # 处理枚举类型，如果是枚举则取 value
                module_value = module.value if hasattr(module, 'value') else module
                event_value = event.value if hasattr(event, 'value') else event
                result_value = result.value if hasattr(result, 'value') else result

                # 创建新的日志记录
                log_entry = OperationLog(
                    user_id=user_id,
                    user_name=user_name,
                    ip=login_ip,
                    module=module_value,
                    event=event_value,
                    result=result_value,
                    time=datetime.now().timestamp(),
                    info=None,  # info 字段在原始函数中未使用
                    detail=detail
                )

                session.add(log_entry)
                # 注意：这里不调用 commit，因为 db_session_scope 会自动处理
                return log_entry
        except (DatabaseException, OSError, IOError, RuntimeError) as e:
            LOGGER.error(f'Error inserting operation log: {e}')
            return None

    @staticmethod
    def del_expire_log():
        """
        删除过期的操作日志记录（使用 ORM）
        """
        try:
            # 计算过期的日期
            expiation_time = (datetime.now() - timedelta(days=get_expire_days())).timestamp()

            with db_session_scope() as session:
                # 使用 ORM 删除过期记录
                deleted_count = session.query(OperationLog).filter(
                    OperationLog.time < expiation_time
                ).delete(synchronize_session=False)

                # 如果有记录被删除，记录系统日志
                if deleted_count > 0:
                    OperationLog.insert(None, 'system', '127.0.0.1', OpLogModule.LOG,
                                        OpLogEvent.LOG_DMP, OpLogResult.SUCCESS,
                                        'Operation logs dumped successfully.')
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f'Delete expired Operation log DB Error:{e}')

    @staticmethod
    def del_over_limit_log():
        """
        删除超出限制的旧日志记录（使用 ORM）
        当日志数量超过 MAX_LOG_SIZE 时，删除最早的记录
        """
        try:
            # 检查日志数量是否超出限制
            total_logs = OperationLog.get_count()
            max_log_size = get_max_log_size()

            # 如果日志数量超过 MAX_LOG_SIZE，则删除多余的旧记录
            if total_logs > max_log_size:
                # 确定需要删除的记录数量
                OperationLog.insert(None, 'system', '127.0.0.1', OpLogModule.LOG,
                                    'Cleanup Log', OpLogResult.SUCCESS,
                                    'Triggered log cleanup due to excessive number of log entries.')
                total_logs += 1
                excess_logs = total_logs - max_log_size

                with db_session_scope() as session:
                    # 获取需要删除的最早记录的 ID（按时间升序，取前 excess_logs 条）
                    old_logs = session.query(OperationLog.id).order_by(
                        OperationLog.time.asc()
                    ).limit(excess_logs).all()

                    if old_logs:
                        old_log_ids = [log.id for log in old_logs]

                        # 使用 ORM 删除这些记录
                        deleted_count = session.query(OperationLog).filter(
                            OperationLog.id.in_(old_log_ids)
                        ).delete(synchronize_session=False)

                        LOGGER.info(f'Deleted {deleted_count} old log entries due to size limit')
        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f'Delete over limit log DB Error:{e}')

    @staticmethod
    def record(user_id, user_name, login_ip, module, event, result, detail):
        module_value = module.value if hasattr(module, 'value') else module
        event_value = event.value if hasattr(event, 'value') else event
        result_value = result.value if hasattr(result, 'value') else result

        log_entry = OperationLog(
            user_id=user_id,
            user_name=user_name,
            ip=login_ip,
            module=module_value,
            event=event_value,
            result=result_value,
            time=datetime.now().timestamp(),
            info=None,
            detail=detail
        )
        log_buffer.push(log_entry)
        return 0


# 单例实例化：放在 OperationLog 类定义之后，确保 _LogBuffer.__init__ 做 WAL 恢复时
# OperationLog 已在模块全局命名空间中（避免 NameError）。
log_buffer = _LogBuffer()


def get_expire_days():
    status, log_expire_days, _ = SysConfig.query_system_configuration \
        (ConfigKeys.LOG_SAVE_TIME, cached=False)
    if status:
        try:
            days = int(log_expire_days)
        except ValueError:
            days = EXPIRATION_DAYS
        return days
    else:
        return EXPIRATION_DAYS


def get_max_log_size():
    return MAX_LOG_SIZE


def generate_random_string(length=10):
    # 定义字符集
    characters = string.ascii_letters + string.digits
    # 生成随机字符串
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


def write_csv(usr_id, operation_log):
    random_string = generate_random_string()
    file_name = f'{usr_id}_{random_string}.csv'
    path = os.path.join(DB_DIR, "logmanager", file_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    csv_dict = [
        {'User Name': i['user_name'], 'Operation': i['event'], 'Component Name': i['module'],
         'Result': i['result'], 'IP Address': i['ip'], 'Time': i['time'],
         'Detail': i['detail']} for i in operation_log]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['User Name', 'Operation', 'Component Name', 'Result', 'IP Address', 'Time',
                      'Detail']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        # 写入表头
        writer.writeheader()
        # 写入数据行
        writer.writerows(csv_dict)
    return f'{random_string}.csv'


def record_operation_log(user_id, login_ip, module, event, result: OpLogResult, detail=None,
                         user_name=None):
    db_user_name = ''
    if user_id:
        user = UserManager.query_by_id(user_id)
        if user:
            db_user_name = user.user_name
    if db_user_name != '':
        user_name = db_user_name
    return OperationLog.record(user_id, user_name, login_ip, module, event, result, detail)
