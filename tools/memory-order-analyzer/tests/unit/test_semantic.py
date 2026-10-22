"""Consumer validation uses synthetic graphs, independent of LLVM integration."""
from copy import deepcopy
import json
import pytest
from conftest import success
from memory_order_analyzer.contracts import AnalysisError, validate, document, file_hash
from memory_order_analyzer.protocol import expected_protocol, check_worker
from memory_order_analyzer import pipeline, scope, quality
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.report import make_report


@pytest.fixture
def graph(fixture_module):
    m = fixture_module
    def node(id_, kind="instruction", owner="f", block="b", operands=(), **details):
        return {"id": id_, "kind": kind, "type": "i32", "type_kind": "integer", "bits": 32,
                "function": owner, "block": block, "operands": list(operands), "details": details, "status": "known"}
    m["values"] = [node("arg", "argument", block=None, position=0),
                   node("phi", operands=["arg", "phi"], opcode="phi", incoming=[{"value_ref": "arg", "predecessor": "entry"}, {"value_ref": "phi", "predecessor": "b"}]),
                   node("int", "integer", None, None, hex="FFFFFFFF"),
                   {**node("ptr", "null", None, None), "type": "ptr", "type_kind": "pointer", "address_space": 0},
                   node("unknown", "unknown", None, None)]
    m["values"][-1].update(status="unknown", reason="unsupported_value")
    def block(name, target):
        return {"id": name, "successors": [target], "terminator": {"id": name + ":i9", "opcode": "br", "condition_ref": None,
                "return_ref": None, "status": "known", "edges": [{"ordinal": 0, "target": target, "kind": "unconditional", "condition_ref": None, "case_ref": None}]}}
    m["functions"] = [{"id": "f", "name": "f", "linkage": "external", "declaration": False, "comdat": False,
                       "parameters": ["arg"], "return_type": "void", "vararg": False, "blocks": [block("entry", "b"), block("b", "b")]}]
    m["globals"] = [{"id": "global", "name": "global", "linkage": "external", "declaration": False, "comdat": False,
                     "initializer": {"state": "value", "value_ref": "int"}}]
    m["events"] = [{"id": "e", "kind": "store", "function": "f", "block": "b", "inputs": {"value": "phi"}, "result_ref": None,
                    "range_status": "available", "ranges": [{"role": "write", "address_ref": "ptr", "address_space": 0, "alignment": 4,
                    "size": {"status": "known", "bytes": "4"}}], "source": {"inline_chain": []}}]
    m["calls"] = [{"id": "c", "kind": "indirect", "target": None, "function": "f", "called_ref": "ptr", "arguments": ["phi", "unknown"],
                   "result_ref": None, "function_type": "void (i32, ...)", "calling_convention": 0, "normal": "b", "unwind": "b", "tail": "none",
                   "attributes": "", "attribute_status": "not_applicable", "bundles": [{"tag": "deopt", "inputs": ["int"]}], "status": "unknown", "source": {"inline_chain": []}}]
    m["extraction"].update(status="partial", roots=3, nodes=5, references=2, unknown=1, diagnostics=[{"id": "unknown", "reason": "unsupported_value"}])
    return m


def test_valid_graph_and_per_kind_versions(graph, fixture_context, fixture_artifact):
    assert validate(graph, "ModuleFacts") is graph
    for kind, value in [("TUManifest", fixture_context), ("BCArtifact", fixture_artifact), ("ModuleFacts", graph), ("RunReport", make_report("doctor", ready=True))]:
        assert validate(value, kind) is value
        for version in [0, 3, True, None, 1 if kind in ("ModuleFacts", "RunReport") else 2]:
            with pytest.raises(AnalysisError, match="schema_version"):
                validate({**value, "schema_version": version}, kind)
    legacy = make_report("doctor", ready=True)
    legacy.pop("fact_extraction")
    with pytest.raises(AnalysisError):
        validate(legacy, "RunReport")
    for field in ("values", "protocol", "extraction"):
        invalid = deepcopy(graph)
        invalid.pop(field)
        with pytest.raises(AnalysisError):
            validate(invalid, "ModuleFacts")


