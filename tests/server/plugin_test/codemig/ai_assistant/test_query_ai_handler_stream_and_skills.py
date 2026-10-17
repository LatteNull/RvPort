"""query_ai_handler 其余函数单元测试：insert_generated_files / streaming / query handlers"""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

import common.ai_key.ai_key_utils as ai_key_utils
ai_key_utils.URL = "https://127.0.0.1:1234/model"
ai_key_utils.AIKey.update_api_key("key")
ai_key_utils.MODEL = "DeepSeek-1234"

from plugin.codemig.ai_assistant import query_ai_handler as qah
from plugin.codemig.ai_assistant.query_ai_handler import (
    insert_generated_files_to_database,
    generate_streaming_response,
    query_query_ai_suggestion_data,
    query_file_info,
    rescan_file,
    query_ai_suggestion_for_change,
    cancel_ai_suggestion_by_id,
    set_ai_score,
    get_ai_score,
    run_ut_test,
    query_project_migrate,
    generate_project_agent_response,
    truncate_suggestion_for_db,
)
from plugin.codemig.ai_assistant.ai_data_status import AiDataStatus

USER = 'tester'
DIR_ID = 3


@pytest.fixture
def dataroot(tmp_path, monkeypatch):
    base = tmp_path / 'codemigdata'
    (base / USER / str(DIR_ID) / 'changed').mkdir(parents=True)
    monkeypatch.setattr(qah, 'get_codemig_data_path', lambda: str(base))
    repo = base / USER / str(DIR_ID) / 'changed'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: repo)
    return base


# ---------------------------------------------------------------- insert_generated_files_to_database
def test_insert_generated_files_no_user(dataroot):
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(False, None)):
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    assert ok is False and 'user_id' in msg


def test_insert_generated_files_git_fail(dataroot):
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(True, 9)), \
         patch.object(qah, 'query_new_files_from_git',
                      return_value=(False, None)):
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    assert ok is False and 'git' in msg


def test_insert_generated_files_no_new(dataroot):
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(True, 9)), \
         patch.object(qah, 'query_new_files_from_git',
                      return_value=(True, [])):
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    assert ok is True and 'no new files' in msg


def test_insert_generated_files_ok(dataroot):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    (repo / 'sub').mkdir()
    (repo / 'sub' / 'new.c').write_text('int a;', encoding='utf-8')
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(True, 9)), \
         patch.object(qah, 'query_new_files_from_git',
                      return_value=(True, ['./sub/new.c'])), \
         patch.object(qah, 'query_file_by_path_from_database',
                      return_value=(True, None)), \
         patch.object(qah, 'save_generated_file_to_database',
                      return_value=(True, 11)) as save:
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    # inserted 只统计文件（目录 save 不计数）
    assert ok is True and 'inserted 1' in msg
    saved_paths = [c.args[3] for c in save.call_args_list]
    assert any(p.endswith('sub') for p in saved_paths)
    assert any(p.endswith('new.c') for p in saved_paths)


def test_insert_generated_files_existing(dataroot):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    (repo / 'new.c').write_text('x', encoding='utf-8')
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(True, 9)), \
         patch.object(qah, 'query_new_files_from_git',
                      return_value=(True, ['new.c'])), \
         patch.object(qah, 'query_file_by_path_from_database',
                      return_value=(True, 5)), \
         patch.object(qah, 'save_generated_file_to_database') as save:
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    assert ok is True and 'inserted 0' in msg
    save.assert_not_called()


def test_insert_generated_files_missing_on_disk(dataroot):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    with patch.object(qah, 'query_user_id_from_database',
                      return_value=(True, 9)), \
         patch.object(qah, 'query_new_files_from_git',
                      return_value=(True, ['ghost.c'])), \
         patch.object(qah, 'query_file_by_path_from_database',
                      return_value=(True, None)), \
         patch.object(qah, 'save_generated_file_to_database') as save:
        ok, msg = insert_generated_files_to_database(USER, DIR_ID, 1)
    assert ok is True and 'inserted 0' in msg
    save.assert_not_called()


# ---------------------------------------------------------------- generate_streaming_response
def _stream_response(lines):
    resp = MagicMock()
    resp.iter_lines.return_value = lines
    return resp


def _collect(gen):
    return [json.loads(c.decode('utf-8')) for c in gen]


