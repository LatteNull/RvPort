import os
from pathlib import Path
import signal
import sys
import pytest
from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer import execution as ex


def test_environment(monkeypatch):
    monkeypatch.setenv("TOKEN_SECRET", "never exposed")
    assert "TOKEN_SECRET" not in ex.environment()
    assert ex.environment({"CPATH": "abc"})["CPATH"] == "abc"
    for overrides in ({"TOKEN_SECRET": "bad"}, {"PATH": 1}):
        with pytest.raises(AnalysisError):
            ex.environment(overrides)


def test_runner_success_nonzero_and_start_failure(tmp_path):
    result = ex.run([sys.executable, "-c", "print('hello')"], tmp_path)
    assert ex.require_success(result, "test") == "hello\n"
    assert result["output_bytes"] >= len("hello\n")
    assert result["cpu_seconds"] >= 0 and result["peak_rss_bytes"] > 0
    result = ex.run([sys.executable, "-c", "import sys; print('bad', file=sys.stderr); sys.exit(3)"], tmp_path)
    assert result["exit_code"] == 3 and result["stderr"] == "bad\n"
    with pytest.raises(AnalysisError, match="bad"):
        ex.require_success(result, "unit")
    assert ex.run(["/nonexistent-tool"], tmp_path)["code"] == "start_failed"


def test_runner_budget(tmp_path):
    result = ex.run([sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, timeout=0.05)
    assert result["status"] == "timed_out"
    result = ex.run([sys.executable, "-c", "print('x'*100000)"], tmp_path, log_limit=100)
    assert result["code"] == "log_limit" and len(result["stdout"]) == 100
    result = ex.run([sys.executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(5)"], tmp_path, timeout=0.05)
    assert result["status"] == "timed_out"


def test_runner_invalid(tmp_path, monkeypatch):
    for argv in ([], [1], ["a\0b"]):
        with pytest.raises(AnalysisError):
            ex.run(argv, tmp_path)
    for options in ({"timeout": 0}, {"log_limit": 0}):
        with pytest.raises(AnalysisError):
            ex.run(["true"], tmp_path, **options)
    with pytest.raises(AnalysisError):
        ex.run(["true"], tmp_path / "absent")
    monkeypatch.setattr(ex.os, "name", "nt")
    # Platform test uses an existing Path object to avoid pathlib's OS factory.
    monkeypatch.setattr(ex, "Path", lambda value: tmp_path)
    with pytest.raises(AnalysisError, match="Linux"):
        ex.run(["true"], tmp_path)
    assert ex._linux_process_usage(1) == {"cpu_seconds": 0.0, "peak_rss_bytes": 0}


def test_linux_process_usage_handles_missing_and_malformed_proc(monkeypatch):
    class Missing:
        def __init__(self, value):
            self.value = value

        def read_text(self, **kwargs):
            raise OSError("gone")

    monkeypatch.setattr(ex, "Path", Missing)
    assert ex._linux_process_usage(999999) == {"cpu_seconds": 0.0, "peak_rss_bytes": 0}


def test_timeout_terminates_owned_child_group(tmp_path):
    code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(p.pid,flush=True); time.sleep(30)"
    result = ex.run([sys.executable, "-c", code], tmp_path, timeout=0.2)
    assert result["status"] == "timed_out"
    pid = int(result["stdout"])
    state = Path(f"/proc/{pid}/stat")
    # A reaped child disappears; a killed child waiting for PID 1 is a zombie.
    assert not state.exists() or state.read_text().split()[2] == "Z"


def test_output_store(tmp_path):
    store = ex.OutputStore(tmp_path / "output")
    for path in ("..", "../escape", ".", "/etc/passwd"):
        with pytest.raises(AnalysisError):
            store.path(path)
    with pytest.raises(AnalysisError):
        ex.OutputStore("/")
    with pytest.raises(AnalysisError):
        ex.OutputStore(Path.home())
    with store.temporary() as stage:
        source = stage / "x"
        source.write_text("owned")
        target = store.publish(source, "nested/x")
        assert target.read_text() == "owned"
        with pytest.raises(AnalysisError, match="nested/x"):
            store.publish(source, "nested/x")
        with pytest.raises(AnalysisError):
            store.publish(tmp_path / "outside", "invalid")
    assert not stage.exists() and target.read_text() == "owned"
    with pytest.raises(RuntimeError):
        with store.temporary() as stage:
            raise RuntimeError("unit interruption")
    assert not stage.exists()