@pytest.mark.parametrize("mutation", [
    lambda m: m["protocol"].update(extractor_version="old"),
    lambda m: m["values"].append(deepcopy(m["values"][0])),
    lambda m: m["functions"].append(deepcopy(m["functions"][0])),
    lambda m: m["functions"][0]["blocks"].append(deepcopy(m["functions"][0]["blocks"][0])),
    lambda m: m["values"][1]["operands"].append("absent"),
    lambda m: m["values"][0].update(function="foreign"),
    lambda m: m["values"][0]["details"].update(position=2),
    lambda m: m["values"][1].update(block="absent"),
    lambda m: m["values"][2]["details"].update(hex="not hex"),
    lambda m: m["values"][2].update(bits=1),
    lambda m: m["values"][4].pop("reason"),
    lambda m: m["extraction"].update(diagnostics=[]),
    lambda m: m["values"][1]["details"].update(incoming=[{}]),
    lambda m: m["values"][1]["details"]["incoming"][0].update(predecessor="absent"),
    lambda m: m["values"][1]["details"]["incoming"][0].update(value_ref="int"),
    lambda m: m["functions"][0]["blocks"][0]["terminator"].update(id="wrong"),
    lambda m: m["functions"][0]["blocks"][0]["terminator"]["edges"][0].update(target="absent"),
    lambda m: m["functions"][0]["blocks"][0]["terminator"]["edges"][0].update(ordinal=2),
    lambda m: m["functions"][0]["blocks"][0]["terminator"].update(condition_ref="absent"),
    lambda m: m["globals"][0].update(declaration=True),
    lambda m: m["globals"][0]["initializer"].update(value_ref="arg"),
    lambda m: m["events"].append(deepcopy(m["events"][0])),
    lambda m: m["events"][0].update(function="absent"),
    lambda m: m["events"][0].update(block="absent"),
    lambda m: m["events"][0]["inputs"].update(value="absent"),
    lambda m: m["events"][0]["ranges"][0].update(address_space=1),
    lambda m: m["events"][0]["ranges"][0]["size"].update(bytes="-1"),
    lambda m: m["events"][0]["ranges"][0]["size"].update(status="unknown"),
    lambda m: m["calls"][0].update(normal="absent"),
    lambda m: m["calls"][0].update(called_ref="absent"),
    lambda m: m["calls"][0]["bundles"][0].update(inputs=["absent"]),
    lambda m: m["extraction"].update(nodes=9),
    lambda m: m["extraction"].update(references=9),
    lambda m: m["extraction"].update(unknown=9),
    lambda m: m["extraction"].update(status="complete"),
    lambda m: m["extraction"]["diagnostics"].append({"id": "absent", "reason": "test"}),
])
def test_invalid_graph_rejected(graph, mutation):
    mutation(graph)
    with pytest.raises(AnalysisError):
        validate(graph, "ModuleFacts")


def test_metadata_handshake_and_doctor(tmp_path):
    from memory_order_analyzer.toolchain import doctor
    path = tmp_path / "protocol.json"
    for value in (None, [], {}, {**expected_protocol(), "policy": {}}, {**expected_protocol(), "policy": {**expected_protocol()["policy"], "max_nodes": 0}}):
        path.write_text(json.dumps(value))
        with pytest.raises(AnalysisError, match="extractor-protocol"):
            expected_protocol(path)
    path.unlink()
    with pytest.raises(AnalysisError):
        expected_protocol(path)
    path.write_text(json.dumps(expected_protocol()))
    assert expected_protocol(path) == expected_protocol()
    runner = lambda *a, **k: success(json.dumps(expected_protocol()))
    assert check_worker("worker", tmp_path, runner) == expected_protocol()
    for output in (success("bad"), success("{}"), success(code=1), {}):
        with pytest.raises(AnalysisError, match="rebuild"):
            check_worker("worker", tmp_path, lambda *a, **k: output)
    result = doctor("worker", finder=lambda n: "/usr/bin/" + n, runner=lambda argv, *a, **k: success("{}" if "--protocol" in argv else "LLVM 21.1.8"))
    assert not result["ready"] and result["failures"][-1]["code"] == "worker_protocol"


