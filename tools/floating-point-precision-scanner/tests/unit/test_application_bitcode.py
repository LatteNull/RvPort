from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.helpers import add_bitcode_artifact_set, ast_for, make_request, rewrite_manifest
from tests.unit.test_ir_worker_evidence import ir_bundle

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.diagnostics import diagnostic
from floating_point_precision_scanner.frontend import FrontendFailure
from floating_point_precision_scanner.ir_worker import IrWorkerFailure
from floating_point_precision_scanner.protocol import SchemaRegistry

ANALYSIS = "org.rvport.floating-point-scanner.analysis"


class Frontend:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def verify(self) -> None:
        return None

    def ast(self, context: Any) -> dict[str, Any]:
        if self.fail:
            raise FrontendFailure(
                diagnostic(
                    "frontend_failed",
                    "frontend",
                    "源码失败。",
                    "Source failed.",
                    translation_unit_id=context.context_id,
                )
            )
        return ast_for(context.absolute_file)


class Worker:
    def __init__(self, *, fail_verify: bool = False, fail_extract: bool = False) -> None:
        self.fail_verify = fail_verify
        self.fail_extract = fail_extract
        self.calls = 0

    def verify(self) -> None:
        if self.fail_verify:
            raise IrWorkerFailure(diagnostic("worker_bad", "ir_worker", "失败。", "Failed."))

    def extract(
        self, _plan: Any, member: Any, *, max_facts: int, project_root: Path, **_: Any
    ) -> dict[str, Any]:
        self.calls += 1
        assert max_facts > 0
        assert project_root.is_absolute()
        if self.fail_extract:
            raise IrWorkerFailure(
                diagnostic(
                    "worker_read_failed",
                    "ir_worker",
                    "读取失败。",
                    "Read failed.",
                    translation_unit_id=member.context_id,
                )
            )
        bundle = ir_bundle(member.context_id)
        bundle["artifact"].update(
            physical_tu_id=member.document["physical_tu_id"],
            sha256=member.document["sha256"],
        )
        return bundle


def test_scanner_consumes_ir_and_builds_evidence_deterministically(tmp_path: Path) -> None:
    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path))
    worker = Worker()
    scanner = Scanner(Frontend(), ir_worker=worker)  # type: ignore[arg-type]
    first = scanner.scan(request)
    second = scanner.scan(request)
    assert first == second
    assert first["scan"]["status"] == "complete"
    assert first["findings"] == []
    assert first["summary"] == {
        "findings": 0,
        "suppressed": 0,
        "diagnostics": 1,
        "assessments": {
            "planned": 0,
            "completed": 0,
            "matched": 0,
            "notMatched": 0,
            "unknown": 0,
            "skipped": 0,
            "failed": 0,
        },
        "layers": {
            "artifact": {"planned": 1, "completed": 1, "failed": 0, "unknown": 0},
            "source": {"planned": 1, "completed": 1, "failed": 0, "unknown": 0},
            "ir": {"planned": 1, "completed": 1, "failed": 0, "unknown": 0},
            "evidence": {"planned": 1, "completed": 1, "failed": 0, "unknown": 0},
            "rules": {"planned": 0, "completed": 0, "failed": 0, "unknown": 0},
        },
    }
    analysis = first["extensions"][ANALYSIS]
    assert analysis["layers"]["ir"]["completed"] == 1
    assert len(analysis["bundleDigests"]["ir"]) == 1
    assert len(analysis["bundleDigests"]["evidence"]) == 1
    assert SchemaRegistry().validate("result", first) == []


def test_scan_identity_is_independent_of_materialization_root(tmp_path: Path) -> None:
    left, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "left"))
    right, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "right"))
    first = Scanner(Frontend(), ir_worker=Worker()).scan(left)  # type: ignore[arg-type]
    second = Scanner(Frontend(), ir_worker=Worker()).scan(right)  # type: ignore[arg-type]
    assert first == second
    serialized = str(first)
    assert str(tmp_path / "left") not in serialized
    assert str(tmp_path / "right") not in serialized


def test_scanner_handles_missing_and_failed_worker(tmp_path: Path) -> None:
    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "missing"))
    result = Scanner(Frontend()).scan(request)
    assert result["scan"]["status"] == "failed"
    assert result["extensions"][ANALYSIS]["layers"]["source"]["completed"] == 1
    assert result["extensions"][ANALYSIS]["layers"]["ir"]["failed"] == 1
    assert result["diagnostics"][0]["code"] == "ir_worker_unavailable"

    for worker, expected in (
        (Worker(fail_verify=True), "worker_bad"),
        (Worker(fail_extract=True), "worker_read_failed"),
    ):
        request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / expected))
        result = Scanner(Frontend(), ir_worker=worker).scan(request)  # type: ignore[arg-type]
        assert result["scan"]["status"] == "failed"
        assert any(item["code"] == expected for item in result["diagnostics"])


