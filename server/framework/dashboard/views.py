import os
import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Optional

import sqlcipher3
from flask import Blueprint, request
from sqlalchemy import func

from common.db.SQLOperation import db_session_scope, get_conn, DatabaseException
from common.public.public import SECONDS_PER_MINUTE, get_codemig_data_path
from common.response.response_code import ResponseCode
from framework.config_manager.config import ConfigKeys, SysConfig
from framework.log_manager.operation_constant import OpLogEvent, OpLogModule, OpLogResult
from framework.log_manager.operation_log import OperationLog
from framework.user_manager.user_db import UserManager
from session_cache import UserSessionCache
from plugin.codemig.solver.solvers_mapping import SolverType
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# 代码迁移任务的软删除状态值（codemig_task_manager.task_common.TaskStatus.DELETED），
# 统计时须排除；dashboard 不直接依赖插件模块，避免 framework -> plugin 反向依赖
CODEMIG_TASK_DELETED = 4    

# --- 轻量缓存，避免频繁扫描 codemig 用户库 ---
_CODEMIG_CACHE = {
    "ts": 0.0,
    "ttl_s": 5.0,
    "db_paths": None,
}


def _parse_ymd(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _list_codemig_db_paths() -> list[str]:
    now = time.time()
    if _CODEMIG_CACHE["db_paths"] is not None and now - _CODEMIG_CACHE["ts"] <= _CODEMIG_CACHE["ttl_s"]:
        return _CODEMIG_CACHE["db_paths"]

    base = get_codemig_data_path()
    # 已软删除目录（has_removed=1）的库文件在定时物理清理前仍在磁盘上，
    # 问题/AI 统计须与其余口径一致地排除，先取其 dir_id 集合
    removed_dir_ids = _query_removed_codemig_dir_ids()

    out: list[str] = []
    if os.path.isdir(base):
        # data/codemig/<user>/<dir_id>/<dir_id>.db
        for user_name in os.listdir(base):
            user_dir = os.path.join(base, user_name)
            if not os.path.isdir(user_dir):
                continue
            for dir_id in os.listdir(user_dir):
                if dir_id in removed_dir_ids:
                    continue
                dir_path = os.path.join(user_dir, dir_id)
                if not os.path.isdir(dir_path):
                    continue
                db_path = os.path.join(dir_path, f"{dir_id}.db")
                if os.path.isfile(db_path):
                    out.append(db_path)

    _CODEMIG_CACHE["ts"] = now
    _CODEMIG_CACHE["db_paths"] = out
    return out


def _query_removed_codemig_dir_ids() -> set[str]:
    """主库中已软删除目录（has_removed=1）的 dir_id 集合，查询失败时返回空集（不排除任何库）。"""
    try:
        with db_session_scope() as session:
            rows = session.query(CodemigDirectoryStorage.dir_id).filter(
                CodemigDirectoryStorage.has_removed == 1
            ).all()
            return {str(dir_id) for (dir_id,) in rows or []}
    except (DatabaseException, OSError, ValueError):
        return set()


def _query_codemig_issue_and_ai_stats(start: date, end: date):
    """
    从所有 codemig 用户数据库聚合（均在 [start, end] 日期内，已软删除目录除外）：
    - 问题数（suggestion ignored=0）
    - 各类问题占比（按 suggestion.type）
    - AI 使用次数（codemig_task_ai）
    - 问题/AI 的按日趋势
    """
    issue_total = 0
    ai_total = 0
    issue_by_type: dict[int, int] = {}
    issue_by_day: dict[str, int] = {}
    ai_by_day: dict[str, int] = {}

    start_s = start.isoformat()
    end_s = end.isoformat()

    db_paths = _list_codemig_db_paths()
    for db_path in db_paths:
        conn = None
        try:
            conn = get_conn(db_path)
            cur = conn.cursor()

            # 周期内问题总数
            # created_at 由 SQLite DEFAULT CURRENT_TIMESTAMP 写入，存的是 UTC；
            # 统计口径是本地日期，读取时须加 'localtime' 修饰符换算
            cur.execute(
                "SELECT COUNT(1) FROM codemig_task_directory_file_suggestion "
                "WHERE ignored = 0 AND date(created_at, 'localtime') BETWEEN ? AND ?",
                (start_s, end_s),
            )
            row = cur.fetchone()
            issue_total += int(row[0] or 0) if row else 0

            # 周期内各类问题数
            cur.execute(
                "SELECT type, COUNT(1) FROM codemig_task_directory_file_suggestion "
                "WHERE ignored = 0 AND date(created_at, 'localtime') BETWEEN ? AND ? "
                "GROUP BY type",
                (start_s, end_s),
            )
            for t, c in cur.fetchall() or []:
                try:
                    issue_by_type[int(t)] = issue_by_type.get(int(t), 0) + int(c or 0)
                except (TypeError, ValueError):
                    continue

            # 周期内 AI 次数
            cur.execute(
                "SELECT COUNT(1) FROM codemig_task_ai "
                "WHERE date(created_at, 'localtime') BETWEEN ? AND ?",
                (start_s, end_s),
            )
            row = cur.fetchone()
            ai_total += int(row[0] or 0) if row else 0

            cur.execute(
                "SELECT date(created_at, 'localtime') AS d, COUNT(1) "
                "FROM codemig_task_directory_file_suggestion "
                "WHERE ignored = 0 AND date(created_at, 'localtime') BETWEEN ? AND ? "
                "GROUP BY d ORDER BY d ASC",
                (start_s, end_s),
            )
            for d, c in cur.fetchall() or []:
                if d:
                    issue_by_day[str(d)] = issue_by_day.get(str(d), 0) + int(c or 0)

            cur.execute(
                "SELECT date(created_at, 'localtime') AS d, COUNT(1) "
                "FROM codemig_task_ai "
                "WHERE date(created_at, 'localtime') BETWEEN ? AND ? "
                "GROUP BY d ORDER BY d ASC",
                (start_s, end_s),
            )
            for d, c in cur.fetchall() or []:
                if d:
                    ai_by_day[str(d)] = ai_by_day.get(str(d), 0) + int(c or 0)

        except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError, OSError, ValueError):
            # 某个用户库损坏/缺表时，跳过即可（不影响整体）
            continue
        finally:
            if conn:
                conn.close()

    # 转为前端饼图数据：name 使用 SolverType 的枚举名（与前端 mock 的大写风格一致）
    issue_type_pie = []
    for t, c in sorted(issue_by_type.items(), key=lambda x: x[1], reverse=True):
        try:
            name = SolverType(t).name
        except ValueError:
            name = str(t)
        issue_type_pie.append({"name": name, "value": int(c)})

    return {
        "issue_total": int(issue_total),
        "ai_total": int(ai_total),
        "issue_type_pie": issue_type_pie,
        "issue_by_day": issue_by_day,
        "ai_by_day": ai_by_day,
    }


