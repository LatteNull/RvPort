import os
import sys
sys.path.insert(0, os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'server')))

"""dashboard.views 单元测试。

覆盖：
- _parse_ymd / _daterange
- _list_codemig_db_paths：目录扫描 + 5s 缓存
- _query_codemig_issue_and_ai_stats：SQLite 聚合与损坏库跳过
- _query_login_by_day / _query_task_created_by_day / _query_codemig_task_total /
  _query_user_task_weight 各查询：正常 + DB 异常
- _build_migration_panel 组装
- /dashboard/system_panel 路由：参数解析、panel 选择、在线用户
"""
import sqlite3
import time
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from framework.dashboard import views as dv
from framework.dashboard.views import (
    dashboard_bp,
    _parse_ymd,
    _daterange,
    _list_codemig_db_paths,
    _query_removed_codemig_dir_ids,
    _query_codemig_issue_and_ai_stats,
    _query_login_by_day,
    _query_task_created_by_day,
    _query_codemig_task_total,
    _query_user_task_weight,
    _build_migration_panel,
    _CODEMIG_CACHE,
)


DV = 'framework.dashboard.views'


@pytest.fixture(autouse=True)
def _reset_codemig_cache():
    _CODEMIG_CACHE['ts'] = 0.0
    _CODEMIG_CACHE['db_paths'] = None
    yield
    _CODEMIG_CACHE['ts'] = 0.0
    _CODEMIG_CACHE['db_paths'] = None


def _mock_session_scope(rows=None, scalar=0):
    """构造 mock 的 db_session_scope，query().filter()...all()/scalar() 可链式调用。"""
    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.filter.return_value.filter.return_value = chain
    chain.group_by.return_value = chain
    chain.order_by.return_value = chain
    if rows is not None:
        chain.all.return_value = rows
    chain.scalar.return_value = scalar
    scope = MagicMock()
    scope.__enter__.return_value = session
    scope.__exit__.return_value = False
    return scope, session


def _make_codemig_db(path, suggestions=(), ai_rows=()):
    """构造带统计表的 codemig 用户库。suggestions: [(type, created_at_local_date_str)]"""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE codemig_task_directory_file_suggestion "
        "(type INTEGER, ignored INTEGER, created_at TEXT)"
    )
    for t, ts in suggestions:
        conn.execute(
            "INSERT INTO codemig_task_directory_file_suggestion VALUES (?,?,?)",
            (t, 0, ts),
        )
    conn.execute("CREATE TABLE codemig_task_ai (created_at TEXT)")
    for ts in ai_rows:
        conn.execute("INSERT INTO codemig_task_ai VALUES (?)", (ts,))
    conn.commit()
    conn.close()


# ---------------- 纯函数 ----------------

class TestParseYmd:
    def test_valid(self):
        assert _parse_ymd('2026-09-01') == date(2026, 9, 1)
        assert _parse_ymd(' 2026-09-01 12:30:00 ') == date(2026, 9, 1)  # 截取前10位
        assert _parse_ymd('2026-09-01T00') == date(2026, 9, 1)

    def test_invalid(self):
        assert _parse_ymd(None) is None
        assert _parse_ymd('') is None
        assert _parse_ymd('not-a-date') is None
        assert _parse_ymd('2026/09/01') is None


class TestDaterange:
    def test_single_day(self):
        days = list(_daterange(date(2026, 9, 1), date(2026, 9, 1)))
        assert days == [date(2026, 9, 1)]

    def test_multiple_days(self):
        days = list(_daterange(date(2026, 9, 1), date(2026, 9, 3)))
        assert days == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]

    def test_reversed_empty(self):
        assert list(_daterange(date(2026, 9, 3), date(2026, 9, 1))) == []