def test_scanner_rejects_artifact_and_ir_schema_errors(tmp_path: Path) -> None:
    request, manifest, _ = add_bitcode_artifact_set(make_request(tmp_path / "artifact"))
    request["bitcode_artifact_set"]["manifest_sha256"] = "0" * 64
    scanner = Scanner(Frontend(), ir_worker=Worker())  # type: ignore[arg-type]
    assert scanner.validate_request(request)[0].diagnostic_code == (
        "artifact_manifest_integrity_mismatch"
    )
    result = scanner.scan(request)
    assert result["scan"]["status"] == "invalid_request"

    class RejectIr(SchemaRegistry):
        def validate(self, name: str, document: Any):  # type: ignore[no-untyped-def]
            if name == "llvm_facts":
                return [diagnostic("bad_ir", "ir_validation", "无效。", "Invalid.")]
            return super().validate(name, document)

    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "ir"))
    result = Scanner(
        Frontend(),
        schemas=RejectIr(),
        ir_worker=Worker(),  # type: ignore[arg-type]
    ).scan(request)
    assert result["scan"]["status"] == "failed"
    assert result["extensions"][ANALYSIS]["layers"]["ir"]["failed"] == 1


def test_scanner_reports_missing_source_and_required_mapping(tmp_path: Path) -> None:
    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "source"))
    result = Scanner(
        Frontend(fail=True),
        ir_worker=Worker(),  # type: ignore[arg-type]
    ).scan(request)
    assert result["scan"]["status"] == "partial"
    assert result["extensions"][ANALYSIS]["layers"]["evidence"]["failed"] == 1
    assert any(
        item["code"] == "source_fact_bundle_missing" for item in result["diagnostics"]
    )

    class UnknownWorker(Worker):
        def extract(
            self, _plan: Any, member: Any, *, max_facts: int, project_root: Path, **_: Any
        ) -> dict[str, Any]:
            bundle = super().extract(_plan, member, max_facts=max_facts, project_root=project_root)
            bundle["facts"][0]["opcode"] = "unknown"
            return bundle

    request, _, _ = add_bitcode_artifact_set(
        make_request(tmp_path / "mapping"), source_mapping="required"
    )
    result = Scanner(
        Frontend(),
        ir_worker=UnknownWorker(),  # type: ignore[arg-type]
    ).scan(request)
    assert result["scan"]["status"] == "partial"
    assert result["extensions"][ANALYSIS]["layers"]["evidence"]["unknown"] == 1
    assert any(
        item["code"] == "source_mapping_incomplete" for item in result["diagnostics"]
    )


def test_scanner_rejects_worker_identity_and_module_mismatch(tmp_path: Path) -> None:
    class IdentityWorker(Worker):
        def extract(
            self, _plan: Any, member: Any, *, max_facts: int, project_root: Path, **_: Any
        ) -> dict[str, Any]:
            bundle = super().extract(_plan, member, max_facts=max_facts, project_root=project_root)
            bundle["artifact"]["artifact_key"] = "0" * 64
            return bundle

    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "identity"))
    result = Scanner(
        Frontend(),
        ir_worker=IdentityWorker(),  # type: ignore[arg-type]
    ).scan(request)
    assert any(
        item["code"] == "ir_fact_artifact_identity_mismatch"
        for item in result["diagnostics"]
    )

    class ModuleWorker(Worker):
        def extract(
            self, _plan: Any, member: Any, *, max_facts: int, project_root: Path, **_: Any
        ) -> dict[str, Any]:
            bundle = super().extract(_plan, member, max_facts=max_facts, project_root=project_root)
            bundle["module"]["target_triple"] = "wrong-target"
            return bundle

    module_root = tmp_path / "module"
    module_root.mkdir()
    (module_root / "main.c").write_text("double value;", encoding="utf-8")
    request = make_request(
        module_root,
        [
            {
                "file": "main.c",
                "directory": str(module_root),
                "arguments": [
                    "clang",
                    "--target=x86_64-unknown-linux-gnu",
                    "main.c",
                ],
            }
        ],
    )
    request, _, _ = add_bitcode_artifact_set(request)
    result = Scanner(
        Frontend(),
        ir_worker=ModuleWorker(),  # type: ignore[arg-type]
    ).scan(request)
    assert any(
        item["code"] == "ir_module_identity_mismatch" for item in result["diagnostics"]
    )

    class VersionWorker(Worker):
        def extract(
            self, _plan: Any, member: Any, *, max_facts: int, project_root: Path, **_: Any
        ) -> dict[str, Any]:
            bundle = super().extract(_plan, member, max_facts=max_facts, project_root=project_root)
            bundle["producer"]["extractor_version"] = "9.9"
            return bundle

    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "version"))
    result = Scanner(
        Frontend(),
        ir_worker=VersionWorker(),  # type: ignore[arg-type]
    ).scan(request)
    assert any(
        item["code"] == "ir_fact_producer_version_mismatch"
        for item in result["diagnostics"]
    )


def test_scanner_returns_failed_for_artifact_not_ready(tmp_path: Path) -> None:
    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path))
    document["members"] = []
    document["counts"] = {"planned": 0, "completed": 0, "failed": 0}
    document["status"] = "GENERATING"
    rewrite_manifest(request, manifest, document)
    result = Scanner(
        Frontend(),
        ir_worker=Worker(),  # type: ignore[arg-type]
    ).scan(request)
    assert result["scan"]["status"] == "failed"
    assert result["diagnostics"][0]["code"] == "artifact_not_ready"
    assert result["diagnostics"][0]["retryable"] is True
