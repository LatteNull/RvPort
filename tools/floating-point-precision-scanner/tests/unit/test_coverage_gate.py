from __future__ import annotations

import json
from pathlib import Path

import pytest

from floating_point_precision_scanner.coverage_gate import evaluate, main, metrics_for


def file_metrics(lines: tuple[int, int], branches: tuple[int, int]) -> dict[str, object]:
    return {
        "summary": {
            "covered_lines": lines[0],
            "num_statements": lines[1],
            "covered_branches": branches[0],
            "num_branches": branches[1],
        }
    }


def test_metrics_and_zero_denominator() -> None:
    metrics = metrics_for([file_metrics((9, 10), (18, 20))])
    assert metrics.lines == 90
    assert metrics.branches == 90
    empty = metrics_for([file_metrics((0, 0), (0, 0))])
    assert empty.lines == empty.branches == 100


def test_gate_checks_overall_and_affected_without_rounding() -> None:
    passing = {
        "files": {"src/floating_point_precision_scanner/a.py": file_metrics((9, 10), (9, 10))}
    }
    ok, values = evaluate(passing, ("floating_point_precision_scanner",))
    assert ok
    assert values["overall"].branches == 90
    failing = {
        "files": {"src/floating_point_precision_scanner/a.py": file_metrics((95, 100), (899, 1000))}
    }
    ok, _ = evaluate(failing, ("floating_point_precision_scanner",))
    assert not ok


def test_gate_rejects_missing_files_and_affected() -> None:
    with pytest.raises(ValueError, match="no_files"):
        evaluate({}, ("module",))
    with pytest.raises(ValueError, match="not_found"):
        evaluate({"files": {"src/other.py": file_metrics((1, 1), (1, 1))}}, ("module",))


def test_gate_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {"files": {"src/floating_point_precision_scanner/a.py": file_metrics((9, 10), (9, 10))}}
        ),
        encoding="utf-8",
    )
    assert main([str(report), "--affected", "floating_point_precision_scanner"]) == 0
    assert json.loads(capsys.readouterr().out)["overall"]["lines"] == 90
    assert (
        main([str(report), "--affected", "floating_point_precision_scanner", "--minimum", "91"])
        == 1
    )
