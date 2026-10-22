from __future__ import annotations

import json
from pathlib import Path

from floating_point_precision_scanner.output import serialize_json
from floating_point_precision_scanner.protocol import SchemaRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_request_example_matches_schema() -> None:
    for name in ("scan-request.json", "core-scan-request.json"):
        document = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
        assert SchemaRegistry().validate("request", document) == []


def test_result_example_matches_schema_and_is_deterministic() -> None:
    document = json.loads((ROOT / "examples" / "scan-result.json").read_text(encoding="utf-8"))
    assert SchemaRegistry().validate("result", document) == []
    assert serialize_json(document) == serialize_json(json.loads(serialize_json(document)))
    assert document["findings"] == []
    assert document["schemaVersion"] == "2.0"
    assert document["scan"]["analysisScope"] == "factsOnly"
    assert set(document["extensions"]) == {
        "org.rvport.floating-point-scanner.analysis",
        "org.rvport.floating-point-scanner.profiles",
        "org.rvport.floating-point-scanner.artifacts",
        "org.rvport.floating-point-scanner.suppressions",
        "org.rvport.floating-point-scanner.runtime",
    }