def test_streaming_basic(dataroot):
    chunks = [
        b'data: ' + json.dumps(
            {'choices': [{'delta': {'content': 'hello'}}]}).encode(),
        b'data: [DONE]',
    ]
    out = _collect(generate_streaming_response(
        _stream_response(chunks), USER, DIR_ID, 'uuid1', start_time=1.0))
    values = [o['value'] for o in out if o.get('value')]
    assert 'hello' in values
    log = dataroot / USER / str(DIR_ID) / 'agent_uuid1.log'
    assert log.read_text(encoding='utf-8') == 'hello'


def test_streaming_reasoning_then_content(dataroot):
    chunks = [
        b'data: ' + json.dumps(
            {'choices': [{'delta': {'reasoning_content': 'R1'}}]}).encode(),
        b'data: ' + json.dumps(
            {'choices': [{'delta': {'content': 'C1'}}]}).encode(),
        b'data: [DONE]',
    ]
    out = _collect(generate_streaming_response(
        _stream_response(chunks), USER, DIR_ID, 'uuid2'))
    values = [o['value'] for o in out if o.get('value')]
    assert '<think/>' in values
    assert 'R1' in values
    assert '</think/>' in values
    assert 'C1' in values


def test_streaming_empty_and_bad_json(dataroot):
    chunks = [b'', b'data: not-json', b'data: {}']
    out = _collect(generate_streaming_response(
        _stream_response(chunks), USER, DIR_ID, 'uuid3'))
    assert all(o.get('value', '') == '' for o in out)


def test_streaming_error_path(dataroot):
    resp = MagicMock()
    resp.iter_lines.side_effect = requests.RequestException('boom')
    out = _collect(generate_streaming_response(
        resp, USER, DIR_ID, 'uuid4'))
    assert any(o['status'] == AiDataStatus.UNKNOWN_ERROR.value for o in out)


# ---------------------------------------------------------------- rescan_file
def test_rescan_file_no_record(dataroot):
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(False, None)):
        assert rescan_file(USER, DIR_ID, 1) is False


def test_rescan_file_missing_on_disk(dataroot):
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(True, ('/ghost.c', 0, 0, 1))):
        assert rescan_file(USER, DIR_ID, 1) is False


def test_rescan_file_is_dir(dataroot, tmp_path):
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(True, (str(tmp_path), 0, 0, 1))):
        assert rescan_file(USER, DIR_ID, 1) is False


def test_rescan_file_not_changed_source(dataroot, tmp_path):
    f = tmp_path / 'a.c'
    f.write_text('x', encoding='utf-8')
    # source='original' != 'changed' → False
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(True, (str(f), 'original', 0, 1))):
        assert rescan_file(USER, DIR_ID, 1) is False


def test_rescan_file_ok(dataroot, tmp_path):
    f = tmp_path / 'a.c'
    f.write_text('x', encoding='utf-8')
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(True, (str(f), 'changed', 0, 1))), \
         patch.object(qah, 'process_updated_file', return_value={}) as pu, \
         patch.object(qah, 'update_file_suggestion_to_database',
                      return_value=True):
        assert rescan_file(USER, DIR_ID, 1) is True
        pu.assert_called_once()


def test_rescan_file_update_fail(dataroot, tmp_path):
    f = tmp_path / 'a.c'
    f.write_text('x', encoding='utf-8')
    with patch.object(qah, 'query_file_info_from_database',
                      return_value=(True, (str(f), 'changed', 0, 1))), \
         patch.object(qah, 'process_updated_file', return_value={}), \
         patch.object(qah, 'update_file_suggestion_to_database',
                      return_value=False):
        assert rescan_file(USER, DIR_ID, 1) is False


# ---------------------------------------------------------------- query handlers
class FakeRequest:
    def __init__(self, user_id=1):
        self.user_id = user_id


def test_set_get_ai_score(dataroot):
    with patch.object(qah, 'set_ai_score_to_database',
                      return_value=(True, None)) as s:
        set_ai_score(USER, DIR_ID, 1, 2, 0.5)
        s.assert_called_once()
    with patch.object(qah, 'query_ai_score_from_database',
                      return_value=(True, 0.5)) as q:
        ret = get_ai_score(USER, DIR_ID, 1, 'uuid')
        assert ret == (True, 0.5)
        q.assert_called_once()