def _query_login_by_day(start: date, end: date) -> dict[str, int]:
    """
    以 operation 表的 Login Successful 作为“活跃用户”趋势的近似口径（按天统计去重用户数）。
    """
    start_ts = datetime.combine(start, datetime.min.time()).timestamp()
    end_ts = datetime.combine(end, datetime.max.time()).timestamp()
    out: dict[str, int] = {}
    try:
        with db_session_scope() as session:
            rows = (
                session.query(
                    # time 是本地时间写入的 epoch；datetime(..., 'unixepoch') 转出 UTC 日期，
                    # 须再加 'localtime' 才能落到本地日的桶上，否则凌晨 0-8 点会被记到前一天
                    func.date(func.datetime(OperationLog.time, "unixepoch", "localtime")).label("d"),
                    func.count(func.distinct(OperationLog.user_id)).label("c"),
                )
                .filter(OperationLog.time >= start_ts)
                .filter(OperationLog.time <= end_ts)
                .filter(OperationLog.module == OpLogModule.SYSTEM)
                .filter(OperationLog.event == OpLogEvent.LOGIN)
                .filter(OperationLog.result == OpLogResult.SUCCESS)
                .group_by("d")
                .order_by("d")
                .all()
            )
            for d, c in rows:
                if d:
                    out[str(d)] = int(c or 0)
    except (DatabaseException, OSError, ValueError):
        return {}
    return out


def _query_task_created_by_day(start: date, end: date) -> dict[str, int]:
    """仅统计代码迁移任务 codemig_tasks（按 created_at 落日在区间内，排除已删除 status=4）。"""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    out: dict[str, int] = {}
    try:
        with db_session_scope() as session:
            rows = (
                session.query(func.date(CodemigTasks.created_at).label("d"), func.count(CodemigTasks.task_id).label("c"))
                .filter(CodemigTasks.status != CODEMIG_TASK_DELETED)
                .filter(CodemigTasks.created_at.isnot(None))
                .filter(CodemigTasks.created_at >= start_dt)
                .filter(CodemigTasks.created_at <= end_dt)
                .group_by("d")
                .order_by("d")
                .all()
            )
            for d, c in rows:
                if d:
                    out[str(d)] = out.get(str(d), 0) + int(c or 0)
    except (DatabaseException, OSError, ValueError):
        return {}
    return out


