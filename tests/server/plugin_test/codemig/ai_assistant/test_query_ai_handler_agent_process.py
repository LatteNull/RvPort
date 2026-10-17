"""query_ai_handler Agent 进程构造 / docker 命令拼装 单元测试"""
import os
from unittest.mock import patch, MagicMock

import pytest

from plugin.codemig.ai_assistant import query_ai_handler as qah
from plugin.codemig.ai_assistant.query_ai_handler import (
    _resolve_agent_credentials,
    _load_proxy_settings,
    _build_agent_cmd_and_env,
    _api_env_args,
    _pi_base_env_args,
    _proxy_env_args,
    _build_chown_tail,
    _assemble_docker_run_cmd,
    _spawn_docker_agent,
    create_agent_process,
    _create_project_agent_process,
    truncate_suggestion_for_db,
    close_unclosed_details,
    _indent_fences_in_chunk,
    _line_value_of,
    _replace_line_value,
)

GOOD_CFG = {'api_key': 'sk-1', 'base_url': 'http://b', 'model': 'm1'}


# ---------------------------------------------------------------- _resolve_agent_credentials
def test_resolve_credentials_ok():
    creds, err = _resolve_agent_credentials(GOOD_CFG)
    assert err is None and creds['api_key'] == 'sk-1'


def test_resolve_credentials_missing_key():
    creds, err = _resolve_agent_credentials({'model': 'm'})
    assert creds is None and err['code'] == -1


# ---------------------------------------------------------------- _load_proxy_settings
def test_load_proxy_settings(monkeypatch):
    monkeypatch.setattr(
        qah.SysConfig, 'query_system_configuration',
        staticmethod(lambda key: (True, f'val-{key}', None)))
    proxy = _load_proxy_settings()
    assert proxy['https_proxy'].startswith('val-')
    assert 'https_proxy' in os.environ


def test_load_proxy_settings_missing(monkeypatch):
    monkeypatch.setattr(
        qah.SysConfig, 'query_system_configuration',
        staticmethod(lambda key: (False, None, None)))
    proxy = _load_proxy_settings()
    assert proxy == {'https_proxy': '', 'http_proxy': '', 'no_proxy': ''}


# ---------------------------------------------------------------- _build_agent_cmd_and_env
def test_build_cmd_openai_default():
    cmd, env, err = _build_agent_cmd_and_env('openai', 'k', 'u', 'model-x',
                                             content="it's")
    assert err is None
    assert cmd.startswith("pi -p '")
    assert "it's".replace("'", "'\"'\"'") in cmd
    assert env['PI_BASE_API_KEY'] == 'k'
    assert env['PI_BASE_MODEL_ID'] == 'model-x'


def test_build_cmd_openai_prompt_file():
    cmd, env, err = _build_agent_cmd_and_env('openai', 'k', 'u', 'm',
                                             use_prompt_file=True)
    assert '$(cat /app/.prompt.txt)' in cmd


def test_build_cmd_openai_resume():
    cmd, env, err = _build_agent_cmd_and_env('openai', 'k', 'u', 'm',
                                             resume=True)
    assert '--continue' in cmd
    assert '简体中文' in cmd


def test_build_cmd_cursor_default():
    cmd, env, err = _build_agent_cmd_and_env('cursor', 'k', 'u', 'm',
                                             content='c')
    assert cmd.startswith('agent -p')
    assert env['CURSOR_API_KEY'] == 'k'


def test_build_cmd_cursor_prompt_file():
    cmd, _, _ = _build_agent_cmd_and_env('cursor', 'k', 'u', 'm',
                                         use_prompt_file=True)
    assert '$(cat /app/.prompt.txt)' in cmd


def test_build_cmd_cursor_resume():
    cmd, _, _ = _build_agent_cmd_and_env('cursor', 'k', 'u', 'm', resume=True)
    assert 'agent --continue' in cmd


def test_build_cmd_unknown_format():
    cmd, env, err = _build_agent_cmd_and_env('nope', 'k', 'u', 'm')
    assert cmd is None and err['code'] == -1


# ---------------------------------------------------------------- env args helpers
def test_api_env_args_openai():
    assert _api_env_args('openai', 'k', 'u') == [
        '-e', 'OPENAI_API_KEY=k', '-e', 'OPENAI_BASE_URL=u']


def test_api_env_args_cursor():
    assert _api_env_args('cursor', 'k', 'u') == ['-e', 'CURSOR_API_KEY=k']


