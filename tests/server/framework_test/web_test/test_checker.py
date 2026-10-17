from unittest.mock import patch

from framework.log_manager.operation_log import OperationLog, log_buffer

# 保存原始（未被 conftest patch 屏蔽的）清理函数引用，
# flush_and_cleanup 需要真实执行清理以对齐旧版 record 的同步清理行为
_orig_del_over_limit_log = OperationLog.del_over_limit_log


def get_last_operation_log(user_id, limit=1, offset=0):
    # record 已改为异步缓冲写入（log_buffer + 后台线程）。
    # 持刷盘串行锁完成"刷盘+查询"，既保证 HTTP 请求产生的日志已落库，
    # 也避免与后台线程进行中的事务竞态（后台弹出批次但未提交时查询会读到旧数据）
    with log_buffer._flush_lock:
        log_buffer._do_flush_locked()
        status, code, oplist = OperationLog.list_operation_log(user_id=user_id, limit=limit, offset=offset)
    return oplist['operation_log_list'][0]


def flush_logs():
    """仅同步刷盘（不触发超限清理），持锁避免与后台线程竞态。"""
    with log_buffer._flush_lock:
        log_buffer._do_flush_locked()


def flush_and_cleanup():
    """同步刷盘并触发超限清理。
    旧版 record 每次同步落库后即调 del_over_limit_log；WAL 重构后清理
    由后台线程周期触发，测试中需显式调用以对齐旧行为。
    使用原始函数引用，绕过 conftest 对类方法的 patch 屏蔽。"""
    with log_buffer._flush_lock:
        log_buffer._do_flush_locked()
        with patch.object(OperationLog, 'del_over_limit_log', _orig_del_over_limit_log):
            _orig_del_over_limit_log()