def _query_codemig_task_total(start: date, end: date) -> int:
    """周期内 codemig_tasks 数量（与人员任务权重、时序一致，排除已删除 status=4）。"""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    try:
        with db_session_scope() as session:
            cnt = (
                session.query(func.count(CodemigTasks.task_id))
                .filter(CodemigTasks.status != CODEMIG_TASK_DELETED)
                .filter(CodemigTasks.created_at.isnot(None))
                .filter(CodemigTasks.created_at >= start_dt)
                .filter(CodemigTasks.created_at <= end_dt)
                .scalar()
            )
            return int(cnt or 0)
    except (DatabaseException, OSError, ValueError):
        return 0


def _query_user_task_weight(start: date, end: date):
    """仅 codemig_tasks，按周期内 created_at 统计各用户任务数（排除已删除 status=4）。"""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    counts: dict[str, int] = {}
    try:
        with db_session_scope() as session:
            rows2 = (
                session.query(CodemigTasks.user_id, func.count(CodemigTasks.task_id))
                .filter(CodemigTasks.status != CODEMIG_TASK_DELETED)
                .filter(CodemigTasks.user_id.isnot(None))
                .filter(CodemigTasks.created_at.isnot(None))
                .filter(CodemigTasks.created_at >= start_dt)
                .filter(CodemigTasks.created_at <= end_dt)
                .group_by(CodemigTasks.user_id)
                .all()
            )
            for uid, c in rows2:
                if uid is None:
                    continue
                counts[str(uid)] = counts.get(str(uid), 0) + int(c or 0)

            # user_id -> user_name
            user_ids = list(counts.keys())
            name_map: dict[str, str] = {}
            if user_ids:
                users = session.query(UserManager).filter(UserManager.user_id.in_(user_ids)).all()
                for u in users:
                    if getattr(u, "user_id", None) is not None:
                        name_map[str(u.user_id)] = u.user_name or str(u.user_id)

    except (DatabaseException, OSError, ValueError):
        return []

    pie = []
    for uid, c in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        pie.append({"name": name_map.get(uid, uid), "value": int(c)})
    return pie


def _build_migration_panel(start: date, end: date, online_user_count: int):
    codemig_stats = _query_codemig_issue_and_ai_stats(start, end)
    login_by_day = _query_login_by_day(start, end)
    task_by_day = _query_task_created_by_day(start, end)

    time_stamp: list[str] = []
    user_count: list[int] = []
    task_count: list[int] = []
    issue_count: list[int] = []
    ai_usage: list[int] = []
    for d in _daterange(start, end):
        ds = d.isoformat()
        time_stamp.append(ds)
        user_count.append(int(login_by_day.get(ds, 0)))
        task_count.append(int(task_by_day.get(ds, 0)))
        issue_count.append(int(codemig_stats["issue_by_day"].get(ds, 0)))
        ai_usage.append(int(codemig_stats["ai_by_day"].get(ds, 0)))

    return {
        "panel": "migration",
        "summary": {
            "online_user_count": int(online_user_count),
            "task_count": int(_query_codemig_task_total(start, end)),
            "issue_count": int(codemig_stats["issue_total"]),
            "ai_usage": int(codemig_stats["ai_total"]),
        },
        "timeseries": {
            "time_stamp": time_stamp,
            "user_count": user_count,
            "task_count": task_count,
            "issue_count": issue_count,
            "ai_usage": ai_usage,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "user_task_pie": _query_user_task_weight(start, end),
        "issue_type_pie": codemig_stats["issue_type_pie"],
    }


@dashboard_bp.route('/system_panel', methods=['GET'])
def system_panel():
    # 默认：过去 30 天
    today = datetime.now().date()
    start = _parse_ymd(request.args.get("start")) or (today - timedelta(days=30))
    end = _parse_ymd(request.args.get("end")) or today
    if start > end:
        start, end = end, start

    panel = (request.args.get("panel") or "migration").strip().lower()
    if panel not in ("migration", "codemig"):
        panel = "migration"
    if panel == "codemig":
        panel = "migration"

    # 在线用户：复用 session timeout 口径
    status, timeout_min, _ = SysConfig.query_system_configuration(ConfigKeys.SESSION_TIMEOUT)
    if not status:
        timeout_min = 30
    exp_time = int(time.time()) - int(timeout_min) * SECONDS_PER_MINUTE
    online_users = UserSessionCache.get_online_users_all_roles(exp_time)
    online_n = int(len(online_users))

    data = _build_migration_panel(start, end, online_n)

    return {"code": 0, "msg": ResponseCode.OK, "data": data}

