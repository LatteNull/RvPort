from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tests.helpers import RISCV, X86, make_request

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.build_contexts import build_context
from floating_point_precision_scanner.profiles import ProfileRegistry
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request
from floating_point_precision_scanner.suppression import Suppression, apply_suppressions

ROOT = Path(__file__).resolve().parents[2]


def context_document(profile: Any, *, implementation: str = "fixture-libm") -> dict[str, Any]:
    return {
        "kind": "FloatingPointBuildContext",
        "schema_version": "1.0",
        "context_id": f"{implementation}-{profile.reference}",
        "base_profile_fingerprint": profile.fingerprint,
        "target_triple": profile.target_triple,
        "abi": profile.abi,
        "toolchain": {"name": "clang", "version": "21.1.8"},
        "libm": {
            "status": "known",
            "value": {
                "implementation": implementation,
                "version": "test-only",
                "errno": True,
                "exceptions": True,
                "special_values": "iec60559",
            },
            "source": "unit-test-fixture",
        },
        "environment": {
            "status": "known",
            "value": {"thread_local": True, "exception_flags": True},
            "source": "unit-test-fixture",
        },
        "target_features": {
            "status": "known",
            "value": {"architecture": profile.target_triple.split("-")[0]},
            "source": "unit-test-fixture",
        },
        "sources": {"fixture": "unit-test-only"},
    }


def test_build_context_schema_binding_and_fingerprint_ignore_materialization() -> None:
    profile = ProfileRegistry().get(X86)
    document = context_document(profile)
    assert SchemaRegistry().validate("build_context", document) == []
    left = copy.deepcopy(document)
    right = copy.deepcopy(document)
    left["materialization_root"] = "C:/one/sysroot"
    right["materialization_root"] = "D:/two/sysroot"
    first, errors = build_context(
        left,
        profile_fingerprint=profile.fingerprint,
        target_triple=profile.target_triple,
        abi=profile.abi,
    )
    second, repeated_errors = build_context(
        right,
        profile_fingerprint=profile.fingerprint,
        target_triple=profile.target_triple,
        abi=profile.abi,
    )
    assert errors == repeated_errors == []
    assert first is not None and second is not None and first.fingerprint == second.fingerprint
    assert "materialization_root" not in first.document
    assert first.capability("libm")["implementation"] == "fixture-libm"
    assert first.capability("missing") is None


def test_build_context_rejects_mismatch_and_missing_source() -> None:
    profile = ProfileRegistry().get(RISCV)
    document = context_document(profile)
    document["abi"] = "wrong"
    item, errors = build_context(
        document,
        profile_fingerprint=profile.fingerprint,
        target_triple=profile.target_triple,
        abi=profile.abi,
    )
    assert item is None and errors[0].diagnostic_code == "build_context_mismatch"
    document = context_document(profile)
    document["sources"] = {}
    item, errors = build_context(
        document,
        profile_fingerprint=profile.fingerprint,
        target_triple=profile.target_triple,
        abi=profile.abi,
    )
    assert item is None and errors[0].diagnostic_code == "build_context_source_missing"


def test_fixed_unknown_build_contexts_validate_without_host_inference() -> None:
    registry = ProfileRegistry()
    schemas = SchemaRegistry()
    for name, reference in (
        ("x86-unknown-libm.json", X86),
        ("riscv-unknown-libm.json", RISCV),
    ):
        document = json.loads(
            (ROOT / "tests" / "fixtures" / "build-context" / name).read_text(encoding="utf-8")
        )
        profile = registry.get(reference)
        assert schemas.validate("build_context", document) == []
        context, errors = build_context(
            document,
            profile_fingerprint=profile.fingerprint,
            target_triple=profile.target_triple,
            abi=profile.abi,
        )
        assert errors == [] and context is not None
        assert context.capability("libm") is None


def test_request_build_context_and_suppression_validation(tmp_path: Path) -> None:
    profiles = ProfileRegistry()
    document = make_request(tmp_path)
    document["schema_version"] = "1.3"
    document["build_contexts"] = {
        "source": context_document(profiles.get(X86)),
        "target": context_document(profiles.get(RISCV)),
    }
    document["suppressions"] = [
        {
            "code": "mixed-precision-conversion",
            "path": "src/*.c",
            "reason": "validated by project policy",
            "start_line": 4,
            "end_line": 7,
        }
    ]
    request, errors = parse_request(document, SchemaRegistry())
    assert errors == [] and request is not None
    assert request.source_build_context is not None
    assert request.suppressions[0].start_line == 4

    legacy = copy.deepcopy(document)
    legacy["schema_version"] = "1.2"
    assert parse_request(legacy, SchemaRegistry())[1][0].diagnostic_code == (
        "build_context_version_unsupported"
    )

    document["suppressions"][0]["reason"] = "   "
    assert parse_request(document, SchemaRegistry())[1][0].diagnostic_code == "invalid_suppression"
    document["suppressions"][0]["reason"] = "reason"
    document["suppressions"][0]["path"] = "../outside.c"
    assert parse_request(document, SchemaRegistry())[1][0].diagnostic_code == "invalid_suppression"

    document["suppressions"][0]["path"] = "src/value.c"
    document["suppressions"][0].pop("end_line")
    assert parse_request(document, SchemaRegistry())[1][0].diagnostic_code == "invalid_suppression"

    document["suppressions"][0]["end_line"] = 7
    document["suppressions"].append(copy.deepcopy(document["suppressions"][0]))
    assert parse_request(document, SchemaRegistry())[1][0].diagnostic_code == "invalid_suppression"