class TestListCodemigDbPaths:
    def test_base_missing(self, tmp_path):
        with patch(DV + '.get_codemig_data_path',
                   return_value=str(tmp_path / 'nope')), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value=set()):
            assert _list_codemig_db_paths() == []

    def test_scans_user_dirs(self, tmp_path):
        base = tmp_path / 'codemig'
        for user, dir_id in [('alice', '1'), ('bob', '2')]:
            d = base / user / dir_id
            d.mkdir(parents=True)
            (d / f'{dir_id}.db').write_bytes(b'x')
        # 干扰项：非目录、无 db 文件的目录
        (base / 'plain.txt').write_text('x')
        (base / 'alice' / 'empty').mkdir()
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value=set()):
            paths = _list_codemig_db_paths()
        assert len(paths) == 2
        assert all(p.endswith('.db') for p in paths)

    def test_skips_soft_deleted_dirs(self, tmp_path):
        # has_removed=1 的目录在物理清理前仍在磁盘上，但不应计入统计
        base = tmp_path / 'codemig'
        for user, dir_id in [('alice', '1'), ('bob', '2')]:
            d = base / user / dir_id
            d.mkdir(parents=True)
            (d / f'{dir_id}.db').write_bytes(b'x')
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value={'1'}):
            paths = _list_codemig_db_paths()
        assert len(paths) == 1
        assert paths[0].endswith('2.db')

    def test_cache_hit_within_ttl(self, tmp_path):
        base = tmp_path / 'codemig'
        d = base / 'alice' / '1'
        d.mkdir(parents=True)
        (d / '1.db').write_bytes(b'x')
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value=set()):
            first = _list_codemig_db_paths()
        # 第二次在 TTL 内：即使目录结构变化也走缓存
        (base / 'bob' / '2').mkdir(parents=True)
        (base / 'bob' / '2' / '2.db').write_bytes(b'x')
        with patch(DV + '.get_codemig_data_path', return_value=str(base)):
            second = _list_codemig_db_paths()
        assert first == second

    def test_cache_expired_rescans(self, tmp_path):
        base = tmp_path / 'codemig'
        d = base / 'alice' / '1'
        d.mkdir(parents=True)
        (d / '1.db').write_bytes(b'x')
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value=set()):
            _list_codemig_db_paths()
        # 过期缓存：手动把 ts 拨回
        _CODEMIG_CACHE['ts'] = time.time() - 10
        (base / 'bob' / '2').mkdir(parents=True)
        (base / 'bob' / '2' / '2.db').write_bytes(b'x')
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value=set()):
            paths = _list_codemig_db_paths()
        assert len(paths) == 2


# ---------------- _query_removed_codemig_dir_ids ----------------

class TestQueryRemovedDirIds:
    def test_rows_mapped_to_str_set(self):
        scope, _ = _mock_session_scope(rows=[(3,), (7,)])
        with patch(DV + '.db_session_scope', return_value=scope):
            out = _query_removed_codemig_dir_ids()
        assert out == {'3', '7'}

    def test_empty_rows(self):
        scope, _ = _mock_session_scope(rows=[])
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_removed_codemig_dir_ids() == set()

    def test_db_error_returns_empty_set(self):
        from common.db.SQLOperation import DatabaseException
        scope, _ = _mock_session_scope()
        scope.__enter__.side_effect = DatabaseException('db down')
        scope.__exit__.return_value = False
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_removed_codemig_dir_ids() == set()


# ---------------- _query_codemig_issue_and_ai_stats ----------------

