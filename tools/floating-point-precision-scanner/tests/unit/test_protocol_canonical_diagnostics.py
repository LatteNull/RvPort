from __future__ import annotations

import math
from pathlib import Path

import pytest
from tests.helpers import make_request

from floating_point_precision_scanner.canonical import (
    canonical_json,
    finding_id,
    normalize_repo_path,
    semantic_digest,
    stable_id,
    stable_sorted,
)
from floating_point_precision_scanner.diagnostics import (
    Diagnostic,
    aggregate_diagnostics,
    diagnostic,
    sanitize_text,
)
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request


def test_canonical_json_and_ids_are_stable(tmp_path: Path) -> None:
    assert canonical_json({"b": 2, "a": "中文"}) == '{"a":"中文","b":2}'
    assert semantic_digest({"b": 2, "a": 1}) == semantic_digest({"a": 1, "b": 2})
    assert stable_id("x", {"v": 1}) != stable_id("y", {"v": 1})
    first = finding_id("rule", "1", "a.c", 1, {"x": 1})
    assert first == finding_id("rule", "1", "a.c", 1, {"x": 1})
    assert first != finding_id("rule", "2", "a.c", 1, {"x": 1})
    assert stable_sorted([{"x": 2}, {"x": 1}], key=lambda item: item["x"]) == [{"x": 1}, {"x": 2}]
    nested = tmp_path / "src" / "a.c"
    nested.parent.mkdir()
    nested.touch()
    assert normalize_repo_path(nested, tmp_path) == "src/a.c"
    assert normalize_repo_path("src/a.c", tmp_path) == "src/a.c"


def test_canonical_rejects_nan_and_root_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        canonical_json({"bad": math.nan})
    with pytest.raises(ValueError, match="path_outside_project_root"):
        normalize_repo_path(tmp_path.parent / "outside.c", tmp_path)


def test_diagnostics_require_bilingual_fields_and_positive_count() -> None:
    with pytest.raises(ValueError, match="bilingual"):
        Diagnostic("x", "stage", "error", "", "en", "建议", "suggestion")
    with pytest.raises(ValueError, match="positive"):
        Diagnostic("x", "stage", "error", "中", "en", "建议", "suggestion", count=0)


def test_diagnostic_aggregation_and_sanitization(tmp_path: Path) -> None:
    first = diagnostic("x", "stage", "中", "en", severity="warning")
    second = diagnostic("x", "stage", "中", "en", severity="warning")
    other = diagnostic("a", "alpha", "甲", "a")
    aggregated = aggregate_diagnostics([first, second, other])
    assert [item.diagnostic_code for item in aggregated] == ["a", "x"]
    assert aggregated[1].count == 2
    assert aggregated[0].to_dict()["message_en"] == "a"
    text = f"token=abc {tmp_path / 'source.c'} C:\\private\\outside.txt"
    safe = sanitize_text(text, tmp_path)
    assert "abc" not in safe
    assert "<project_root>" in safe
    assert "private" not in safe
    assert len(sanitize_text("x" * 3000)) == 2048


def test_schema_registry_loads_caches_and_rejects_unknown() -> None:
    registry = SchemaRegistry()
    assert registry.schema("request") is registry.schema("request")
    with pytest.raises(KeyError):
        registry.schema("missing")


def test_parse_valid_request(tmp_path: Path) -> None:
    document = make_request(tmp_path)
    request, errors = parse_request(document, SchemaRegistry())
    assert errors == []
    assert request is not None
    assert request.project_root == tmp_path.resolve()
    assert request.rules_enabled == ()


def test_parse_request_aggregates_schema_errors(tmp_path: Path) -> None:
    document = make_request(tmp_path)
    document["schema_version"] = "2.0"
    del document["target_profile"]
    document["unknown"] = True
    request, errors = parse_request(document, SchemaRegistry())
    assert request is None
    assert len(errors) == 3
    assert all(item.diagnostic_code == "schema_validation_error" for item in errors)


@pytest.mark.parametrize("rules", [{"enabled": ["x"]}, {"disabled": ["x"]}])
def test_parse_request_rejects_rules(tmp_path: Path, rules: dict[str, list[str]]) -> None:
    document = make_request(tmp_path)
    document["rules"] = rules
    request, errors = parse_request(document, SchemaRegistry())
    assert request is None
    assert errors[0].diagnostic_code == "rules_not_available"
