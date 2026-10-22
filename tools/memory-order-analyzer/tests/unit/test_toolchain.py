import json
from pathlib import Path
import pytest
from memory_order_analyzer import toolchain as t
from memory_order_analyzer.contracts import AnalysisError
from conftest import success
from memory_order_analyzer.protocol import expected_protocol


def test_probe_and_doctor(tmp_path):
    finder = lambda name: "/usr/bin/" + name
    def runner(argv, cwd, **kwargs):
        return success(json.dumps(expected_protocol()) if argv[-1] == "--protocol" else "LLVM 21.1.8")
    assert t.probe_tool("clang", finder=finder, runner=runner)["version"] == "21.1.8"
    assert t.doctor("worker", finder=finder, runner=runner)["ready"]
    reader = t.reader_doctor("worker", runner=runner)
    assert reader["ready"] and set(reader["tools"]) == {"worker"}
    assert not t.reader_doctor(None, runner=runner)["ready"]
    assert not t.reader_doctor("worker", runner=lambda *a, **k: success("{}"))["ready"]
    assert not t.doctor(finder=finder, runner=runner)["ready"]
    assert not t.doctor("worker", finder=lambda name: None, runner=runner)["ready"]
    mismatch = t.doctor("worker", finder=finder, runner=lambda *a, **k: success("LLVM 16.0.4"))
    assert len(mismatch["failures"]) == len(t.LLVM_TOOLS) + 1
    for probe_runner in (lambda *a, **k: success("unknown"), lambda *a, **k: success(code=1)):
        with pytest.raises(AnalysisError):
            t.probe_tool("clang", finder=finder, runner=probe_runner)


def test_driver_symlink_name_is_preserved(tmp_path):
    binary = tmp_path / "clang"
    binary.write_text("unit")
    alias = tmp_path / "clang++"
    alias.symlink_to(binary)
    result = t.probe_tool("clang++", finder=lambda name: str(alias), runner=lambda *a, **k: success("LLVM 21.1.8"))
    assert result["path"] == str(alias) and result["resolved_path"] == str(binary)
