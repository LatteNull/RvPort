from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

import pytest
from tests.helpers import RISCV, X86, add_bitcode_artifact_set, make_request

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.frontend import ClangFrontend
from floating_point_precision_scanner.ir_worker import IrWorker
from floating_point_precision_scanner.protocol import SchemaRegistry

pytestmark = pytest.mark.integration


def test_real_loops_keep_independent_findings(tmp_path: Path) -> None:
    clang = Path(os.environ.get("FP_SCANNER_CLANG", "/usr/lib/llvm-21/bin/clang-21"))
    assert clang.is_file(), "归约验收要求锁定的 Clang 21.1.8，不允许跳过"
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures/expression-risks/independent-reductions.c"
    )
    source = tmp_path / fixture.name
    source.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    request = {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.4",
        "request_id": "independent-reductions",
        "project_root": str(tmp_path),
        "source_profile": X86,
        "target_profile": RISCV,
        "input": {
            "translation_units": [
                {
                    "file": source.name,
                    "directory": str(tmp_path),
                    "arguments": ["clang", "-std=c17", "-c", source.name],
                }
            ]
        },
        "rules": {"enabled": ["reduction-reassociation"]},
    }
    result = Scanner(ClangFrontend(clang)).scan(request)
    assert result["scan"]["status"] == "complete"
    assert SchemaRegistry().validate("result", result) == []
    findings = result["findings"]
    oracle = json.loads(
        (fixture.parent.parent / "validation/reduction-granularity-oracle-v1.json").read_text()
    )
    assert len(findings) == len(oracle["matched_lines"])
    assert {f["fact"]["primaryLocation"]["line"] for f in findings} == set(oracle["matched_lines"])
    assert all(len(f["occurrences"]) == 1 for f in findings)
    assert all(f["conclusion"]["affectedCount"] == 1 for f in findings)
    assert all(f["conclusion"]["evidenceOrigin"] == "heuristic" for f in findings)
    suppressed = copy.deepcopy(request)
    suppressed["suppressions"] = [
        {
            "code": "reduction-reassociation",
            "path": source.name,
            "start_line": 4,
            "end_line": 4,
            "reason": "independently reviewed",
        }
    ]
    remaining = Scanner(ClangFrontend(clang)).scan(suppressed)
    assert len(remaining["findings"]) == 3
    assert remaining["summary"]["suppressed"] == 1
    assert {f["fact"]["primaryLocation"]["line"] for f in remaining["findings"]} == set(
        oracle["remaining_lines"]
    )
    request["cache"] = {"mode": "read-write", "root": str(tmp_path / ".cache")}
    cold = Scanner(ClangFrontend(clang)).scan(request)
    warm = Scanner(ClangFrontend(clang)).scan(request)
    assert cold["findings"] == warm["findings"] == findings
    assert cold["scan"]["semanticDigest"] == warm["scan"]["semanticDigest"]
    assert warm["extensions"]["org.rvport.floating-point-scanner.runtime"]["cache"]["hit"] == 1
    # 导出实际观察供验收审计，预期行号来自上面独立编写的源文件。
    output = Path("artifacts/validation/reduction-granularity-observed.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("matching", [True, False])
def test_real_reduction_ir_is_bound_only_to_matching_candidates(tmp_path: Path, matching: bool):
    clang = Path(os.environ.get("FP_SCANNER_CLANG", "/usr/lib/llvm-21/bin/clang-21"))
    worker = Path(os.environ.get("FP_SCANNER_IR_WORKER", "/workspace/build/fp-ir-worker"))
    assert clang.is_file() and worker.is_file()
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures/expression-risks/independent-reductions.c"
    )
    source = tmp_path / fixture.name
    source.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    ir_source = source
    if not matching:
        ir_source = tmp_path / "unrelated.c"
        ir_source.write_text("double unrelated(double a, double b) { return a + b; }\n")
    bc = tmp_path / "compiled.bc"
    subprocess.run(
        [str(clang), "-g", "-ffast-math", "-emit-llvm", "-c", str(ir_source), "-o", str(bc)],
        check=True,
    )
    request = make_request(
        tmp_path,
        [
            {
                "file": source.name,
                "directory": str(tmp_path),
                "arguments": ["clang", "-std=c17", "-g", "-ffast-math", "-c", source.name],
            }
        ],
    )
    request["rules"] = {"enabled": ["reduction-reassociation"]}
    request, _, _ = add_bitcode_artifact_set(
        request, profile="build-faithful", bitcode=bc.read_bytes()
    )
    request["schema_version"] = "1.4"
    result = Scanner(ClangFrontend(clang), ir_worker=IrWorker(worker)).scan(request)
    output = Path(f"artifacts/validation/reduction-ir-{matching}-observed.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert SchemaRegistry().validate("result", result) == []
    assert len(result["findings"]) == 4
    for finding in result["findings"]:
        ir_steps = [
            step for step in finding["evidenceChain"]["steps"] if step["kind"] == "irObservation"
        ]
        assert bool(ir_steps) is matching
        assert finding["conclusion"]["evidenceOrigin"] == "heuristic"
        assert len(finding["occurrences"]) == 1
    output = Path(f"artifacts/validation/reduction-ir-{matching}-observed.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