def test_pi_base_env_args():
    args = _pi_base_env_args('k', 'u', 'm')
    assert '-e' in args and 'PI_BASE_API_KEY=k' in args
    assert 'PI_BASE_CONTEXT=200000' in args


def test_proxy_env_args():
    assert _proxy_env_args('h1', 'h2', 'h3') == [
        '-e', 'https_proxy=h1', '-e', 'http_proxy=h2', '-e', 'no_proxy=h3']


def test_build_chown_tail_linux():
    chown_env, shell = _build_chown_tail('RUN')
    assert chown_env[0] == '-e' and chown_env[1].startswith('HOST_UID=')
    assert shell.startswith('RUN;')
    assert 'chown -R' in shell


# ---------------------------------------------------------------- _assemble_docker_run_cmd
def test_assemble_docker_run_cmd_openai():
    cmd = _assemble_docker_run_cmd(
        'uuid1', '/proj', 'openai', 'k', 'u', 'm',
        'p1', 'p2', 'p3', 'RUN')
    assert cmd[0] == 'docker' and cmd[1] == 'run'
    assert 'docker_uuid1' in cmd
    assert '/proj:/app' in cmd
    assert 'PI_BASE_API_KEY=k' in cmd
    assert 'PYTHONUNBUFFERED=1' in cmd
    assert cmd[-3:] == ['sh', '-c', cmd[-1]]


def test_assemble_docker_run_cmd_cursor_with_mounts():
    cmd = _assemble_docker_run_cmd(
        'uuid2', '/proj', 'cursor', 'k', 'u', 'm',
        '', '', '', 'RUN',
        extra_mounts=['-v', 'vol:/root/.pi'])
    assert 'CURSOR_API_KEY=k' in cmd
    assert 'vol:/root/.pi' in cmd
    assert not any(a.startswith('PI_BASE') for a in cmd)


# ---------------------------------------------------------------- _spawn_docker_agent
def test_spawn_docker_agent_ok():
    popen = MagicMock()
    cmd_list = []
    with patch('subprocess.Popen', return_value=popen) as p:
        ret = _spawn_docker_agent(['docker', 'run'], {'A': '1'}, cmd_list)
    assert ret is popen
    assert cmd_list == ['docker', 'run']
    assert p.call_args.kwargs['env'] == {'A': '1'}


def test_spawn_docker_agent_error():
    cmd_list = []
    with patch('subprocess.Popen', side_effect=RuntimeError('boom')):
        with pytest.raises(RuntimeError):
            _spawn_docker_agent(['x'], {}, cmd_list)


# ---------------------------------------------------------------- create_agent_process
def test_create_agent_process_no_key():
    ret = create_agent_process('c', '/p', {}, 'u', [], 'openai')
    assert ret['code'] == -1


def test_create_agent_process_ok():
    cmd_list = []
    with patch.object(qah, '_load_proxy_settings',
                      return_value={'https_proxy': '', 'http_proxy': '',
                                    'no_proxy': ''}), \
         patch.object(qah, '_spawn_docker_agent',
                      side_effect=lambda cmd, env, cl: cl.extend(cmd) or 'PROC') as spawn:
        ret = create_agent_process('c', '/p', GOOD_CFG, 'u1', cmd_list,
                                   'openai')
    assert ret == 'PROC'
    command = spawn.call_args[0][0]
    assert 'docker_u1' in command
    assert cmd_list  # cmd_list 被 _spawn_docker_agent 回填


def test_create_agent_process_bad_format():
    with patch.object(qah, '_load_proxy_settings',
                      return_value={'https_proxy': '', 'http_proxy': '',
                                    'no_proxy': ''}):
        ret = create_agent_process('c', '/p', GOOD_CFG, 'u1', [], 'zzz')
    assert ret['code'] == -1


# ---------------------------------------------------------------- _create_project_agent_process
def test_project_agent_process_no_key():
    ret = _create_project_agent_process('c', '/p', {}, 'u', [], 'openai')
    assert ret['code'] == -1


