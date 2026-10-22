from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from tests.helpers import add_bitcode_artifact_set, make_request, rewrite_manifest

from floating_point_precision_scanner.artifacts import ArtifactInputError, load_artifact_plan
from floating_point_precision_scanner.compilation import load_compilation_plan
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request


def load(request: dict[str, Any]):  # type: ignore[no-untyped-def]
    parsed, errors = parse_request(request, SchemaRegistry())
    assert parsed is not None and not errors and parsed.bitcode_artifact_set is not None
    compilation = load_compilation_plan(parsed)
    return load_artifact_plan(
        parsed.bitcode_artifact_set,
        compilation,
        SchemaRegistry(),
        source_revision=parsed.source_revision,
        max_bytes=int(parsed.budgets.get("max_bitcode_bytes", 536_870_912)),
    )


def code(request: dict[str, Any]) -> str:
    with pytest.raises(ArtifactInputError) as error:
        load(request)
    return error.value.diagnostics[0].diagnostic_code


def test_loads_and_orders_valid_artifact_set(tmp_path: Path) -> None:
    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path))
    plan = load(request)
    assert plan.artifact_set_id == "a" * 64
    assert plan.members[0].profile == "source-preserving"
    assert plan.failed_count == 0


def test_manifest_missing_hash_and_json_failures(tmp_path: Path) -> None:
    request, manifest, _ = add_bitcode_artifact_set(make_request(tmp_path))
    request["bitcode_artifact_set"]["manifest"] = "absent.json"
    assert code(request) == "artifact_manifest_missing"
    request, manifest, _ = add_bitcode_artifact_set(make_request(tmp_path / "hash"))
    request["bitcode_artifact_set"]["manifest_sha256"] = "0" * 64
    assert code(request) == "artifact_manifest_integrity_mismatch"
    request, manifest, _ = add_bitcode_artifact_set(make_request(tmp_path / "json"))
    manifest.write_text("{", encoding="utf-8")
    request["bitcode_artifact_set"]["manifest_sha256"] = hashlib.sha256(
        manifest.read_bytes()
    ).hexdigest()
    assert code(request) == "artifact_manifest_invalid_json"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda d: d.update(source_revision="other"), "artifact_source_revision_mismatch"),
        (
            lambda d: d.update(compile_commands_sha256="0" * 64),
            "artifact_compile_context_mismatch",
        ),
        (
            lambda d: d["counts"].update(planned=2),
            "artifact_manifest_count_mismatch",
        ),
        (lambda d: d.update(status="PARTIAL"), "artifact_manifest_status_mismatch"),
        (
            lambda d: d["producer"]["analysis_compiler"].update(version="20.0.0"),
            "artifact_toolchain_mismatch",
        ),
        (
            lambda d: d["members"].append(dict(d["members"][0])),
            "artifact_manifest_count_mismatch",
        ),
        (
            lambda d: d["members"][0].update(context_id="f" * 64),
            "artifact_translation_unit_mismatch",
        ),
        (
            lambda d: d["members"][0].update(language="c++"),
            "artifact_language_mismatch",
        ),
        (
            lambda d: d["members"][0].update(target="riscv64-unknown-linux-gnu"),
            "artifact_target_mismatch",
        ),
        (
            lambda d: d["members"][0].update(profile_version="2.0"),
            "artifact_profile_capability_mismatch",
        ),
        (
            lambda d: d["members"][0].update(capabilities=[]),
            "artifact_profile_capability_mismatch",
        ),
    ],
)
def test_manifest_consistency_failures(tmp_path: Path, mutation: Any, expected: str) -> None:
    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path))
    mutation(document)
    rewrite_manifest(request, manifest, document)
    assert code(request) == expected


def test_duplicate_and_missing_required_profile(tmp_path: Path) -> None:
    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "duplicate"))
    duplicate = dict(document["members"][0])
    document["members"].append(duplicate)
    document["counts"] = {"planned": 2, "completed": 2, "failed": 0}
    rewrite_manifest(request, manifest, document)
    assert code(request) == "artifact_manifest_duplicate_member"

    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "missing"))
    request["bitcode_artifact_set"]["required_profiles"] = ["build-faithful"]
    assert code(request) == "artifact_required_profile_missing"