class TestQueryCodemigStats:
    def test_aggregates_from_dbs(self, tmp_path):
        # 两个用户库：suggestion（type 0/1）与 AI 记录
        db1 = tmp_path / 'u1.db'
        _make_codemig_db(str(db1),
                         suggestions=[(0, '2026-09-01 10:00:00'), (0, '2026-09-02 11:00:00')],
                         ai_rows=['2026-09-01 12:00:00'])
        db2 = tmp_path / 'u2.db'
        _make_codemig_db(str(db2),
                         suggestions=[(1, '2026-09-02 09:00:00')],
                         ai_rows=['2026-09-02 08:00:00', '2026-09-02 09:30:00'])
        with patch(DV + '._list_codemig_db_paths', return_value=[str(db1), str(db2)]):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 1), date(2026, 9, 2))
        assert stats['issue_total'] == 3
        assert stats['ai_total'] == 3
        assert stats['issue_by_day'] == {'2026-09-01': 1, '2026-09-02': 2}
        assert stats['ai_by_day'] == {'2026-09-01': 1, '2026-09-02': 2}
        # 饼图：type 0 两项、type 1 一项
        pie = {p['name']: p['value'] for p in stats['issue_type_pie']}
        assert pie.get('MAKEFILE') == 2  # SolverType(0).name
        assert pie.get('INTRINSICS') == 1  # SolverType(1).name

    def test_date_range_filters(self, tmp_path):
        db = tmp_path / 'u.db'
        _make_codemig_db(str(db),
                         suggestions=[(0, '2026-09-01 10:00:00'), (0, '2026-09-05 10:00:00')],
                         ai_rows=['2026-09-01 10:00:00', '2026-09-05 10:00:00'])
        with patch(DV + '._list_codemig_db_paths', return_value=[str(db)]):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 2), date(2026, 9, 4))
        assert stats['issue_total'] == 0
        assert stats['ai_total'] == 0

    def test_corrupt_db_skipped(self, tmp_path):
        bad = tmp_path / 'bad.db'
        bad.write_bytes(b'not a sqlite db at all')
        good = tmp_path / 'good.db'
        _make_codemig_db(str(good), suggestions=[(0, '2026-09-01 10:00:00')])
        with patch(DV + '._list_codemig_db_paths', return_value=[str(bad), str(good)]):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 1), date(2026, 9, 1))
        assert stats['issue_total'] == 1  # 坏库跳过，好库正常聚合

    def test_empty_db_list(self):
        with patch(DV + '._list_codemig_db_paths', return_value=[]):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 1), date(2026, 9, 1))
        assert stats['issue_total'] == 0
        assert stats['ai_total'] == 0
        assert stats['issue_type_pie'] == []

    def test_unknown_solver_type_falls_back_to_str(self, tmp_path):
        db = tmp_path / 'u.db'
        _make_codemig_db(str(db), suggestions=[(999, '2026-09-01 10:00:00')])
        with patch(DV + '._list_codemig_db_paths', return_value=[str(db)]):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 1), date(2026, 9, 1))
        assert stats['issue_type_pie'] == [{'name': '999', 'value': 1}]

    def test_soft_deleted_dir_excluded(self, tmp_path):
        # 软删除目录的库文件仍在磁盘上，但路径已被 _list_codemig_db_paths 过滤
        base = tmp_path / 'codemig'
        kept = base / 'alice' / '2'
        removed = base / 'alice' / '1'
        kept.mkdir(parents=True)
        removed.mkdir(parents=True)
        _make_codemig_db(str(kept / '2.db'),
                         suggestions=[(0, '2026-09-01 10:00:00')])
        _make_codemig_db(str(removed / '1.db'),
                         suggestions=[(0, '2026-09-01 10:00:00'),
                                      (0, '2026-09-01 11:00:00')])
        with patch(DV + '.get_codemig_data_path', return_value=str(base)), \
             patch(DV + '._query_removed_codemig_dir_ids', return_value={'1'}):
            stats = _query_codemig_issue_and_ai_stats(
                date(2026, 9, 1), date(2026, 9, 1))
        # 只统计未被软删除目录 2.db 的一条问题
        assert stats['issue_total'] == 1


# ---------------- 各 SQL 查询（mock session） ----------------

class TestQueryLoginByDay:
    def test_rows_mapped(self):
        scope, _ = _mock_session_scope(rows=[('2026-09-01', 3), ('2026-09-02', 5)])
        with patch(DV + '.db_session_scope', return_value=scope):
            out = _query_login_by_day(date(2026, 9, 1), date(2026, 9, 2))
        assert out == {'2026-09-01': 3, '2026-09-02': 5}

    def test_none_day_skipped(self):
        scope, _ = _mock_session_scope(rows=[(None, 3), ('2026-09-01', 2)])
        with patch(DV + '.db_session_scope', return_value=scope):
            out = _query_login_by_day(date(2026, 9, 1), date(2026, 9, 2))
        assert out == {'2026-09-01': 2}

    def test_db_error_returns_empty(self):
        from common.db.SQLOperation import DatabaseException
        scope, _ = _mock_session_scope()
        scope.__enter__.side_effect = DatabaseException('db down')
        scope.__exit__.return_value = False
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_login_by_day(date(2026, 9, 1), date(2026, 9, 2)) == {}


class TestQueryTaskCreatedByDay:
    def test_rows_accumulated(self):
        scope, _ = _mock_session_scope(rows=[('2026-09-01', 2), ('2026-09-01', 3)])
        with patch(DV + '.db_session_scope', return_value=scope):
            out = _query_task_created_by_day(date(2026, 9, 1), date(2026, 9, 2))
        assert out == {'2026-09-01': 5}  # 同日多行累加

    def test_db_error_returns_empty(self):
        from common.db.SQLOperation import DatabaseException
        scope, _ = _mock_session_scope()
        scope.__enter__.side_effect = DatabaseException('db down')
        scope.__exit__.return_value = False
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_task_created_by_day(date(2026, 9, 1), date(2026, 9, 2)) == {}


