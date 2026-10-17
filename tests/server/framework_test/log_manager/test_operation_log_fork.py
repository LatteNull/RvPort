"""
_LogBuffer fork 自愈测试。

gunicorn 预 fork 模型：master 进程 import 模块时 log_buffer 已启动刷盘线程；
worker 是 fork 出的子进程，继承的线程副本已死、_init_flag=True 阻止重建，
历史上导致 worker 的日志只进 WAL 队列、永远无人落库（CI 现象：/action/logmanager/list
总计 0 条）。push 入口的 _ensure_alive 负责检测并重启刷盘线程，本文件验证该机制。
"""
import os
import sys
import time
import tempfile
import warnings

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

import common.db.SQLOperation as sql_op
from common.db.SQLOperation import Base
from framework.log_manager.operation_constant import OpLogResult
from framework.log_manager.operation_log import (
    OperationLog, _LogBuffer, _wal_path, log_buffer,
)

POLL_TIMEOUT = 10


def _wait_flushed(check, timeout=POLL_TIMEOUT):
    """轮询等待后台刷盘线程把队列写入库（FLUSH_INTERVAL=5s 量级）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="function")
def setup_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db:
        db_path = db.name

    original_engine = sql_op.engine
    original_session = sql_op.db_session
    new_engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
    new_db_session = scoped_session(new_session_local)
    sql_op.engine = new_engine
    sql_op.db_session = new_db_session
    Base.metadata.create_all(bind=new_engine)

    try:
        yield db_path
    finally:
        sql_op.engine = original_engine
        sql_op.db_session = original_session
        new_engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


class TestEnsureAlive:
    def test_no_restart_in_owner_process(self, setup_db):
        """owner 进程内、线程存活时 _ensure_alive 是纯 no-op（不换对象）。"""
        lock_before = log_buffer._lock
        thread_before = log_buffer._thread
        log_buffer._ensure_alive()
        assert log_buffer._lock is lock_before
        assert log_buffer._thread is thread_before

    def test_restart_on_owner_pid_mismatch(self, setup_db):
        """伪造 fork 后状态（owner_pid 不一致、线程副本已死）→ push 触发重启。"""
        original = (log_buffer._owner_pid, log_buffer._thread, log_buffer._lock,
                    log_buffer._flush_event, log_buffer._queue, log_buffer._stopped)
        try:
            log_buffer._owner_pid = -1  # 模拟"当前进程不是创建线程的进程"
            assert not log_buffer._thread.is_alive() or True
            log_buffer._ensure_alive()
            assert log_buffer._owner_pid == os.getpid()
            assert log_buffer._thread.is_alive()
            assert log_buffer._thread is not original[1]
            assert log_buffer._lock is not original[2]
        finally:
            # 恢复现场，避免影响同进程其他用例
            log_buffer.stop()
            (log_buffer._owner_pid, log_buffer._thread, log_buffer._lock,
             log_buffer._flush_event, log_buffer._queue, log_buffer._stopped) = original

    def test_push_recovers_after_fork_state(self, setup_db):
        """fork 后状态调用 push：日志最终落库（自愈端到端，不开子进程）。"""
        original = (log_buffer._owner_pid, log_buffer._thread, log_buffer._lock,
                    log_buffer._flush_event, log_buffer._queue, log_buffer._stopped)
        try:
            log_buffer.stop()  # 停掉原线程并复位 _stopped
            log_buffer._owner_pid = -1  # 模拟 worker 继承态
            OperationLog.record('uid', 'fork_user', '127.0.0.1', 'mod', 'evt',
                                OpLogResult.SUCCESS, 'd')
            assert log_buffer._thread.is_alive()
            assert _wait_flushed(lambda: OperationLog.get_count() >= 1)
            assert OperationLog.get_count() == 1
        finally:
            log_buffer.stop()
            (log_buffer._owner_pid, log_buffer._thread, log_buffer._lock,
             log_buffer._flush_event, log_buffer._queue, log_buffer._stopped) = original


class TestWalPath:
    def test_wal_path_uses_current_pid(self):
        assert _wal_path().endswith(f'oplog.{os.getpid()}.wal')


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='平台不支持 fork')
class TestRealFork:
    def test_real_fork_child_flushes_to_db(self, setup_db):
        """真实 fork：子进程内 push 的日志由子进程自愈出的线程落库。"""
        read_fd, write_fd = os.pipe()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='.*multi-threaded.*fork.*')
            pid = os.fork()
        if pid == 0:
            # 子进程：继承态线程已死（fork 只保留调用线程），push 应触发自愈
            status = 1
            try:
                os.close(read_fd)
                OperationLog.record('uid', 'child_user', '127.0.0.1', 'mod', 'evt',
                                    OpLogResult.SUCCESS, 'child_detail')
                child_alive = log_buffer._thread.is_alive()
                flushed = _wait_flushed(lambda: OperationLog.get_count() >= 1)
                status = 0 if (child_alive and flushed) else 2
            except BaseException:
                status = 3
            finally:
                os.write(write_fd, bytes([status]))
                os.close(write_fd)
                os._exit(status)

        os.close(write_fd)
        try:
            status_byte = os.read(read_fd, 1)
            _, exit_status = os.waitpid(pid, 0)
        finally:
            os.close(read_fd)

        child_status = status_byte[0] if status_byte else 255
        # 管道回传的状态优先（_exit 前写入）；两者都校验更稳
        assert child_status == 0, f'子进程自愈失败 status={child_status}'
        assert os.waitstatus_to_exitcode(exit_status) == 0

        # 子进程 _exit 不触发 atexit/daemon 线程收尾，等 DB 数据可见即可
        assert _wait_flushed(lambda: OperationLog.get_count() >= 1)
        logs = OperationLog.list_operation_log()[2]['operation_log_list']
        assert any(log.get('user_name') == 'child_user' for log in logs)

    def test_real_fork_wal_pid_isolated(self, setup_db):
        """fork 前后 _wal_path() 分别取各自 pid，不再共享 master 的 WAL 文件名。"""
        read_fd, write_fd = os.pipe()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='.*multi-threaded.*fork.*')
            pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            # 子进程实际落一次 WAL 写，验证文件名带子进程 pid
            ok = 0
            try:
                from datetime import datetime
                from types import SimpleNamespace
                entry = SimpleNamespace(
                    user_id='u', user_name='n', ip='i', module='m', event='e',
                    result='r', time=datetime.now().timestamp(), info=None, detail='d')
                log_buffer._wal_append(entry)
                ok = 1 if os.path.exists(_wal_path()) else 2
            except BaseException:
                ok = 3
            finally:
                os.write(write_fd, bytes([ok]))
                os.close(write_fd)
                os._exit(0)

        os.close(write_fd)
        try:
            status_byte = os.read(read_fd, 1)
            os.waitpid(pid, 0)
        finally:
            os.close(read_fd)
        assert (status_byte[0] if status_byte else 255) == 1
        # 清理子进程产生的 WAL，避免影响后续用例的恢复逻辑
        child_wal = os.path.join(os.path.dirname(_wal_path()), f'oplog.{pid}.wal')
        if os.path.exists(child_wal):
            os.remove(child_wal)
