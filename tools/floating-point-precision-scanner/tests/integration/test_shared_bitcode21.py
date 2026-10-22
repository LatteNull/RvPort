from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
from tests.helpers import RISCV, X86, add_bitcode_artifact_set, make_request

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.artifacts import ArtifactPlan, BitcodeMember
from floating_point_precision_scanner.frontend import ClangFrontend
from floating_point_precision_scanner.ir_worker import IrWorker
from floating_point_precision_scanner.protocol import SchemaRegistry

ROOT = Path(__file__).resolve().parents[2]
CLANG = Path(os.environ.get("FP_SCANNER_CLANG", "/usr/lib/llvm-21/bin/clang-21"))
WORKER = Path(os.environ.get("FP_SCANNER_IR_WORKER", "/workspace/build/fp-ir-worker"))

pytestmark = pytest.mark.integration
requires_toolchain = pytest.mark.skipif(
    not CLANG.is_file() or not WORKER.is_file(), reason="locked Clang/LLVM 21.1.8 is unavailable"
)


@requires_toolchain
@pytest.mark.parametrize(
    ("extension", "standard"), [("c", "c11"), ("c", "c17"), ("cpp", "c++17"), ("cpp", "c++20")]
)
def test_real_ast_bitcode_and_evidence_pipeline(
    tmp_path: Path, extension: str, standard: str
) -> None:
    source = tmp_path / f"main.{extension}"
    source.write_text("double compute(double a, double b) { return a + b; }\n", encoding="utf-8")
    bitcode_path = tmp_path / "compiled.bc"
    subprocess.run(
        [
            str(CLANG),
            f"-std={standard}",
            "-g",
            "-emit-llvm",
            "-c",
            str(source),
            "-o",
            str(bitcode_path),
        ],
        check=True,
        shell=False,
    )
    request = make_request(
        tmp_path,
        [
            {
                "file": source.name,
                "directory": str(tmp_path),
                "arguments": ["clang", f"-std={standard}", "-g", "-c", source.name],
            }
        ],
    )
    request["source_profile"] = X86
    request["target_profile"] = RISCV
    request, _, _ = add_bitcode_artifact_set(request, bitcode=bitcode_path.read_bytes())
    result = Scanner(ClangFrontend(CLANG), ir_worker=IrWorker(WORKER)).scan(request)
    assert result["scan"]["status"] in {"complete", "partial"}, result["diagnostics"][0][
        "suggestionEn"
    ]
    artifacts = result["extensions"]["org.rvport.floating-point-scanner.artifacts"]
    analysis = result["extensions"]["org.rvport.floating-point-scanner.analysis"]
    assert artifacts["irAnalysis"]["status"] == "complete"
    assert analysis["bundleDigests"]["ir"]
    assert result["findings"] == []
    assert SchemaRegistry().validate("result", result) == []


@requires_toolchain
def test_real_core_long_double_fma_and_fast_math_findings(tmp_path: Path) -> None:
    source = tmp_path / "core.c"
    source.write_text(
        "long double exported(long double value) { return value; }\n"
        "double compute(double a, double b, double c) { return a * b + c; }\n",
        encoding="utf-8",
    )
    flags = ["-std=c17", "-O2", "-g", "-ffast-math", "-ffp-contract=fast"]
    bitcode_path = tmp_path / "compiled.bc"
    subprocess.run(
        [str(CLANG), *flags, "-emit-llvm", "-c", str(source), "-o", str(bitcode_path)],
        check=True,
        shell=False,
    )
    request = make_request(
        tmp_path,
        [
            {
                "file": source.name,
                "directory": str(tmp_path),
                "arguments": ["clang", *flags, "-c", source.name],
            }
        ],
    )
    request["rules"] = {"enabled": ["long-double-abi", "fma-contraction", "unsafe-fp-optimization"]}
    request, _, _ = add_bitcode_artifact_set(
        request, profile="build-faithful", bitcode=bitcode_path.read_bytes()
    )
    result = Scanner(ClangFrontend(CLANG), ir_worker=IrWorker(WORKER)).scan(request)
    assert result["scan"]["status"] in {"complete", "partial"}
    assert {item["conclusion"]["findingCode"] for item in result["findings"]} == {
        "long-double-abi",
        "fma-contraction",
        "unsafe-fp-optimization",
    }
    # long-double return and parameter are separate, directly evidenced ABI boundaries.
    assert result["summary"]["assessments"]["matched"] == 4
    assert SchemaRegistry().validate("result", result) == []
    steps = [step for finding in result["findings"] for step in finding["evidenceChain"]["steps"]]
    ir_steps = [step for step in steps if step["kind"] == "irObservation"]
    assert ir_steps and all("fast_math_flags=" in step["reason"] for step in ir_steps)
    assert all("Unrecorded attributes" in step["reasonEn"] for step in ir_steps)
    assert all(
        all(step[key].strip() for key in ("title", "titleEn", "reason", "reasonEn"))
        for step in steps
    )


@requires_toolchain
def test_real_x87_excess_precision_finding(tmp_path: Path) -> None:
    source = tmp_path / "x87.c"
    source.write_text(
        "double compute(double a, double b, double c) { return (a + b) * c; }\n",
        encoding="utf-8",
    )
    flags = [
        "-std=c17",
        "-m32",
        "-mno-sse",
        "-mfpmath=387",
        "-fexcess-precision=fast",
        "-g",
    ]
    bitcode_path = tmp_path / "compiled.bc"
    subprocess.run(
        [str(CLANG), *flags, "-emit-llvm", "-c", str(source), "-o", str(bitcode_path)],
        check=True,
        shell=False,
    )
    request = make_request(
        tmp_path,
        [
            {
                "file": source.name,
                "directory": str(tmp_path),
                "arguments": ["clang", *flags, "-c", source.name],
            }
        ],
    )
    request["rules"] = {"enabled": ["x87-excess-precision"]}
    request, _, _ = add_bitcode_artifact_set(
        request, profile="build-faithful", bitcode=bitcode_path.read_bytes()
    )
    result = Scanner(ClangFrontend(CLANG), ir_worker=IrWorker(WORKER)).scan(request)
    assert result["scan"]["status"] in {"complete", "partial"}
    assert [item["conclusion"]["findingCode"] for item in result["findings"]] == [
        "x87-excess-precision"
    ]
    assert result["summary"]["assessments"]["matched"] == 1
    assert SchemaRegistry().validate("result", result) == []


@requires_toolchain
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("scalar.bc", {"fadd", "fcmp", "fptrunc", "fdiv"}),
        ("calls.bc", {"call"}),
        ("vector.bc", {"fadd"}),
        ("constrained.bc", {"call"}),
    ],
)
def test_fixed_bitcode_oracles(name: str, expected: set[str]) -> None:
    path = ROOT / "tests" / "fixtures" / "bitcode" / name
    content = path.read_bytes()
    member = BitcodeMember(
        {
            "artifact_key": "b" * 64,
            "physical_tu_id": "c" * 64,
            "context_id": "d" * 64,
            "profile": "source-preserving",
            "sha256": hashlib.sha256(content).hexdigest(),
        },
        path,
        None,
    )
    plan = ArtifactPlan({"artifact_set_id": "a" * 64}, (member,), (), 0)
    worker = IrWorker(WORKER)
    worker.verify()
    bundle = worker.extract(plan, member, max_facts=1000, project_root=ROOT)
    assert expected <= {str(item["opcode"]) for item in bundle["facts"]}
    assert SchemaRegistry().validate("llvm_facts", bundle) == []