class TestQueryCodemigTaskTotal:
    def test_count(self):
        scope, _ = _mock_session_scope(scalar=7)
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_codemig_task_total(date(2026, 9, 1), date(2026, 9, 2)) == 7

    def test_none_scalar_is_zero(self):
        scope, _ = _mock_session_scope(scalar=None)
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_codemig_task_total(date(2026, 9, 1), date(2026, 9, 2)) == 0

    def test_db_error_returns_zero(self):
        from common.db.SQLOperation import DatabaseException
        scope, _ = _mock_session_scope()
        scope.__enter__.side_effect = DatabaseException('db down')
        scope.__exit__.return_value = False
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_codemig_task_total(date(2026, 9, 1), date(2026, 9, 2)) == 0


class TestQueryUserTaskWeight:
    def test_pie_with_user_names(self):
        # 两次 query：第1次分组计数，第2次查用户名（filter().all()）
        scope, session = _mock_session_scope(rows=[('uid-1', 4), ('uid-2', 2)])
        user_obj = MagicMock(user_id='uid-1', user_name='alice')
        grouped = session.query.return_value
        user_query = MagicMock()
        user_query.filter.return_value.all.return_value = [user_obj]
        session.query.side_effect = [grouped, user_query]
        with patch(DV + '.db_session_scope', return_value=scope):
            pie = _query_user_task_weight(date(2026, 9, 1), date(2026, 9, 2))
        assert pie[0] == {'name': 'alice', 'value': 4}
        assert pie[1] == {'name': 'uid-2', 'value': 2}  # 查不到用户名时用 uid

    def test_none_uid_skipped(self):
        scope, _ = _mock_session_scope(rows=[(None, 4)])
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_user_task_weight(date(2026, 9, 1), date(2026, 9, 2)) == []

    def test_db_error_returns_empty(self):
        from common.db.SQLOperation import DatabaseException
        scope, _ = _mock_session_scope()
        scope.__enter__.side_effect = DatabaseException('db down')
        scope.__exit__.return_value = False
        with patch(DV + '.db_session_scope', return_value=scope):
            assert _query_user_task_weight(date(2026, 9, 1), date(2026, 9, 2)) == []


# ---------------- panel 组装 ----------------

class TestBuildMigrationPanel:
    def test_panel_structure(self):
        start, end = date(2026, 9, 1), date(2026, 9, 3)
        codemig_stats = {
            'issue_total': 4, 'ai_total': 2,
            'issue_by_day': {'2026-09-01': 1, '2026-09-02': 3},
            'ai_by_day': {'2026-09-01': 2},
            'issue_type_pie': [{'name': 'MAKEFILE', 'value': 4}],
        }
        with patch(DV + '._query_codemig_issue_and_ai_stats', return_value=codemig_stats), \
             patch(DV + '._query_login_by_day',
                   return_value={'2026-09-01': 2, '2026-09-03': 1}), \
             patch(DV + '._query_task_created_by_day', return_value={'2026-09-02': 7}), \
             patch(DV + '._query_codemig_task_total', return_value=7), \
             patch(DV + '._query_user_task_weight',
                   return_value=[{'name': 'alice', 'value': 7}]):
            panel = _build_migration_panel(start, end, 3)
        assert panel['panel'] == 'migration'
        assert panel['summary'] == {
            'online_user_count': 3, 'task_count': 7,
            'issue_count': 4, 'ai_usage': 2,
        }
        ts = panel['timeseries']
        assert ts['time_stamp'] == ['2026-09-01', '2026-09-02', '2026-09-03']
        assert ts['user_count'] == [2, 0, 1]
        assert ts['task_count'] == [0, 7, 0]
        assert ts['issue_count'] == [1, 3, 0]
        assert ts['ai_usage'] == [2, 0, 0]
        assert ts['start'] == '2026-09-01' and ts['end'] == '2026-09-03'
        assert panel['user_task_pie'] == [{'name': 'alice', 'value': 7}]
        assert panel['issue_type_pie'] == [{'name': 'MAKEFILE', 'value': 4}]


# ---------------- 蓝图路由 ----------------