def test_cancel_ai_suggestion_ok(dataroot):
    result = MagicMock()
    result.returncode = 0
    result.stdout = 'ok'
    with patch('subprocess.run', return_value=result):
        ret = cancel_ai_suggestion_by_id(USER, DIR_ID, 'uuid')
    assert ret['code'] == 0


def test_cancel_ai_suggestion_container_gone(dataroot):
    result = MagicMock()
    result.returncode = 1
    result.stderr = 'Error: No such container: docker_uuid'
    with patch('subprocess.run', return_value=result):
        ret = cancel_ai_suggestion_by_id(USER, DIR_ID, 'uuid')
    assert ret['code'] == 0


def test_cancel_ai_suggestion_docker_down(dataroot):
    import subprocess as sp
    with patch('subprocess.run', side_effect=sp.TimeoutExpired('cmd', 30)):
        with pytest.raises(Exception):
            cancel_ai_suggestion_by_id(USER, DIR_ID, 'uuid')


# ---------------------------------------------------------------- _build_skill_runner handlers
def _req(user_id=1):
    return FakeRequest(user_id=user_id)


def _user_mock():
    user = MagicMock()
    user.user_name = USER
    user.role = 'user'
    return user


def test_skill_runner_no_uuid(dataroot):
    resp = run_ut_test({'user_name': USER}, _req())
    assert resp.status_code == 200
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.NO_REQUEST_UUID.value


def test_skill_runner_unknown_user(dataroot):
    with patch.object(qah, '_validate_user', return_value=None):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1'}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value


def test_skill_runner_no_files(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=(None, [])):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID},
            _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.UNKNOWN_ERROR.value
    assert '没有可用迁移产物' in body['value']


def test_skill_runner_no_api_key(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db',
                      return_value={'msg': 'no key'}):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID,
             'agent_model': 'm'}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value


def test_skill_runner_prompt_write_fail(dataroot, monkeypatch):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: repo)
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db',
                      return_value={'api_key': 'k', 'base_url': 'u',
                                    'model': 'm'}), \
         patch.object(qah, '_write_prompt_to_repo_for_commit',
                      return_value=False):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID,
             'agent_model': 'm'}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value
    assert '.prompt.txt' in body['value']


def test_skill_runner_resume_unavailable(dataroot, monkeypatch):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: repo)
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db',
                      return_value={'api_key': 'k', 'base_url': 'u',
                                    'model': 'm'}), \
         patch.object(qah, '_write_prompt_to_repo_for_commit',
                      return_value=True), \
         patch.object(qah, '_ensure_named_volume', lambda v: v), \
         patch.object(qah, '_maybe_prepare_resume', return_value=False):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID,
             'agent_model': 'm', '_resume': True}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value
    assert '无 pi 会话存档' in body['value']


def test_skill_runner_full(dataroot, monkeypatch):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: repo)
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db',
                      return_value={'api_key': 'k', 'base_url': 'u',
                                    'model': 'm'}), \
         patch.object(qah, '_ensure_named_volume', lambda v: v), \
         patch.object(qah, '_create_project_agent_process',
                      return_value='PROC') as cap, \
         patch.object(qah, 'create_ai_info_to_database'), \
         patch.object(qah, 'generate_project_agent_response',
                      return_value=iter(['ok'])):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID,
             'agent_model': 'm'}, _req())
    # uttest 走 inject_skill_via_repo=False
    kwargs = cap.call_args[1]
    assert kwargs['inject_skill'] is False
    body = resp.get_data()
    assert b'ok' in body


