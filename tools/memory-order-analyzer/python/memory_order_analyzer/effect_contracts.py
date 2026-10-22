"""Independent P2 structural contracts; never upgrades or rewrites P1 facts."""

import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError
from .effect_bounds import bounded_values

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("EffectAnalysisRequest", "LocalAnalysisFacts", "LocalEvaluationRequest",
         "LocalEvaluationResult", "EffectSummary", "EffectAnalysisReport")


def expected_analysis_protocol(path=ROOT / "protocols/analysis-protocol.json"):
    try:
        protocol = json.loads(Path(path).read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas/effects.json").read_text(encoding="utf-8"))
        expected_budgets = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {"protocol_version": 1, "analysis_version": "0.1.0", "llvm_version": "21.1.8",
                    "policy_id": "scoped-effects-v1", "kinds": dict.fromkeys(KINDS, 1), "budgets": expected_budgets}
        # JSON canonical comparison also distinguishes booleans from integers.
        if json.dumps(protocol, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise ValueError("Analysis protocol does not match supported schemas")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AnalysisError("analysis_protocol", "Invalid or missing protocols/analysis-protocol.json") from exc
    return protocol


def validate_effect_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown effect contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    values = bounded_values(value)
    schema = json.loads((ROOT / "schemas/effects.json").read_text(encoding="utf-8"))
    # Validate operands iteratively, not through recursive oneOf descent. Each
    # operand is still required to match Value; this is not a schema exclusion.
    schema["$defs"]["Value"]["oneOf"][-1]["properties"]["operands"]["items"] = {}
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/Value", "$defs": schema["$defs"]})
        for item in values:
            validator.validate(item)
            if item["kind"] == "expression":
                for operand in item["operands"]:
                    validator.validate(operand)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    return value


def effect_document(kind, **fields):
    protocol = expected_analysis_protocol()
    return validate_effect_document({"kind": kind, "schema_version": 1,
        "analysis_version": protocol["analysis_version"], "policy_id": protocol["policy_id"], **fields}, kind)


def read_effect_document(path, kind):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("input_invalid", str(exc)) from exc
    return validate_effect_document(value, kind)