class _UnusedFrontend:
    def verify(self) -> None:
        raise AssertionError("validation must stop before the frontend")


def test_scanner_rejects_profile_context_mismatch_before_frontend(tmp_path: Path) -> None:
    profiles = ProfileRegistry()
    document = make_request(tmp_path)
    document["schema_version"] = "1.3"
    target = context_document(profiles.get(RISCV))
    target["base_profile_fingerprint"] = "0" * 64
    document["build_contexts"] = {"target": target}
    errors = Scanner(_UnusedFrontend()).validate_request(document)  # type: ignore[arg-type]
    assert errors[0].diagnostic_code == "build_context_mismatch"
    result = Scanner(_UnusedFrontend()).scan(document)  # type: ignore[arg-type]
    assert result["scan"]["status"] == "invalid_request"
    assert result["diagnostics"][0]["code"] == "build_context_mismatch"


def test_suppression_is_applied_after_stable_finding_identity() -> None:
    finding = {
        "finding_id": "a" * 64,
        "finding_code": "mixed-precision-conversion",
        "location": {"path": "src/value.c", "line": 5, "column": 2},
    }
    visible, records = apply_suppressions(
        [finding],
        [Suppression("mixed-precision-conversion", "src/*.c", "reviewed", 5, 5)],
    )
    assert visible == ()
    assert records[0]["finding_id"] == finding["finding_id"]
    assert records[0]["reason"] == records[0]["reason_en"] == "reviewed"
    repeated = apply_suppressions(
        [finding],
        [Suppression("mixed-precision-conversion", "src/*.c", "different text", 5, 5)],
    )
    assert repeated[1][0]["suppression_id"] == records[0]["suppression_id"]
    assert Suppression("fragile-fp-comparison", "src/*.c", "x").matches(finding) is False


def test_suppression_match_rejects_missing_or_invalid_locations_and_ranges() -> None:
    suppression = Suppression("mixed-precision-conversion", "src/*.c", "reviewed", 5, 7)
    base = {"finding_code": "mixed-precision-conversion"}
    assert suppression.matches(base) is False
    assert suppression.matches({**base, "location": {"expansion": "invalid"}}) is False
    assert suppression.matches({**base, "location": {"path": "other.c", "line": 6}}) is False
    assert suppression.matches({**base, "location": {"path": "src/value.c", "line": 4}}) is False
    assert suppression.matches({**base, "location": {"path": "src/value.c", "line": 6}})


def test_suppression_record_budget_keeps_unrecorded_candidates_visible() -> None:
    findings = [
        {
            "finding_id": character * 64,
            "finding_code": "fragile-fp-comparison",
            "location": {"path": "src/value.c", "line": line, "column": 1},
        }
        for character, line in (("a", 5), ("b", 6))
    ]
    visible, records = apply_suppressions(
        findings,
        [Suppression("fragile-fp-comparison", "src/*.c", "reviewed")],
        max_records=1,
    )
    assert len(records) == 1
    assert [item["finding_id"] for item in visible] == ["b" * 64]


def test_source_suppression_extraction_is_strict_and_bilingual() -> None:
    valid = {
        "fact_kind": "suppression",
        "payload": {
            "code": "fragile-fp-comparison",
            "reason": "reviewed",
            "target_line": 8,
        },
        "location": {"expansion": {"path": "src/value.c", "line": 7, "column": 1}},
    }
    malformed = [
        None,
        {"fact_kind": "call"},
        {"fact_kind": "suppression", "payload": None, "location": {}},
        {
            "fact_kind": "suppression",
            "payload": {"code": "unknown", "reason": "", "target_line": None},
            "location": {"expansion": "invalid"},
        },
    ]
    suppressions, diagnostics = Scanner._source_suppressions(
        [{"facts": [*malformed, valid]}]  # type: ignore[list-item]
    )
    assert suppressions == (
        Suppression("fragile-fp-comparison", "src/value.c", "reviewed", 8, 8, "source"),
    )
    assert len(diagnostics) == 1
    assert diagnostics[0].message and diagnostics[0].message_en