def _patch_common(monkeypatch, tmp_path):
    monkeypatch.setattr(qah, '_load_proxy_settings',
                        lambda: {'https_proxy': '', 'http_proxy': '',
                                 'no_proxy': ''})
    monkeypatch.setattr(qah, '_build_agent_cmd_and_env',
                        lambda *a, **kw: ('pi-run', {'E': '1'}, None))
    monkeypatch.setattr(qah, '_assemble_docker_run_cmd',
                        lambda **kw: ['docker', 'run'])
    monkeypatch.setattr(qah, '_spawn_docker_agent',
                        lambda cmd, env, cl, **kw: ('PROC', cl.append('x'))[0])


def test_project_agent_process_writes_prompt(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    ret = _create_project_agent_process('CONTENT', str(tmp_path), GOOD_CFG,
                                        'uuid', [], 'openai')
    assert ret is not None
    assert (tmp_path / '.prompt.txt').read_text(encoding='utf-8') == 'CONTENT'


def test_project_agent_process_prompt_exists(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    (tmp_path / '.prompt.txt').write_text('OLD', encoding='utf-8')
    _create_project_agent_process('CONTENT', str(tmp_path), GOOD_CFG,
                                  'uuid', [], 'openai')
    # 已存在时不覆盖
    assert (tmp_path / '.prompt.txt').read_text(encoding='utf-8') == 'OLD'


def test_project_agent_process_resume_skips_prompt(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    ret = _create_project_agent_process('CONTENT', str(tmp_path), GOOD_CFG,
                                        'uuid', [], 'openai', resume=True)
    assert ret is not None
    assert not (tmp_path / '.prompt.txt').exists()


def test_project_agent_process_prompt_write_fail(tmp_path, monkeypatch):
    _patch_common(monkeypatch, tmp_path)
    with patch('builtins.open', side_effect=OSError('ro')):
        ret = _create_project_agent_process('C', str(tmp_path), GOOD_CFG,
                                            'uuid', [], 'openai')
    assert ret['code'] == -1


def test_project_agent_process_named_volume(tmp_path, monkeypatch):
    spawn_args = {}

    def fake_spawn(cmd, env, cl, **kw):
        spawn_args['cmd'] = cmd
        return 'PROC'

    monkeypatch.setattr(qah, '_load_proxy_settings',
                        lambda: {'https_proxy': '', 'http_proxy': '', 'no_proxy': ''})
    monkeypatch.setattr(qah, '_build_agent_cmd_and_env',
                        lambda *a, **kw: ('pi', {}, None))
    monkeypatch.setattr(qah, '_assemble_docker_run_cmd', lambda **kw: ['docker'])
    monkeypatch.setattr(qah, '_spawn_docker_agent', fake_spawn)
    ret = _create_project_agent_process('C', str(tmp_path), GOOD_CFG, 'uuid',
                                        [], 'openai', named_volume='myvol')
    assert ret == 'PROC'
    # 挂载参数传入 _assemble_docker_run_cmd
    assert spawn_args['cmd'] == ['docker']


def test_project_agent_process_inject_skill(tmp_path, monkeypatch):
    captured = {}

    def fake_assemble(**kw):
        captured.update(kw)
        return ['docker']

    monkeypatch.setattr(qah, '_load_proxy_settings',
                        lambda: {'https_proxy': '', 'http_proxy': '', 'no_proxy': ''})
    monkeypatch.setattr(qah, '_build_agent_cmd_and_env',
                        lambda *a, **kw: ('pi', {}, None))
    monkeypatch.setattr(qah, '_assemble_docker_run_cmd', fake_assemble)
    monkeypatch.setattr(qah, '_spawn_docker_agent',
                        lambda cmd, env, cl, **kw: 'PROC')
    _create_project_agent_process('C', str(tmp_path), GOOD_CFG, 'uuid', [],
                                  'openai', inject_skill=True)
    # shell_cmd 内含 skill cp 命令
    assert 'cp -r /app/.skills/' in captured['shell_cmd']
    assert captured['extra_mounts'] == []


# ---------------------------------------------------------------- 文本处理 helpers
def test_indent_fences_in_chunk():
    assert _indent_fences_in_chunk('plain') == 'plain'
    out = _indent_fences_in_chunk('```python\nx=1\n```')
    assert out.split('\n')[0].startswith('    ```')


def test_line_value_of():
    line = b'{"status": 1, "value": "v"}'
    assert _line_value_of(line) == 'v'
    assert _line_value_of(b'not-json') == ''


def test_replace_line_value():
    line = b'{"status": 1, "value": "old"}'
    new = _replace_line_value(line, 'new')
    assert b'new' in new and b'"status": 1' in new
