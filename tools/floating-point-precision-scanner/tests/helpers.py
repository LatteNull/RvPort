from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from floating_point_precision_scanner.compilation import load_compilation_plan
from floating_point_precision_scanner.frontend import ProcessResult
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request

X86 = "x86_64-linux-gnu-clang21@1.0"
RISCV = "riscv64-linux-gnu-lp64d-clang21@1.0"


def make_request(root: Path, units: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    if units is None:
        source = root / "main.c"
        source.write_text("double add(double a, double b) { return a + b; }\n", encoding="utf-8")
        units = [
            {
                "file": "main.c",
                "directory": str(root),
                "arguments": ["clang", "-std=c17", "-c", "main.c"],
            }
        ]
    return {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.0",
        "request_id": "request-1",
        "project_root": str(root),
        "source_profile": X86,
        "target_profile": RISCV,
        "input": {"translation_units": units},
        "rules": {"enabled": []},
    }


def add_bitcode_artifact_set(
    request: dict[str, Any],
    *,
    profile: str = "source-preserving",
    bitcode: bytes = b"BC fixture",
    source_mapping: str = "best-effort",
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    root = Path(str(request["project_root"]))
    artifact_root = root / "artifacts"
    artifact_root.mkdir()
    bitcode_path = artifact_root / "main.bc"
    bitcode_path.write_bytes(bitcode)
    parsed, errors = parse_request(request, SchemaRegistry())
    assert parsed is not None and not errors
    plan = load_compilation_plan(parsed)
    context = plan.contexts[0]
    document: dict[str, Any] = {
        "kind": "SharedBitcodeArtifactSet",
        "schema_version": "1.0",
        "artifact_set_id": "a" * 64,
        "source_revision": "revision-1",
        "build_run_id": "build-1",
        "compile_commands_sha256": plan.input_digest,
        "status": "READY",
        "producer": {
            "tool": "x86-builder",
            "version": "1.0",
            "analysis_compiler": {"name": "clang", "version": "21.1.8"},
            "production_compiler": {"name": "clang", "version": "21.1.8"},
        },
        "counts": {"planned": 1, "completed": 1, "failed": 0},
        "members": [
            {
                "physical_tu_id": context.physical_tu_id,
                "context_id": context.context_id,
                "artifact_key": "b" * 64,
                "language": context.language,
                "target": context.target,
                "abi": context.abi,
                "profile": profile,
                "profile_version": "1.0",
                "capabilities": ["debug-location", "llvm-fp-facts"],
                "path": bitcode_path.name,
                "size_bytes": len(bitcode),
                "sha256": hashlib.sha256(bitcode).hexdigest(),
                "data_layout": None,
            }
        ],
        "failures": [],
    }
    manifest_path = artifact_root / "manifest.json"
    manifest_path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    request["schema_version"] = "1.1"
    request["source_revision"] = "revision-1"
    request["bitcode_artifact_set"] = {
        "artifact_root": str(artifact_root),
        "manifest": manifest_path.name,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "required_profiles": [profile],
        "source_mapping": source_mapping,
    }
    return request, manifest_path, document


def rewrite_manifest(
    request: dict[str, Any], manifest_path: Path, document: dict[str, Any]
) -> None:
    manifest_path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    request["bitcode_artifact_set"]["manifest_sha256"] = hashlib.sha256(  # type: ignore[index]
        manifest_path.read_bytes()
    ).hexdigest()


def ast_for(path: Path, *, unknown: bool = False) -> dict[str, Any]:
    children: list[dict[str, Any]] = [
        {
            "kind": "VarDecl",
            "name": "x",
            "type": {"qualType": "double"},
            "loc": {"file": str(path), "line": 1, "col": 1},
        },
        {
            "kind": "FloatingLiteral",
            "value": "1.0",
            "type": {"qualType": "double"},
            "loc": {"file": str(path), "line": 1, "col": 12},
        },
        {
            "kind": "BinaryOperator",
            "opcode": "+",
            "type": {"qualType": "double"},
            "loc": {"file": str(path), "line": 1, "col": 16},
        },
        {
            "kind": "BinaryOperator",
            "opcode": "==",
            "type": {"qualType": "int"},
            "loc": {"file": str(path), "line": 1, "col": 20},
            "inner": [
                {"kind": "DeclRefExpr", "type": {"qualType": "double"}},
                {"kind": "DeclRefExpr", "type": {"qualType": "double"}},
            ],
        },
        {
            "kind": "ImplicitCastExpr",
            "castKind": "FloatingCast",
            "type": {"qualType": "float"},
            "loc": {"file": str(path), "line": 1, "col": 24},
        },
        {
            "kind": "CallExpr",
            "type": {"qualType": "double"},
            "loc": {"file": str(path), "line": 1, "col": 28},
            "inner": [{"kind": "DeclRefExpr", "referencedDecl": {"name": "sqrt"}}],
        },
    ]
    if unknown:
        children.append(
            {
                "kind": "FutureFloatExpr",
                "type": {"qualType": "double"},
                "loc": {"file": str(path), "line": 1, "col": 32},
            }
        )
    return {"kind": "TranslationUnitDecl", "inner": children}


class QueueRunner:
    def __init__(self, *results: ProcessResult | BaseException) -> None:
        self.results = list(results)
        self.calls: list[list[str]] = []

    def run(self, arguments: Any, **_: Any) -> ProcessResult:
        self.calls.append(list(arguments))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result