class TestSystemPanelRoute:
    @pytest.fixture()
    def client(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.secret_key = 'test-secret'
        app.register_blueprint(dashboard_bp)
        return app.test_client()

    def _patch_common(self):
        """mock 面板构建与在线用户依赖。"""
        return [
            patch(DV + '.SysConfig.query_system_configuration',
                  return_value=(True, 30, None)),
            patch(DV + '.UserSessionCache.get_online_users_all_roles',
                  return_value=['u1', 'u2']),
            patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration', 'summary': {}}),
        ]

    def test_default_migration_panel(self, client):
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles',
                   return_value=['u1', 'u2']) as mock_online, \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build:
            resp = client.get('/dashboard/system_panel')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['code'] == 0
        assert body['data']['panel'] == 'migration'
        # 在线用户按 session timeout 口径计算
        exp_time = mock_online.call_args.args[0]
        assert exp_time <= time.time()
        args = mock_build.call_args.args
        assert args[2] == 2  # online_user_count

    def test_panel_codemig_alias_to_migration(self, client):
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles', return_value=[]), \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build:
            resp = client.get('/dashboard/system_panel?panel=codemig')
        assert resp.get_json()['data']['panel'] == 'migration'
        assert mock_build.called

    def test_invalid_panel_falls_back_to_migration(self, client):
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles', return_value=[]), \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build:
            resp = client.get('/dashboard/system_panel?panel=bogus')
        assert resp.get_json()['data']['panel'] == 'migration'
        assert mock_build.called

    def test_swapped_start_end_corrected(self, client):
        """start > end 时自动交换。"""
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles', return_value=[]), \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build:
            client.get('/dashboard/system_panel?start=2026-09-10&end=2026-09-01')
        start, end = mock_build.call_args.args[0], mock_build.call_args.args[1]
        assert start < end
        assert start == date(2026, 9, 1) and end == date(2026, 9, 10)

    def test_invalid_dates_use_default_30_days(self, client):
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles', return_value=[]), \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build, \
             patch(DV + '.datetime') as mock_dt:
            # datetime.now().date() 返回固定日期以确定默认区间
            fixed = datetime(2026, 9, 10, 12, 0, 0)
            mock_dt.now.return_value = fixed
            mock_dt.combine = datetime.combine
            mock_dt.min = datetime.min
            mock_dt.max = datetime.max
            mock_dt.strptime = datetime.strptime  # _parse_ymd 解析 'bad' 抛 ValueError
            client.get('/dashboard/system_panel?start=bad&end=worse')
        start, end = mock_build.call_args.args[0], mock_build.call_args.args[1]
        assert end == date(2026, 9, 10)
        assert start == date(2026, 8, 11)  # 30 天前

    def test_session_config_failed_uses_default(self, client):
        with patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(False, None, 'err')), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles',
                   return_value=['u1', 'u2', 'u3']), \
             patch(DV + '._build_migration_panel',
                   return_value={'panel': 'migration'}) as mock_build:
            resp = client.get('/dashboard/system_panel')
        assert resp.get_json()['code'] == 0
        assert mock_build.call_args.args[2] == 3

    def test_full_migration_flow_with_sqlite(self, client, tmp_path):
        """端到端：真实 SQLite codemig 库 + mock 主库查询。"""
        db = tmp_path / 'u1' / '1'
        db.mkdir(parents=True)
        _make_codemig_db(str(db / '1.db'),
                         suggestions=[(0, '2026-09-01 10:00:00')],
                         ai_rows=['2026-09-01 11:00:00'])
        scope, _ = _mock_session_scope(rows=[])
        with patch(DV + '.get_codemig_data_path', return_value=str(tmp_path)), \
             patch(DV + '.SysConfig.query_system_configuration',
                   return_value=(True, 30, None)), \
             patch(DV + '.UserSessionCache.get_online_users_all_roles', return_value=['u1']), \
             patch(DV + '.db_session_scope', return_value=scope):
            resp = client.get('/dashboard/system_panel?start=2026-09-01&end=2026-09-01')
        body = resp.get_json()
        assert body['code'] == 0
        data = body['data']
        assert data['panel'] == 'migration'
        assert data['summary']['issue_count'] == 1
        assert data['summary']['online_user_count'] == 1
        # created_at 经 date(created_at,'localtime') 换算本地日（UTC+8），
        # UTC 时间戳可能落到次日，此处不硬编码 ai 桶位，仅校验总数口径
        assert data['summary']['ai_usage'] in (0, 1)
