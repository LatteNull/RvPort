from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from tests.helpers import RISCV, X86

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.frontend import ClangFrontend

ROOT = Path(__file__).resolve().parents[2]
CLANG = Path(os.environ.get("FP_SCANNER_CLANG", "/usr/lib/llvm-21/bin/clang-21"))

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not CLANG.is_file(), reason="locked Clang 21.1.8 is unavailable")
@pytest.mark.parametrize(
    ("file", "standard", "source_profile", "target", "abi"),
    [
        ("c11.c", "c11", X86, "x86_64-unknown-linux-gnu", None),
        ("c17.c", "c17", X86, "x86_64-unknown-linux-gnu", None),
        ("cpp17.cpp", "c++17", X86, "x86_64-unknown-linux-gnu", None),
        ("cpp20.cpp", "c++20", RISCV, "riscv64-unknown-linux-gnu", "lp64d"),
    ],
)
def test_locked_clang_extracts_canonical_facts(
    file: str, standard: str, source_profile: str, target: str, abi: str | None
) -> None:
    fixture_root = ROOT / "tests" / "fixtures" / "integration"
    arguments = ["clang", f"-std={standard}", f"--target={target}"]
    if abi:
        arguments.append(f"-mabi={abi}")
    arguments.append(file)
    request = {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.0",
        "request_id": f"integration-{standard}",
        "project_root": str(fixture_root),
        "source_profile": source_profile,
        "target_profile": RISCV if source_profile == X86 else X86,
        "input": {
            "translation_units": [
                {"file": file, "directory": str(fixture_root), "arguments": arguments}
            ]
        },
    }
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    assert result["scan"]["status"] in {"complete", "partial"}
    analysis = result["extensions"]["org.rvport.floating-point-scanner.analysis"]
    assert analysis["layers"]["source"]["completed"] == 1
    assert result["summary"]["assessments"]["planned"] == 4
    assert analysis["bundleDigests"]["source"]


@pytest.mark.skipif(not CLANG.is_file(), reason="locked Clang 21.1.8 is unavailable")
@pytest.mark.parametrize(
    ("file", "standard"),
    [
        ("legacy.c", "c89"),
        ("legacy.c", "c99"),
        ("legacy.c", "gnu99"),
        ("legacy.cpp", "c++98"),
        ("legacy.cpp", "gnu++03"),
        ("legacy.c", None),
    ],
)
def test_locked_clang_replays_legacy_and_default_standards(
    file: str, standard: str | None
) -> None:
    fixture_root = ROOT / "tests" / "fixtures" / "integration"
    arguments = ["clang++" if file.endswith(".cpp") else "clang"]
    if standard is not None:
        arguments.append(f"-std={standard}")
    arguments.append(file)
    request = {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.0",
        "request_id": f"integration-{standard or 'compiler-default'}",
        "project_root": str(fixture_root),
        "source_profile": X86,
        "target_profile": RISCV,
        "input": {
            "translation_units": [
                {"file": file, "directory": str(fixture_root), "arguments": arguments}
            ]
        },
    }
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    assert result["scan"]["status"] in {"complete", "partial"}
    analysis = result["extensions"]["org.rvport.floating-point-scanner.analysis"]
    assert analysis["layers"]["source"]["completed"] == 1


@pytest.mark.skipif(not CLANG.is_file(), reason="locked Clang 21.1.8 is unavailable")
def test_locked_clang_extracts_expression_risks_and_conservative_libm(tmp_path: Path) -> None:
    source = tmp_path / "expression.c"
    fixture = ROOT / "tests" / "fixtures" / "expression-risks"
    source.write_text((fixture / "expression.c").read_text(encoding="utf-8"), encoding="utf-8")
    fixture_root = ROOT / "tests" / "fixtures" / "build-context"
    request = {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.3",
        "request_id": "integration-expression-risks",
        "project_root": str(tmp_path),
        "source_profile": X86,
        "target_profile": RISCV,
        "build_contexts": {
            "source": json.loads(
                (fixture_root / "x86-unknown-libm.json").read_text(encoding="utf-8")
            ),
            "target": json.loads(
                (fixture_root / "riscv-unknown-libm.json").read_text(encoding="utf-8")
            ),
        },
        "input": {
            "translation_units": [
                {
                    "file": source.name,
                    "directory": str(tmp_path),
                    "arguments": ["clang", "-std=c17", "-c", source.name],
                }
            ]
        },
        "rules": {
            "enabled": [
                "mixed-precision-conversion",
                "fragile-fp-comparison",
                "reduction-reassociation",
                "math-library-variance",
            ]
        },
    }
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    analysis = result["extensions"]["org.rvport.floating-point-scanner.analysis"]
    assessments = {item["ruleCode"]: item["status"] for item in analysis["assessments"]}
    assert assessments == expected["assessments"]
    assert sorted({item["conclusion"]["evidenceOrigin"] for item in result["findings"]}) == sorted(
        expected["finding_origins"]
    )
