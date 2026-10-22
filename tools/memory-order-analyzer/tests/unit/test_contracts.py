import json
import math
import pytest
from memory_order_analyzer import __version__
from memory_order_analyzer.contracts import *


def test_deterministic_serialization_and_hash(tmp_path):
    assert __version__ == "0.1.0"
    assert canonical({"z": 1, "a": 2}) == canonical({"a": 2, "z": 1})
    assert identity([1, 2]) != identity([2, 1])
    path = tmp_path / "large"
    path.write_bytes(b"x" * 2000000)
    assert file_hash(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        canonical(math.nan)


def test_contract_validation(tmp_path, fixture_module):
    assert validate(fixture_module, "ModuleFacts") is fixture_module
    for value in (None, {}, {"schema_version": 3}):
        with pytest.raises(AnalysisError, match="schema_version"):
            validate(value, "ModuleFacts")
    with pytest.raises(AnalysisError) as caught:
        validate({"schema_version": 2}, "ModuleFacts")
    assert caught.value.as_dict()["code"] == "schema_invalid"
    with pytest.raises(AnalysisError):
        validate(fixture_module, "Future")
    with pytest.raises(AnalysisError):
        validate({**fixture_module, "calls": [{"id": "x", "kind": "direct", "target": "f"}]}, "ModuleFacts")
    path = tmp_path / "data.json"
    path.write_text(json.dumps(fixture_module))
    assert read_document(path, "ModuleFacts") == fixture_module
    path.write_text("not json")
    with pytest.raises(AnalysisError):
        read_document(path, "ModuleFacts")
    with pytest.raises(AnalysisError):
        read_document(tmp_path / "absent", "ModuleFacts")
    validate_references(["a"], {"a": 1})
    with pytest.raises(AnalysisError, match="Missing references"):
        validate_references(["b"], {"a": 1})
