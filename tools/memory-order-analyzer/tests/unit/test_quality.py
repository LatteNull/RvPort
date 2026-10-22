import json
from pathlib import Path
import runpy
import sys
import pytest
from memory_order_analyzer import quality as q
from memory_order_analyzer.contracts import AnalysisError


def reports(root, output, hit=90, total=100, branch_hit=90):
    (root / "python").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "python/unloaded.py").write_text("raise RuntimeError('not imported')\n")
    (root / "src/worker.cpp").write_text("int main() { return 0; }\n")
    python = {"files": {"python/unloaded.py": {"summary": {"covered_lines": hit, "num_statements": total,
                "covered_branches": branch_hit, "num_branches": total}}}}
    cpp = {"data": [{"files": [{"filename": str(root / "src/worker.cpp"), "summary": {
        "lines": {"covered": total, "count": total}, "branches": {"covered": total, "count": total}}}]}]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "python.json").write_text(json.dumps(python))
    (output / "cpp.json").write_text(json.dumps(cpp))
    return python, cpp


@pytest.mark.parametrize("hit,total,branches,passed", [(8999, 10000, 9000, False), (9000, 10000, 9000, True), (95, 100, 89, False)])
def test_threshold_modules_languages_and_weighted_totals(tmp_path, hit, total, branches, passed):
    root, output = tmp_path / "root", tmp_path / "reports"
    reports(root, output, hit, total, branches)
    result = q.evaluate(root, output / "python.json", output / "cpp.json")
    assert result["passed"] is passed
    assert result["overall"]["lines"]["hit"] == hit + total
    assert result["overall"]["lines"]["total"] == 2 * total
    assert result["modules"]["python/unloaded.py"]["lines"]["percent"] == 100 * hit / total
    assert len(result["modules"]) == 2 and result["profile"] == "unit-only"


def test_missing_report_unloaded_source_exclusions_and_invalid_counts(tmp_path):
    root, output = tmp_path / "root", tmp_path / "reports"
    reports(root, output)
    with pytest.raises(AnalysisError, match="cannot be excluded"):
        q.evaluate(root, output / "python.json", output / "cpp.json", exclusions=["unloaded.py"])
    (root / "python/never_imported.py").write_text("x = 1\n")
    with pytest.raises(AnalysisError, match="owned source"):
        q.evaluate(root, output / "python.json", output / "cpp.json")
    with pytest.raises(AnalysisError):
        q.evaluate(root, output / "absent.json", output / "cpp.json")
    (output / "cpp.json").write_text("{")
    with pytest.raises(AnalysisError):
        q.evaluate(root, output / "python.json", output / "cpp.json")
    for hit, total in ((-1, 1), (2, 1), (1.0, 2), (0, -1)):
        with pytest.raises(AnalysisError):
            q.metric(hit, total)
    assert q.metric(0, 0)["percent"] is None
    assert q.aggregate([])["branches"]["total"] == 0


def test_thread_entry_modules_are_in_owned_coverage_denominator():
    root = Path(__file__).resolve().parents[2]
    names = {path.relative_to(root).as_posix() for path in q.owned_sources(root)["python"]}
    assert {
        "python/memory_order_analyzer/thread_entry_analysis.py",
        "python/memory_order_analyzer/thread_entry_cache.py",
        "python/memory_order_analyzer/thread_entry_contracts.py",
        "python/memory_order_analyzer/thread_entry_profiles.py",
        "python/memory_order_analyzer/discover_thread_entries.py",
    } <= names


def test_concurrent_access_modules_are_in_owned_coverage_denominator():
    root = Path(__file__).resolve().parents[2]
    names = {path.relative_to(root).as_posix() for path in q.owned_sources(root)["python"]}
    assert {
        "python/memory_order_analyzer/build_concurrent_access_candidates.py",
        "python/memory_order_analyzer/concurrent_access_analysis.py",
        "python/memory_order_analyzer/concurrent_access_cache.py",
        "python/memory_order_analyzer/concurrent_access_contracts.py",
        "python/memory_order_analyzer/concurrent_access_validation.py",
    } <= names


def test_demand_driven_modules_are_in_owned_coverage_denominator():
    root = Path(__file__).resolve().parents[2]
    names = {path.relative_to(root).as_posix() for path in q.owned_sources(root)["python"]}
    assert {
        "python/memory_order_analyzer/analyze_demanded_functions.py",
        "python/memory_order_analyzer/demand_adapters.py",
        "python/memory_order_analyzer/demand_cache.py",
        "python/memory_order_analyzer/demand_contracts.py",
        "python/memory_order_analyzer/demand_graph.py",
        "python/memory_order_analyzer/demand_scheduler.py",
    } <= names
    cpp = {path.relative_to(root).as_posix() for path in q.owned_sources(root)["cpp"]}
    assert {"src/demand_analysis.cpp", "src/demand_analysis.h", "src/ir_identity.h"} <= cpp


@pytest.mark.parametrize("integration", [False, True])
def test_quality_orchestration_separates_profiles(tmp_path, monkeypatch, integration):
    root, output = tmp_path / "root", tmp_path / "quality"
    reference = tmp_path / "reference"
    python, cpp = reports(root, reference)
    commands = []
    def runner(command, **kwargs):
        commands.append((command, kwargs))
        if "json" in command:
            (output / "python.json").write_text(json.dumps(python))
    def export(command, **kwargs):
        assert command[:2] == ["llvm-cov", "export"] and kwargs["check"]
        kwargs["stdout"].write(json.dumps(cpp))
    monkeypatch.setattr(q.subprocess, "run", export)
    result = q.run_quality(root, output, integration=integration, runner=runner)
    assert result["passed"]
    assert (output / "coverage-summary.html").exists()
    assert (["cmake", "--build", str(output / "build"), "-j", "2"], {"cwd": root}) in commands
    coverage_command = next(cmd for cmd, _ in commands if "--branch" in cmd)
    assert "--source=" + str(root / "python") in coverage_command
    assert all("integration" not in " ".join(cmd) for cmd, opts in commands[:-1])
    if integration:
        command, options = commands[-1]
        assert command[-1].endswith("tests/integration")
        assert "integration-%p" in options["env"]["LLVM_PROFILE_FILE"]
    with pytest.raises(AnalysisError, match="new directory"):
        q.run_quality(root, output, runner=runner)
    monkeypatch.setattr(q, "evaluate", lambda *a, **k: {"passed": False})
    with pytest.raises(AnalysisError, match="coverage-summary"):
        q.run_quality(root, tmp_path / "failed", runner=runner)


def test_cli_and_subprocess_check(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(q.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    q.check(["unit"], cwd=tmp_path)
    assert calls[0][1]["check"] is True
    monkeypatch.setattr(q, "run_quality", lambda *a, **k: {"passed": True})
    assert q.main(["--output", str(tmp_path / "output")]) == 0
    assert json.loads(capsys.readouterr().out)["passed"]
    monkeypatch.setattr(sys, "argv", ["quality", "--help"])
    monkeypatch.delitem(sys.modules, "memory_order_analyzer.quality", raising=False)
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("memory_order_analyzer.quality", run_name="__main__")
    assert caught.value.code == 0
