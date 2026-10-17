"""query_ai_handler 一键迁移（projectmigrate）系列单元测试

覆盖 _query_* helpers、_build_projectmigrate_prompt、命名卷 helpers、
skill 注入 helpers、manual suggestion handlers、回退/历史/补丁 handlers。
"""
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from plugin.codemig.ai_assistant import query_ai_handler as qah
from plugin.codemig.ai_assistant.query_ai_handler import (
    _migrate_named_volume_name,
    _ensure_named_volume,
    _remove_named_volume,
    _resumable_status_for_volume,
    _resumable_status_all_stages,
    _maybe_prepare_resume,
    _resolve_skill_source_path,
    _ensure_skill_in_repo,
    _enforce_chinese_output,
    _write_skill_to_repo,
    _write_prompt_to_repo_for_commit,
    _query_file_path_by_file_id,
    _read_code_range,
    insert_manual_suggestion_handler,
    delete_manual_suggestion_handler,
    list_manual_suggestions_by_dir_handler,
    rollback_project_migrate_handler,
    list_project_migrate_history_handler,
    generate_project_patch_handler,
    _query_all_files_with_suggestions,
    _query_suggestions_for_file,
    _query_manual_suggestions_for_projectmigrate,
    _query_existing_arch_for_missing_file,
    _build_projectmigrate_prompt,
    _rescan_all_files,
    save_intermediate_state_on_failure,
    force_commit_marker,
)

USER = 'tester'
DIR_ID = 3


@pytest.fixture
def codemig_root(tmp_path, monkeypatch):
    """构造 {data}/tester/3/{3.db, changed/} 并把公共数据路径指过去"""
    import common.public.public as pub
    base = tmp_path / 'codemigdata'
    user_dir = base / USER / str(DIR_ID)
    repo = user_dir / 'changed'
    repo.mkdir(parents=True)
    # query_ai_handler / codemig_common_utils / common_git 各自持有导入副本，都替换
    monkeypatch.setattr(pub, 'CODEMIG_DATA_PATH', str(base))
    import plugin.codemig.ai_assistant.query_ai_handler as qh
    monkeypatch.setattr(qh, 'get_codemig_data_path', lambda: str(base))
    import plugin.codemig.codemig_common.codemig_common_utils as ccu
    monkeypatch.setattr(ccu, 'get_codemig_data_path', lambda: str(base))
    import plugin.codemig.codemig_common.common_git as cg
    monkeypatch.setattr(cg, 'get_codemig_data_path', lambda: str(base))
    monkeypatch.setattr(qah, 'get_repo_path',
                        lambda u, d: Path(str(base)) / u / str(d) / 'changed')
    return base, user_dir, repo