def test_skill_runner_exception(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      side_effect=RuntimeError('boom')), \
         patch.object(qah, 'save_intermediate_state_on_failure'), \
         patch.object(qah, 'update_ai_exception'):
        resp = run_ut_test(
            {'user_name': USER, 'request_uuid': 'u1', 'dir_id': DIR_ID},
            _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value


# ---------------------------------------------------------------- query_project_migrate
def test_project_migrate_no_uuid():
    resp = query_project_migrate({'user_name': USER}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body['status'] == AiDataStatus.NO_REQUEST_UUID.value


def test_project_migrate_unknown_user():
    with patch.object(qah, '_validate_user', return_value=None):
        resp = query_project_migrate(
            {'user_name': USER, 'request_uuid': 'u'}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body['status'] == AiDataStatus.BACKEND_ERROR.value


def test_project_migrate_no_prompt(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=(None, [])):
        resp = query_project_migrate(
            {'user_name': USER, 'request_uuid': 'u', 'dir_id': DIR_ID}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body['status'] == AiDataStatus.UNKNOWN_ERROR.value


def test_project_migrate_no_api_key(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db', return_value=None):
        resp = query_project_migrate(
            {'user_name': USER, 'request_uuid': 'u', 'dir_id': DIR_ID,
             'agent_model': 'm'}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body['status'] == AiDataStatus.BACKEND_ERROR.value


def test_project_migrate_full(dataroot, monkeypatch):
    repo = dataroot / USER / str(DIR_ID) / 'changed'
    monkeypatch.setattr(qah, 'get_repo_path', lambda u, d: repo)
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      return_value=('C', [{'file_id': 1}])), \
         patch.object(qah, 'get_agent_config_from_db',
                      return_value={'api_key': 'k', 'base_url': 'u',
                                    'model': 'm'}), \
         patch.object(qah, '_ensure_named_volume', lambda v: v), \
         patch.object(qah, '_create_project_agent_process',
                      return_value='PROC') as cap, \
         patch.object(qah, 'create_ai_info_to_database'), \
         patch.object(qah, 'generate_project_agent_response',
                      return_value=iter(['done'])):
        resp = query_project_migrate(
            {'user_name': USER, 'request_uuid': 'u', 'dir_id': DIR_ID,
             'agent_model': 'm'}, _req())
    kwargs = cap.call_args[1]
    assert kwargs['skill_name'] == 'projectmigrate'
    assert b'done' in resp.get_data()


def test_project_migrate_exception(dataroot):
    with patch.object(qah, '_validate_user', return_value=_user_mock()), \
         patch.object(qah, '_build_projectmigrate_prompt',
                      side_effect=ValueError('bad')), \
         patch.object(qah, 'save_intermediate_state_on_failure'), \
         patch.object(qah, 'update_ai_exception'):
        resp = query_project_migrate(
            {'user_name': USER, 'request_uuid': 'u', 'dir_id': DIR_ID}, _req())
    body = json.loads(resp.get_data().decode('utf-8'))
    assert body["status"] == AiDataStatus.BACKEND_ERROR.value


# ---------------------------------------------------------------- generate_project_agent_response
def test_project_agent_response_interrupted(dataroot, monkeypatch):
    def gen():
        yield b'x'
        raise GeneratorExit()
    proc = MagicMock()
    with patch.object(qah, 'parse_agent_output', return_value=gen()), \
         patch.object(qah, 'cleanup_process'), \
         patch.object(qah, 'force_commit_marker') as fc, \
         patch.object(qah, 'update_ai_result') as ur:
        out = list(generate_project_agent_response(
            proc, USER, DIR_ID, [{'file_id': 1}], 'uuid9', 1.0))
        fc.assert_called_once()
        ur.assert_called_once()
        args = ur.call_args[0]
        assert args[-1] == 'interrupted'
        assert '用户已停止' in args[-2]


def test_project_agent_response_completed(dataroot, monkeypatch):
    def gen():
        yield json.dumps({'value': 'V1'}).encode()
    proc = MagicMock()
    with patch.object(qah, 'parse_agent_output', return_value=gen()), \
         patch.object(qah, 'cleanup_process'), \
         patch.object(qah, 'force_commit_marker'), \
         patch.object(qah, 'insert_generated_files_to_database',
                      return_value=(True, None)), \
         patch.object(qah, 'update_ai_result') as ur, \
         patch.object(qah, '_rescan_all_files') as rs:
        out = list(generate_project_agent_response(
            proc, USER, DIR_ID, [{'file_id': 7}], 'uuid10', 1.0,
            agent_model='m1', key_prefix='sk-'))
        rs.assert_called_once()
        args = ur.call_args[0]
        assert args[-1] == 'completed'
        assert args[-2] == 'V1'
        # 日志文件写过后被删除
        log = dataroot / USER / str(DIR_ID) / 'agent_uuid10.log'
        assert not log.exists()


def test_project_agent_response_oserror(dataroot):
    proc = MagicMock()
    with patch.object(qah, 'parse_agent_output',
                      side_effect=OSError('disk gone')), \
         patch.object(qah, 'cleanup_process'), \
         patch.object(qah, 'force_commit_marker'), \
         patch.object(qah, 'update_ai_result'):
        with pytest.raises(OSError):
            list(generate_project_agent_response(
                proc, USER, DIR_ID, [], 'uuid11', 1.0))