def test_import_rekey_idempotence_and_scope(graph, fixture_artifact, tmp_path):
    bc = tmp_path / "input.bc"
    bc.write_bytes(b"BC\xc0\xdetest bitcode")
    old = deepcopy(fixture_artifact)
    old.update(sha256=file_hash(bc), lineage=["c" * 64])
    # The fixture runner returns an empty but valid current graph; no old facts are migrated.
    empty = {**graph, "functions": [], "globals": [], "events": [], "calls": [], "values": [],
             "extraction": {"status": "complete", "roots": 0, "nodes": 0, "references": 0, "unknown": 0, "diagnostics": []}}
    def runner(argv, *a, **k):
        return success(json.dumps(expected_protocol() if "--protocol" in argv else {**empty, "artifact_key": argv[2], "module_hash": file_hash(bc)}))
    original = deepcopy(old)
    artifact, facts = pipeline.import_bc(bc, OutputStore(tmp_path / "new"), "worker", manifest=old, runner=runner)
    assert old == original and artifact["artifact_key"] != old["artifact_key"]
    assert artifact["lineage"] == sorted([old["artifact_key"], "c" * 64])
    for field in ("context_id", "profile", "provenance", "inputs"):
        assert artifact[field] == old[field]
    again, _ = pipeline.import_bc(bc, OutputStore(tmp_path / "again"), "worker", manifest=artifact, runner=runner)
    assert again["artifact_key"] == artifact["artifact_key"] and again["lineage"] == artifact["lineage"]
    assert make_report("import-bc", planned=1, artifacts=[artifact], facts=[facts])["artifact_migrations"] == [{"from": old["artifact_key"], "to": artifact["artifact_key"]}]
    unknown, _ = pipeline.import_bc(bc, OutputStore(tmp_path / "unknown"), "worker", runner=runner)
    assert unknown["provenance"] == "unknown" and "migration_from" not in unknown["toolchain"]
    a, b = artifact["artifact_key"], old["artifact_key"]
    manifest = document("ScopeManifest", members=[a, b], target_id="app", evidence="explicit", closed=True, external_boundaries=[])
    with pytest.raises(AnalysisError, match="ancestry"):
        scope.preflight(manifest, {a: artifact, b: old}, {a: facts, b: {**facts, "artifact_key": b}})
    with pytest.raises(AnalysisError, match="schema_version"):
        scope.preflight({**manifest, "members": [a]}, {a: artifact}, {a: {**facts, "schema_version": 1}})


def test_report_v2_denominators_and_partial(graph, fixture_module, fixture_artifact):
    complete = deepcopy(fixture_module)
    complete["extraction"].update(status="complete", unknown=0, diagnostics=[])
    for facts, failures, expected in [([complete], [], 0), ([graph], [], 2), ([], [{"code": "extraction_budget_exceeded"}], 1)]:
        for m in facts:
            m["source_mapping"] = "complete"
        result = make_report("collect", planned=1, facts=facts, artifacts=[fixture_artifact] if facts else [], failures=failures)
        assert result["exit_code"] == expected
        assert result["schema_version"] == 2
        assert result["semantic_analysis"] == "not_run" and result["safety"] == "not_evaluated" and result["findings"] is None
    result = make_report("collect", planned=4, facts=[complete, graph], artifacts=[fixture_artifact] * 2, failures=[{"code": "timed_out"}])
    assert result["fact_extraction"]["complete_ratio"] == .25
    assert result["fact_extraction"]["failed"] == 2 and result["fact_extraction"]["partial"] == 1
    assert make_report("doctor", ready=True)["fact_extraction"]["status"] == "not_run"
    assert make_report("collect")["fact_extraction"]["complete_ratio"] is None


def test_truncated_worker(fixture_module, tmp_path):
    bc = tmp_path / "input.bc"
    bc.write_bytes(b"bitcode")
    for result in (success("{"), {"status": "timed_out", "code": "timed_out", "stderr": "timeout", "stdout": ""}):
        def runner(argv, *a, **k):
            return success(json.dumps(expected_protocol())) if "--protocol" in argv else result
        with pytest.raises(AnalysisError) as caught:
            pipeline.read_facts(bc, "a" * 64, "worker", runner=runner)
        assert caught.value.code in ("worker_protocol", "timed_out")


def test_recursive_source_inventory_and_executable_headers(tmp_path):
    for name in ("src/nested/a.cpp", "src/nested/code.hpp", "src/unused.inc", "python/nested/unused.py", "python/other/never_loaded.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int unused() { return 1; }" if name.startswith("src") else "unused = 1")
    sources = quality.owned_sources(tmp_path)
    assert len(sources["cpp"]) == 3 and len(sources["python"]) == 2
    for filename in ("python.json", "cpp.json"):
        (tmp_path / filename).write_text(json.dumps({"files": {}} if filename.startswith("python") else {"data": [{"files": []}]}))
    with pytest.raises(AnalysisError, match="owned source"):
        quality.evaluate(tmp_path, tmp_path / "python.json", tmp_path / "cpp.json")