def _make_db(user_dir, with_suggestions=True, with_manual=False,
             with_missing=False):
    """按 common_sql.py 真实 DDL 建 codemig 用户库，返回 db_path"""
    db_path = user_dir / f'{DIR_ID}.db'
    conn = sqlite3.connect(str(db_path))
    conn.executescript('''
        CREATE TABLE codemig_task_directory_file (
            user_id INTEGER NOT NULL, dir_id INTEGER NOT NULL,
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL DEFAULT 0,
            file_path TEXT NOT NULL,
            has_removed INTEGER NOT NULL DEFAULT 0,
            file_source TEXT NOT NULL,
            is_file INTEGER NOT NULL DEFAULT 1,
            source_file_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE codemig_task_directory_file_suggestion (
            file_id INTEGER NOT NULL,
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            append_or_replace INTEGER NOT NULL,
            start_line_number INTEGER NOT NULL,
            end_line_number INTEGER NOT NULL,
            suggestion TEXT NOT NULL,
            code_too_long INTEGER, code TEXT,
            ignored INTEGER NOT NULL DEFAULT 0,
            is_manual INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE codemig_task_directory_existing_architecture (
            file_id INTEGER NOT NULL,
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            architecture_path TEXT NOT NULL,
            type INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    ''')
    if with_suggestions:
        conn.execute(
            "INSERT INTO codemig_task_directory_file(user_id, dir_id, file_path,"
            " type, file_source) VALUES(9, ?, 'changed/src/a.c', 0, 'changed')",
            (DIR_ID,))
        conn.execute(
            "INSERT INTO codemig_task_directory_file_suggestion("
            "file_id, type, append_or_replace, start_line_number,"
            " end_line_number, suggestion)"
            " VALUES(1, 1, 0, 10, 20, 'use RVV')")
    if with_manual:
        cur = conn.execute(
            "INSERT INTO codemig_task_directory_file(user_id, dir_id, file_path,"
            " type, file_source) VALUES(9, ?, 'changed/src/b.c', 0, 'changed')",
            (DIR_ID,))
        conn.execute(
            "INSERT INTO codemig_task_directory_file_suggestion("
            "file_id, type, append_or_replace, is_manual, start_line_number,"
            " end_line_number, suggestion)"
            " VALUES(?, 2, 2, 1, 5, 8, 'manual pick')", (cur.lastrowid,))
    if with_missing:
        # type=2 表示缺失文件（file_id 自增为 2 或 3，按是否含 manual 行）；
        # 关联 existing_architecture 触发 missing 查询
        cur = conn.execute(
            "INSERT INTO codemig_task_directory_file(user_id, dir_id, file_path,"
            " type, file_source) VALUES(9, ?, 'changed/arm/lib.so', 2, 'changed')",
            (DIR_ID,))
        conn.execute(
            "INSERT INTO codemig_task_directory_existing_architecture("
            "file_id, architecture_path, type) VALUES(?, 'x86/lib.so', 0)",
            (cur.lastrowid,))
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------- DB 查询 helpers
def test_query_all_files_with_suggestions_ok(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    status, rows = _query_all_files_with_suggestions(USER, DIR_ID)
    assert status is True
    assert rows == [(1, 'changed/src/a.c')]


def test_query_all_files_with_suggestions_no_db(codemig_root):
    _, user_dir, _ = codemig_root
    status, rows = _query_all_files_with_suggestions(USER, DIR_ID)
    assert status is False and rows == []


def test_query_all_files_with_suggestions_sql_error(codemig_root):
    _, user_dir, _ = codemig_root
    db = _make_db(user_dir)
    conn = sqlite3.connect(str(db))
    conn.execute('DROP TABLE codemig_task_directory_file')
    conn.commit()
    conn.close()
    status, rows = _query_all_files_with_suggestions(USER, DIR_ID)
    assert status is False and rows == []


def test_query_suggestions_for_file(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    status, rows = _query_suggestions_for_file(USER, DIR_ID, 1)
    assert status is True
    assert rows[0][:3] == (10, 20, 1)
    # 不存在的文件 / 缺 db
    status, rows = _query_suggestions_for_file(USER, DIR_ID, 999)
    assert status is True and rows == []
    # db 不存在（换一个没建库的 dir）
    status, rows = _query_suggestions_for_file(USER, 404, 1)
    assert status is False and rows == []


def test_query_manual_suggestions(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir, with_manual=True)
    rows = _query_manual_suggestions_for_projectmigrate(USER, DIR_ID)
    assert rows == [(2, 'changed/src/b.c', 5, 8)]
    assert _query_manual_suggestions_for_projectmigrate(USER, 404) == []


def test_query_existing_arch_for_missing_file(codemig_root):
    _, user_dir, _ = codemig_root
    db = _make_db(user_dir, with_missing=True)
    conn = sqlite3.connect(str(db))
    fid = conn.execute(
        'SELECT file_id FROM codemig_task_directory_file WHERE type=2'
    ).fetchone()[0]
    conn.close()
    status, rows = _query_existing_arch_for_missing_file(USER, DIR_ID, fid)
    assert status is True
    assert rows == [('x86/lib.so', 0)]
    status, rows = _query_existing_arch_for_missing_file(USER, 404, 3)
    assert status is False and rows == []


# ---------------------------------------------------------------- _build_projectmigrate_prompt
def test_build_prompt_no_files(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID)
    # 有建议文件
    assert content is not None
    assert file_list == [{'file_id': 1, 'file_path': 'changed/src/a.c'}]
    scan = json.loads((codemig_root[2] / 'scan_result.json').read_text(encoding='utf-8'))
    assert scan['suggestion_class'][0]['start_line'] == 10
    # skill 文件也写入
    assert (codemig_root[2] / '.skills' / 'projectmigrate' / 'SKILL.md').exists()


def test_build_prompt_empty_db(codemig_root):
    _, user_dir, _ = codemig_root
    # 空 db：无 suggestion_class → None
    _make_db(user_dir, with_suggestions=False)
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is None and file_list == []


def test_build_prompt_query_fail(codemig_root):
    # db 不存在
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is None and file_list == []


def test_build_prompt_manual_from_db(codemig_root, monkeypatch):
    _, user_dir, _ = codemig_root
    _make_db(user_dir, with_manual=True, with_suggestions=False)
    # query_missing_files_sql 函数内 import，patch 其源模块的数据路径
    import plugin.codemig.codemig_task_manager.query_processor as qp
    monkeypatch.setattr(qp, 'get_codemig_data_path', lambda: str(codemig_root[0]))
    monkeypatch.setattr(qp, 'get_database_path',
                        lambda u, i: Path(str(codemig_root[0])) / u / str(i) / f'{i}.db')
    # 手动选中兜底：manual_items=None 时从 DB 读取
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is not None
    scan = json.loads((codemig_root[2] / 'scan_result.json').read_text(encoding='utf-8'))
    manual = [s for s in scan['suggestion_class'] if s['class_type'] == 'manual_selection']
    assert manual and manual[0]['start_line'] == 5


def test_build_prompt_manual_items_param(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    manual = [{'file_path': './changed/src/a.c', 'start_line': 1, 'end_line': 2},
              {'file_path': '', 'start_line': 1, 'end_line': 2}]  # 第二条缺路径被跳过
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID, manual_items=manual)
    assert content is not None
    scan = json.loads((codemig_root[2] / 'scan_result.json').read_text(encoding='utf-8'))
    manuals = [s for s in scan['suggestion_class'] if s['class_type'] == 'manual_selection']
    assert len(manuals) == 1


def test_build_prompt_missing_files(codemig_root, monkeypatch):
    _, user_dir, _ = codemig_root
    _make_db(user_dir, with_suggestions=True, with_missing=True)
    import plugin.codemig.codemig_task_manager.query_processor as qp
    monkeypatch.setattr(qp, 'get_codemig_data_path', lambda: str(codemig_root[0]))
    monkeypatch.setattr(qp, 'get_database_path',
                        lambda u, i: Path(str(codemig_root[0])) / u / str(i) / f'{i}.db')
    content, _ = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is not None
    scan = json.loads((codemig_root[2] / 'scan_result.json').read_text(encoding='utf-8'))
    assert scan['missing_class_count'] == 1
    entry = scan['missing_class'][0]
    assert entry['class_type'] == 'missing_class'
    assert entry['is_file'] is True
    assert '/app/' in entry['existing_arch_paths'][0]


def test_build_prompt_prompt_to_write(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    content, _ = _build_projectmigrate_prompt(
        USER, DIR_ID, prompt_to_write='PROMPT-CONTENT')
    assert content is not None
    assert (codemig_root[2] / '.prompt.txt').read_text(encoding='utf-8') == 'PROMPT-CONTENT'


def test_build_prompt_unknown_solver_type(codemig_root):
    _, user_dir, _ = codemig_root
    db = _make_db(user_dir)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE codemig_task_directory_file_suggestion SET type=99 WHERE file_id=1")
    conn.commit()
    conn.close()
    content, _ = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is not None
    scan = json.loads((codemig_root[2] / 'scan_result.json').read_text(encoding='utf-8'))
    assert scan['suggestion_class'][0]['solver_description'] == '未知'


def test_build_prompt_write_fail(codemig_root, monkeypatch):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    # repo_path 变为只读位置：写 scan_result.json 失败
    monkeypatch.setattr(qah, 'get_repo_path',
                        lambda u, d: codemig_root[2] / 'nope' / 'x')
    (codemig_root[2] / 'nope').mkdir()
    content, file_list = _build_projectmigrate_prompt(USER, DIR_ID)
    assert content is None and file_list == []


# ---------------------------------------------------------------- 命名卷 helpers
def test_migrate_named_volume_name():
    name = _migrate_named_volume_name('张三$恶意', 5, 'uttest')
    assert name.startswith('codemig_migrate_ut_')
    assert '$' not in name and name.endswith('_5')
    # 未知 stage 用默认前缀
    assert _migrate_named_volume_name('u', 1, 'unknown').startswith('codemig_migrate_')
    # 空用户名回退 'u'
    assert _migrate_named_volume_name('', 1, 'uttest').split('_')[-2] == 'u'


def test_ensure_named_volume_existing():
    with patch('subprocess.run') as run:
        run.return_value = MagicMock(returncode=0)
        assert _ensure_named_volume('vol1') == 'vol1'
        run.assert_called_once()


def test_ensure_named_volume_create():
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[2])
        # inspect 用 check=True：非零抛 CalledProcessError 走 create 分支
        if cmd[2] == 'inspect':
            raise subprocess.CalledProcessError(1, cmd)
        return MagicMock(returncode=0)

    with patch('subprocess.run', side_effect=fake_run):
        assert _ensure_named_volume('vol2') == 'vol2'
    assert calls == ['inspect', 'create']


def test_ensure_named_volume_create_fail():
    def fake_run(cmd, **kwargs):
        if cmd[2] == 'inspect':
            raise subprocess.CalledProcessError(1, cmd)
        raise RuntimeError('docker down')

    with patch('subprocess.run', side_effect=fake_run):
        with pytest.raises(RuntimeError):
            _ensure_named_volume('vol3')


def test_remove_named_volume():
    with patch('subprocess.run') as run:
        _remove_named_volume('vol')
        run.assert_called_once()


def test_remove_named_volume_error():
    with patch('subprocess.run', side_effect=OSError('boom')):
        _remove_named_volume('vol')  # 不抛


def test_resumable_status_available():
    with patch('subprocess.run', return_value=MagicMock(returncode=0)):
        assert _resumable_status_for_volume('v') == {'available': True}


def test_resumable_status_missing():
    with patch('subprocess.run', return_value=MagicMock(returncode=1)):
        assert _resumable_status_for_volume('v') == {'available': False}


def test_resumable_status_timeout():
    with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('cmd', 3)):
        assert _resumable_status_for_volume('v') == {'available': False}


def test_resumable_status_no_docker():
    with patch('subprocess.run', side_effect=FileNotFoundError()):
        assert _resumable_status_for_volume('v') == {'available': False}


def test_resumable_status_unexpected_error():
    with patch('subprocess.run', side_effect=ValueError('bad')):
        assert _resumable_status_for_volume('v') == {'available': False}


def test_resumable_status_all_stages():
    with patch.object(qah, '_resumable_status_for_volume',
                      side_effect=lambda vol: {'available': '_ut_' in vol}):
        out = _resumable_status_all_stages('u', 1)
    assert set(out) == {'projectmigrate', 'uttest'}
    assert out['uttest'] == {'available': True}


def test_maybe_prepare_resume_ok():
    with patch.object(qah, '_resumable_status_for_volume',
                      return_value={'available': True}):
        assert _maybe_prepare_resume('u', 1, 'uttest', 'v') is True


def test_maybe_prepare_resume_unavailable():
    with patch.object(qah, '_resumable_status_for_volume',
                      return_value={'available': False}):
        assert _maybe_prepare_resume('u', 1, 'uttest', 'v') is False


# ---------------------------------------------------------------- skill helpers
def test_resolve_skill_source_path_missing(monkeypatch):
    monkeypatch.setattr(qah, '_AGENT_ASSETS_ROOT', '/nonexistent-root')
    assert _resolve_skill_source_path('uttest') is None


def test_resolve_skill_source_path_found(monkeypatch, tmp_path):
    skill = tmp_path / 'x86' / '.pi' / 'agent' / 'skills' \
        / 'myskill' / 'SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('x', encoding='utf-8')
    monkeypatch.setattr(qah, '_AGENT_ASSETS_ROOT', str(tmp_path))
    # host 是 x86_64 时优先 x86
    found = _resolve_skill_source_path('myskill')
    assert found is None or found == str(skill)


def test_ensure_skill_in_repo_no_source(monkeypatch):
    monkeypatch.setattr(qah, '_resolve_skill_source_path', lambda name: None)
    assert _ensure_skill_in_repo('u', 1, 'uttest') is False


def test_ensure_skill_in_repo_ok(codemig_root, monkeypatch):
    _, user_dir, repo = codemig_root
    src = user_dir / 'SKILL.src.md'
    src.write_text('---\nname: x\n---\nbody', encoding='utf-8')
    monkeypatch.setattr(qah, '_resolve_skill_source_path', lambda name: str(src))
    assert _ensure_skill_in_repo(USER, DIR_ID, 'uttest') is True
    content = (repo / '.skills' / 'uttest' / 'SKILL.md').read_text(encoding='utf-8')
    assert '语言守则' in content
    assert 'body' in content


def test_ensure_skill_in_repo_get_repo_fail(codemig_root, monkeypatch):
    monkeypatch.setattr(qah, '_resolve_skill_source_path', lambda name: '/x/y')

    def _fail(u, d):
        raise RuntimeError('no repo')
    monkeypatch.setattr(qah, 'get_repo_path', _fail)
    assert _ensure_skill_in_repo(USER, DIR_ID, 'uttest') is False


def test_enforce_chinese_output_with_yaml():
    out = _enforce_chinese_output('uttest', '---\nname: x\n---\nWORKFLOW')
    assert out.index('---') < out.index('语言守则') < out.index('WORKFLOW')


def test_enforce_chinese_output_no_yaml():
    out = _enforce_chinese_output('uttest', 'WORKFLOW')
    assert out.startswith('> **⚠️ 语言守则')
    assert out.rstrip().endswith('WORKFLOW')


def test_write_skill_to_repo_prefer_source(codemig_root, monkeypatch):
    _, user_dir, repo = codemig_root
    monkeypatch.setattr(qah, '_ensure_skill_in_repo', lambda *a: True)
    assert _write_skill_to_repo(USER, DIR_ID, 'uttest', 'ignored') is True


def test_write_skill_to_repo_fallback_content(codemig_root, monkeypatch):
    _, user_dir, repo = codemig_root
    monkeypatch.setattr(qah, '_ensure_skill_in_repo', lambda *a: False)
    ok = _write_skill_to_repo(USER, DIR_ID, 'proj', 'SKILL {platform}')
    assert ok is True
    content = (repo / '.skills' / 'proj' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'Linux' in content


def test_write_skill_to_repo_no_content(codemig_root, monkeypatch):
    monkeypatch.setattr(qah, '_ensure_skill_in_repo', lambda *a: False)
    assert _write_skill_to_repo(USER, DIR_ID, 'proj', '') is False


def test_write_skill_to_repo_no_repo(codemig_root, monkeypatch):
    monkeypatch.setattr(qah, '_ensure_skill_in_repo', lambda *a: False)

    def _fail(u, d):
        raise RuntimeError('x')
    monkeypatch.setattr(qah, 'get_repo_path', _fail)
    assert _write_skill_to_repo(USER, DIR_ID, 'proj', 'c') is False


def test_write_skill_to_repo_write_fail(codemig_root, monkeypatch):
    _, user_dir, _ = codemig_root
    monkeypatch.setattr(qah, '_ensure_skill_in_repo', lambda *a: False)
    # open 失败：repo 指向一个文件路径，makedirs 会 OSError
    (codemig_root[2] / 'blockfile').write_text('x', encoding='utf-8')
    monkeypatch.setattr(qah, 'get_repo_path',
                        lambda u, d: codemig_root[2] / 'blockfile' / 'sub')
    assert _write_skill_to_repo(USER, DIR_ID, 'proj', 'c') is False


# ---------------------------------------------------------------- _write_prompt_to_repo_for_commit
def test_write_prompt_to_repo_ok(tmp_path):
    assert _write_prompt_to_repo_for_commit(str(tmp_path), 'hi', 'uuid', '阶段') is True
    assert (tmp_path / '.prompt.txt').read_text(encoding='utf-8') == 'hi'


def test_write_prompt_to_repo_fail(tmp_path):
    with patch('builtins.open', side_effect=OSError('ro')):
        assert _write_prompt_to_repo_for_commit(str(tmp_path), 'hi', 'u', 's') is False


# ---------------------------------------------------------------- manual suggestion handlers
def test_insert_manual_suggestion(codemig_root):
    _, user_dir, repo = codemig_root
    _make_db(user_dir)
    src = repo / 'src' / 'a.c'
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('\n'.join(f'line{i}' for i in range(1, 31)), encoding='utf-8')
    ret = insert_manual_suggestion_handler(USER, DIR_ID, 1, 2, 4, 'manual', 2)
    assert ret == {'code': 0, 'inserted': 1}
    # 幂等：再次插入同样范围
    ret = insert_manual_suggestion_handler(USER, DIR_ID, 1, 2, 4, 'manual', 2)
    assert ret == {'code': 0, 'inserted': 0}


def test_insert_manual_suggestion_no_db(codemig_root):
    ret = insert_manual_suggestion_handler(USER, DIR_ID, 1, 1, 2, 'm', 2)
    assert ret['code'] == -1


def test_insert_manual_suggestion_too_long(codemig_root):
    _, user_dir, repo = codemig_root
    _make_db(user_dir)
    src = repo / 'src' / 'a.c'
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('\n'.join(f'l{i}' for i in range(1, 101)), encoding='utf-8')
    # file 表里 file_path 是相对值 changed/src/a.c，读取失败时 code=''
    ret = insert_manual_suggestion_handler(USER, DIR_ID, 1, 1, 100, 'm', 2)
    assert ret == {'code': 0, 'inserted': 1}
    conn = sqlite3.connect(str(user_dir / f'{DIR_ID}.db'))
    code, too_long = conn.execute(
        'SELECT code, code_too_long FROM '
        'codemig_task_directory_file_suggestion WHERE is_manual=1').fetchone()
    conn.close()
    assert code == '' and too_long == 1


def test_delete_manual_suggestion(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir, with_manual=True)
    ret = delete_manual_suggestion_handler(USER, DIR_ID, 2, 5, 8)
    assert ret == {'code': 0, 'deleted': 1}
    ret = delete_manual_suggestion_handler(USER, DIR_ID, 2, 5, 8)
    assert ret == {'code': 0, 'deleted': 0}


def test_delete_manual_suggestion_no_db(codemig_root):
    assert delete_manual_suggestion_handler(USER, DIR_ID, 1, 1, 2)['code'] == -1


def test_list_manual_suggestions(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir, with_manual=True)
    ret = list_manual_suggestions_by_dir_handler(USER, DIR_ID)
    assert ret['code'] == 0
    assert ret['selections'][0]['file_id'] == 2
    assert list_manual_suggestions_by_dir_handler(USER, 404)['code'] == -1


def test_query_file_path_by_file_id(codemig_root):
    _, user_dir, _ = codemig_root
    _make_db(user_dir)
    assert _query_file_path_by_file_id(USER, DIR_ID, 1) == 'changed/src/a.c'
    assert _query_file_path_by_file_id(USER, DIR_ID, 999) is None
    assert _query_file_path_by_file_id(USER, 404, 1) is None


def test_read_code_range(tmp_path):
    f = tmp_path / 'a.c'
    f.write_text('l1\nl2\nl3\n', encoding='utf-8')
    text, flag = _read_code_range(str(f), 2, 3)
    assert text == 'l2\nl3\n'
    assert flag == 0
    # 超长
    text, flag = _read_code_range(str(f), 1, 100)
    assert text is None and flag == 1
    # 文件不存在
    text, flag = _read_code_range(str(tmp_path / 'nope'), 1, 2)
    assert text == '' and flag == 1


# ---------------------------------------------------------------- 回退/历史/补丁
def test_rollback_no_repo(codemig_root):
    # get_repo_path 被 fixture 指到已存在的 changed 目录 → 走 git.Repo 打开分支
    import git.exc as git_exc
    with patch('git.Repo', side_effect=git_exc.InvalidGitRepositoryError('x')):
        ret = rollback_project_migrate_handler(USER, DIR_ID)
    assert ret['code'] == 1
    assert '未初始化' in ret['msg']


def test_rollback_path_missing(codemig_root, monkeypatch):
    monkeypatch.setattr(qah, 'get_repo_path',
                        lambda u, d: codemig_root[0] / 'no-such-dir')
    ret = rollback_project_migrate_handler(USER, DIR_ID)
    assert ret['code'] == 1
    assert '不存在' in ret['msg']


def test_rollback_no_git(codemig_root):
    # changed 目录存在但不是 git 仓库
    with patch('git.Repo', side_effect=__import__(
            'git.exc', fromlist=['InvalidGitRepositoryError'])
            .InvalidGitRepositoryError('x')):
        ret = rollback_project_migrate_handler(USER, DIR_ID)
    assert ret['code'] == 1


def test_rollback_with_hash(codemig_root):
    repo = MagicMock()
    repo.head.commit.hexsha = 'aa11bb22'
    with patch('git.Repo', return_value=repo), \
         patch.object(qah, 'reset_to_commit', return_value=(True, 'abc1234')) as m:
        ret = rollback_project_migrate_handler(USER, DIR_ID, target_hash='abc1234')
    assert ret['code'] == 0
    m.assert_called_once()


def test_rollback_reset_fail(codemig_root):
    repo = MagicMock()
    repo.head.commit.hexsha = 'aa11bb22'
    with patch('git.Repo', return_value=repo), \
         patch.object(qah, 'reset_to_commit', return_value=(False, 'git error')):
        ret = rollback_project_migrate_handler(USER, DIR_ID, target_hash='abc')
    assert ret['code'] == 1


def test_rollback_auto_find_commit(codemig_root):
    commit = MagicMock()
    commit.hexsha = 'deadbeef'
    commit.message = 'Save type:ai stage:before src:x reason:y'
    repo = MagicMock()
    repo.iter_commits.return_value = [commit]
    with patch('git.Repo', return_value=repo), \
         patch.object(qah, 'reset_to_commit', return_value=(True, 'deadbeef')):
        ret = rollback_project_migrate_handler(USER, DIR_ID)
    assert ret['code'] == 0 and 'deadbeef' in ret['msg']


def test_rollback_auto_not_found(codemig_root):
    repo = MagicMock()
    repo.iter_commits.return_value = []
    with patch('git.Repo', return_value=repo):
        ret = rollback_project_migrate_handler(USER, DIR_ID)
    assert ret['code'] == 1


def test_list_project_history_ok():
    with patch('plugin.codemig.ai_assistant.query_ai_handler.list_project_history',
               return_value=(True, [{'hash': 'a'}])):
        ret = list_project_migrate_history_handler('u', 1)
    assert ret == {'code': 0, 'data': [{'hash': 'a'}]}


def test_list_project_history_fail():
    with patch('plugin.codemig.ai_assistant.query_ai_handler.list_project_history',
               return_value=(False, 'err')):
        ret = list_project_migrate_history_handler('u', 1)
    assert ret['code'] == 1


def test_generate_patch_handler_empty():
    assert generate_project_patch_handler('u', 1, '')['code'] == 1


def test_generate_patch_handler_ok():
    with patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between',
               return_value=(True, 'diff --git')):
        ret = generate_project_patch_handler('u', 1, 'h1', 'h2')
    assert ret == {'code': 0, 'data': 'diff --git'}


def test_generate_patch_handler_fail():
    with patch('plugin.codemig.ai_assistant.query_ai_handler.generate_patch_between',
               return_value=(False, 'boom')):
        ret = generate_project_patch_handler('u', 1, 'h1')
    assert ret['code'] == 1


# ---------------------------------------------------------------- rescan / commit
def test_rescan_all_files(codemig_root):
    with patch.object(qah, 'rescan_file') as rf:
        _rescan_all_files('u', 1, [{'file_id': 1}, {'file_id': 2}])
    assert rf.call_count == 2


def test_rescan_all_files_swallows(codemig_root):
    with patch.object(qah, 'rescan_file', side_effect=RuntimeError('x')):
        _rescan_all_files('u', 1, [{'file_id': 1}])  # 不抛


def test_save_intermediate_state_no_git(codemig_root, monkeypatch):
    # get_repo_path 指向非 git 目录 → InvalidGitRepositoryError 分支
    import git as gitmod
    monkeypatch.setattr(qah, 'get_repo_path',
                        lambda u, d: codemig_root[2])
    save_intermediate_state_on_failure('u', 1)  # 目录非 git 仓库，吞掉异常


def test_force_commit_marker_ok(codemig_root, monkeypatch):
    repo = MagicMock()
    repo.head.commit.hexsha = 'aa11bb22'
    repo.head.commit.author = 'a'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: codemig_root[2])
    with patch('git.Repo', return_value=repo):
        sha = force_commit_marker('u', 1, 'stage-end-success')
    assert sha == 'aa11bb22'
    # 后端路径用 add -A
    repo.git.add.assert_called_once_with(all=True)


def test_force_commit_marker_boundary_add_u(codemig_root, monkeypatch):
    repo = MagicMock()
    repo.head.commit.hexsha = 'cc33'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: codemig_root[2])
    with patch('git.Repo', return_value=repo):
        sha = force_commit_marker('u', 1, 'user-click-run', src='codemig-boundary')
    assert sha == 'cc33'
    repo.git.add.assert_called_once_with('-u')


def test_force_commit_marker_failure(codemig_root, monkeypatch):
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: codemig_root[2])
    with patch('git.Repo', side_effect=RuntimeError('boom')):
        assert force_commit_marker('u', 1, 'x') is None