def test_member_integrity_size_budget_and_path_escape(tmp_path: Path) -> None:
    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "integrity"))
    (tmp_path / "integrity" / "artifacts" / "main.bc").write_bytes(b"changed")
    assert code(request) == "bitcode_integrity_mismatch"

    request, _, _ = add_bitcode_artifact_set(make_request(tmp_path / "budget"))
    request["budgets"] = {"max_bitcode_bytes": 1}
    assert code(request) == "bitcode_too_large"

    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "total"))
    second = dict(document["members"][0])
    second.update(profile="build-faithful", artifact_key="e" * 64)
    document["members"].append(second)
    document["counts"] = {"planned": 2, "completed": 2, "failed": 0}
    request["bitcode_artifact_set"]["required_profiles"] = [
        "source-preserving",
        "build-faithful",
    ]
    request["budgets"] = {"max_bitcode_bytes": len(b"BC fixture") + 1}
    rewrite_manifest(request, manifest, document)
    assert code(request) == "bitcode_total_too_large"

    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "escape"))
    outside = tmp_path / "outside.bc"
    outside.write_bytes(b"outside")
    document["members"][0].update(
        path="../../outside.bc",
        size_bytes=len(b"outside"),
        sha256=hashlib.sha256(b"outside").hexdigest(),
    )
    rewrite_manifest(request, manifest, document)
    assert code(request) == "artifact_path_escape"

    for value in (str(outside.resolve()), "https://example.test/main.bc", "user@host:main.bc"):
        request, manifest, document = add_bitcode_artifact_set(
            make_request(tmp_path / hashlib.sha256(value.encode()).hexdigest()[:8])
        )
        document["members"][0]["path"] = value
        rewrite_manifest(request, manifest, document)
        assert code(request) == "artifact_path_not_relative"

    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "directory"))
    directory = manifest.parent / "member-dir"
    directory.mkdir()
    document["members"][0].update(path=directory.name, size_bytes=1, sha256="0" * 64)
    rewrite_manifest(request, manifest, document)
    assert code(request) == "bitcode_not_regular_file"


def test_sidecar_is_verified_and_partial_failures_are_preserved(tmp_path: Path) -> None:
    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "sidecar"))
    sidecar = manifest.parent / "bindings.json"
    sidecar_bytes = json.dumps(
        {
            "kind": "FloatingPointBindingSidecar",
            "schema_version": "1.0",
            "artifact_key": "b" * 64,
            "context_id": document["members"][0]["context_id"],
            "source_fact_bundle_digest": "c" * 64,
            "ir_fact_bundle_digest": "d" * 64,
            "bindings": [],
        }
    ).encode()
    sidecar.write_bytes(sidecar_bytes)
    document["members"][0]["binding_sidecar"] = {
        "path": sidecar.name,
        "size_bytes": len(sidecar_bytes),
        "sha256": hashlib.sha256(sidecar_bytes).hexdigest(),
        "schema_version": "1.0",
    }
    rewrite_manifest(request, manifest, document)
    assert load(request).members[0].sidecar_path == sidecar
    sidecar.write_text("changed", encoding="utf-8")
    assert code(request) == "binding_sidecar_integrity_mismatch"

    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path / "partial"))
    member = document["members"][0]
    document["failures"] = [
        {
            "physical_tu_id": member["physical_tu_id"],
            "context_id": member["context_id"],
            "profile": "build-faithful",
            "code": "producer_failed",
            "detail": "生产失败。",
            "detail_en": "Production failed.",
        }
    ]
    document["status"] = "PARTIAL"
    document["counts"] = {"planned": 2, "completed": 1, "failed": 1}
    request["bitcode_artifact_set"]["required_profiles"] = [
        "source-preserving",
        "build-faithful",
    ]
    rewrite_manifest(request, manifest, document)
    plan = load(request)
    assert plan.failed_count == 1
    assert plan.diagnostics[0].message_en == "Production failed."


@pytest.mark.parametrize(
    ("status", "expected", "retryable"),
    [
        ("MISSING", "artifact_not_ready", True),
        ("QUEUED", "artifact_not_ready", True),
        ("GENERATING", "artifact_not_ready", True),
        ("FAILED", "artifact_generation_failed", False),
    ],
)
def test_non_consumable_states(tmp_path: Path, status: str, expected: str, retryable: bool) -> None:
    request, manifest, document = add_bitcode_artifact_set(make_request(tmp_path))
    member = document["members"].pop()
    if status == "FAILED":
        document["failures"] = [
            {
                "physical_tu_id": member["physical_tu_id"],
                "context_id": member["context_id"],
                "profile": member["profile"],
                "code": "producer_failed",
                "detail": "生产失败。",
                "detail_en": "Production failed.",
            }
        ]
        document["counts"] = {"planned": 1, "completed": 0, "failed": 1}
    else:
        document["counts"] = {"planned": 0, "completed": 0, "failed": 0}
    document["status"] = status
    rewrite_manifest(request, manifest, document)
    with pytest.raises(ArtifactInputError) as error:
        load(request)
    assert error.value.diagnostics[0].diagnostic_code == expected
    assert error.value.diagnostics[0].retryable is retryable
