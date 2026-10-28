import json
from pathlib import Path

import pytest

import memory_order_analyzer.unified_adapters as adapters
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash, identity
from memory_order_analyzer.execution import OutputStore


def record(identifier="tu", *, language="c", standard="c17", family="clang"):
    return {"record_id": identifier, "physical_tu_id": "a" * 64, "producer": {"family": family},
            "compile_record_digest": "b" * 64, "language": language, "standard": standard,
            "target": {"triple": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64", "abi": {"name": "c", "cxx_abi": "itanium"}},
            "bitcode": {"sha256": "c" * 64}}


def scope(values=None):
    return {"target_id": "scope", "target_triple": "x86_64-pc-linux-gnu",
            "closed": True, "external_boundaries": [], "records": values or [record()]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")
    return path


def test_reference_copy_json_and_abi_helpers(tmp_path):
    value = {"schema_version": 1, "policy_id": "policy", "kind": "K"}
    assert adapters.dependency("K", "id", value)["digest"] == identity(value)
    assert adapters.evidence("K", "id", value, "a\\b")["path"] == "a/b"
    source = write(tmp_path / "a.json", value)
    assert adapters.hashed_input(source)["sha256"] == file_hash(source)
    assert adapters._json(source) == value
    with pytest.raises(AnalysisError, match="Invalid adapter"):
        adapters._json(tmp_path / "missing")
    store = OutputStore(tmp_path / "store")
    first = adapters._copy(store, source, "x/a.json")
    assert adapters._copy(store, source, "x/a.json") == first
    other = write(tmp_path / "b.json", {"different": True})
    with pytest.raises(AnalysisError, match="conflict"):
        adapters._copy(store, other, "x/a.json")
    assert adapters._abi(record()) == "c"
    raw = record(); raw["target"]["abi"] = {}
    assert adapters._abi(raw) == "{}"


def test_run_demand_builds_request_and_publishes_views(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    plan = {"schema_version": 1, "kind": "RootDrivenAnalysisPlan", "policy_id": "execution-root-driven-analysis-v1"}
    overlay = {"schema_version": 1, "kind": "ThreadEntryRootOverlay", "policy_id": "thread-entry-discovery-v1"}
    write(data / "root-plans/scope.json", plan); write(data / "thread-entry-roots/scope.json", overlay)
    output = data / "out"
    captured = {}
    def analyze(path, artifact_store, destination, worker):
        captured.update(json.loads(Path(path).read_text()))
        destination.mkdir(parents=True)
        for name in ("demand-graph.json", "worker-manifest.json"):
            write(destination / name, {"kind": name})
        for name in ("effects", "threads", "concurrent-access"):
            write(destination / f"views/{name}.json", {"kind": name})
        return {"status": "complete"}
    monkeypatch.setattr(adapters, "analyze_demanded_functions", analyze)
    source_inputs = {"tu": {"request": {"profile": {"profile_id": "d" * 64,
                                                       "compiler": {"family": "gcc"}}}}}
    result = adapters.run_demand(scope(), data, store, {"tu": {"artifact_key": "e" * 64}},
                                 source_inputs, output, "worker")
    assert result["status"] == "complete" and captured["members"][0]["compiler"] == "gcc"
    assert (data / "demand-graphs/scope.json").is_file()
    with pytest.raises(AnalysisError, match="requires"):
        adapters.run_demand({**scope(), "target_id": "missing"}, data, store, {}, {}, data / "other", "worker")


def test_demand_skips_unattested_llvm_compatible_member(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    write(data / "root-plans/scope.json", {"schema_version": 1, "kind": "RootDrivenAnalysisPlan", "policy_id": "p"})
    write(data / "thread-entry-roots/scope.json", {"schema_version": 1, "kind": "ThreadEntryRootOverlay", "policy_id": "p"})
    value = record(family="llvm-compatible")
    monkeypatch.setattr(adapters, "analyze_demanded_functions", lambda *args: {"status": "partial"})
    with pytest.raises(AnalysisError):
        adapters.run_demand(scope([value]), data, store, {"tu": {"artifact_key": "e" * 64}}, {}, data / "out", "worker")


def test_vendor_inference_and_profile_ambiguity(tmp_path, monkeypatch):
    assert adapters._infer_vendor({"nodes": [{"qualified_name": "std::__1::thread"}]}) == "libc++"
    assert adapters._infer_vendor({"nodes": [{"qualified_name": "std::thread"}]}) == "libstdc++"
    assert adapters._infer_vendor(None) is None
    monkeypatch.setattr(adapters, "ROOT", tmp_path)
    (tmp_path / "profiles").mkdir()
    monkeypatch.setattr(adapters, "_source_fact", lambda *args: {"nodes": [{"qualified_name": "std::thread"}]})
    fake = lambda path, kind: {"status": "verified", "cxx_standard": "c++17",
                               "target": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64",
                               "vendor": "libstdc++", "cxx_abi": "itanium", "profile_id": path.stem}
    write(tmp_path / "profiles/a.json", {}); write(tmp_path / "profiles/b.json", {})
    cpp = scope([record(language="c++", standard="c++17")])
    with pytest.raises(AnalysisError, match="unique"):
        adapters._profiles("profiles", fake, "Profile", cpp, tmp_path)


def test_cpp_adapters_skip_c_and_construct_requests(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    assert adapters.run_cpp_lifecycle(scope(), data, store, {}, {}, data / "a") is None
    assert adapters.run_raii(scope(), data, store, {}, data / "b") is None
    cpp_record = record(language="c++", standard="c++17")
    cpp_scope = scope([cpp_record])
    source_ref = {"kind": "SourceSemanticFacts", "id": "a" * 64, "digest": "1" * 64}
    module_ref = {"kind": "ModuleFacts", "id": "e" * 64, "digest": "2" * 64}
    base = [{"physical_tu_id": "a" * 64, "language": "c++", "standard": "c++17",
             "source": {"profile_id": "d" * 64}, "source_ref": source_ref,
             "module": {}, "module_ref": module_ref, "mapping": {"artifact_key": "e" * 64}}]
    monkeypatch.setattr(adapters, "_base_dependencies", lambda *args: ([source_ref, module_ref], base))
    write(data / "execution-roots/scope.json", {"roots": [{"id": "root"}]})
    write(data / f"llvm-binding-facts/{'e' * 64}.json", {"kind": "LLVMSourceBindingFacts"})
    thread_profile = {"profile_id": "p", "kind": "CppThreadLibraryProfile"}
    raii_profile = {"profile_id": "q", "kind": "CppRaiiSynchronizationProfile"}
    monkeypatch.setattr(adapters, "_profiles", lambda directory, *args: [(tmp_path / "profile.json",
                         thread_profile if directory == "cpp-thread-profiles" else raii_profile)])
    write(tmp_path / "profile.json", {})
    monkeypatch.setattr(adapters, "read_source_document", lambda *args: {"kind": "LLVMSourceBindingFacts"})
    monkeypatch.setattr(adapters, "dependency", lambda kind, identifier, value:
                        {"kind": kind, "id": identifier, "digest": identity(value)})
    monkeypatch.setattr(adapters, "cpp_thread_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "cpp_raii_document", lambda kind, **fields: {"kind": kind, **fields})
    def a3(path, artifact_store, output):
        write(output / "graphs/g.json", {"kind": "CppThreadLifecycleGraph"})
        return {"status": "complete"}
    def a4(path, artifact_store, output):
        write(output / "graphs/g.json", {"kind": "CppRaiiSynchronizationGraph"})
        return {"status": "complete"}
    monkeypatch.setattr(adapters, "model_cpp_thread_lifecycle", a3)
    monkeypatch.setattr(adapters, "model_cpp_raii_synchronization", a4)
    assert adapters.run_cpp_lifecycle(cpp_scope, data, store, {}, {}, data / "a3")["status"] == "complete"
    assert adapters.run_raii(cpp_scope, data, store, {}, data / "a4")["status"] == "complete"
    assert (data / "cpp-thread-graphs/scope.json").is_file() and (data / "raii-graphs/scope.json").is_file()


def test_provenance_concurrent_publication_and_atomic_adapters(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    write(data / "execution-roots/scope.json", {"roots": []})
    monkeypatch.setattr(adapters, "provenance_document", lambda kind, **fields: {"kind": kind, **fields})
    def provenance(path, artifact_store, output, source_worker, ir_worker):
        write(output / "graphs/g.json", {"kind": "BoundedObjectProvenanceGraph"})
        return {"status": "complete"}
    monkeypatch.setattr(adapters, "analyze_object_provenance", provenance)
    result = adapters.run_provenance(scope(), data, store, {"tu": {"artifact_key": "e" * 64}}, {}, data / "provenance", "s", "i")
    assert result["status"] == "complete" and (data / "provenance-graphs/scope.json").is_file()

    plan = {"schema_version": 1, "kind": "RootDrivenAnalysisPlan", "policy_id": "root"}
    overlay = {"schema_version": 1, "kind": "ThreadEntryRootOverlay", "policy_id": "entry"}
    write(data / "root-plans/scope.json", plan); write(data / "thread-entry-roots/scope.json", overlay)
    write(data / "summaries/s.json", {"context_id": "ctx"})
    monkeypatch.setattr(adapters, "concurrent_access_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "build_concurrent_access_candidates", lambda *args: {"status": "complete"})
    assert adapters.run_concurrent(scope(), data, {}, {}, data / "concurrent")["status"] == "complete"
    (data / "root-plans/scope.json").unlink()
    with pytest.raises(AnalysisError, match="requires"):
        adapters.run_concurrent(scope(), data, {}, {}, data / "bad")

    request_dir = data / "requests/scope"; request_dir.mkdir(parents=True, exist_ok=True)
    from memory_order_analyzer.thread_contracts import thread_document, expected_thread_protocol
    p3 = write(request_dir / "thread-0.json", thread_document(
        "ThreadAnalysisRequest", scope=str(data / "scopes/scope.json"),
        roots=[{"artifact_key": "e" * 64, "function_id": "f", "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"]))
    monkeypatch.setattr(adapters, "publication_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "detect_publication_risks", lambda *args: {"status": "complete"})
    assert adapters.run_publication(scope(), data, data / "pub", "worker", p3)["status"] == "complete"
    (request_dir / "thread-0.json").unlink()
    with pytest.raises(AnalysisError, match="requires"):
        adapters.run_publication(scope(), data, data / "pub2", "worker")

    artifact = "e" * 64
    write(data / "facts" / f"{artifact}.json", {"kind": "ModuleFacts"})
    write(data / "report.json", {"record_artifacts": [{"record_id": "tu", "artifact_key": artifact}]})
    monkeypatch.setattr(adapters, "advanced_atomic_document", lambda kind, **fields: {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "model_fence_rmw_publication", lambda path, store, output: {"status": "complete"})
    reports = adapters.run_atomic(scope(), data, data / "atomic")
    assert len(reports) == 1 and reports[0]["status"] == "complete"


def test_source_module_profile_and_base_dependency_helpers(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    item = record()
    mapping = {"artifact_key": "e" * 64}
    write(data / f"source-facts/{item['physical_tu_id']}.json", {"kind": "source"})
    write(data / f"facts/{mapping['artifact_key']}.json", {"kind": "module"})
    monkeypatch.setattr(adapters, "read_source_document", lambda path, kind: {"kind": kind})
    monkeypatch.setattr(adapters, "read_document", lambda path, kind: {"kind": kind})
    assert adapters._source_fact(data, item)["kind"] == "SourceSemanticFacts"
    assert adapters._module(data, mapping)["kind"] == "ModuleFacts"
    assert adapters._profile_id(item, {}) == identity({
        "compile": item["compile_record_digest"], "target": item["target"],
        "language": item["language"], "standard": item["standard"],
    })
    source_inputs = {"tu": {"request": {"profile": {"profile_id": "f" * 64}}}}
    assert adapters._profile_id(item, source_inputs) == "f" * 64
    for relative, kind in (("entity-index/scope.json", "ProgramEntityIndex"),
                           ("source-ir-binding/scope.json", "SourceIRBinding"),
                           ("graphs/scope.json", "ThreadContextGraph")):
        write(data / relative, {"kind": kind})
    dependencies, members = adapters._base_dependencies(scope(), data, {"tu": mapping})
    assert {value["kind"] for value in dependencies} == {
        "SourceSemanticFacts", "ModuleFacts", "ProgramEntityIndex",
        "SourceIRBinding", "ThreadContextGraph",
    }
    assert members[0]["source_ref"] and members[0]["module_ref"]


def test_profiles_selects_verified_vendor_and_rejects_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters, "ROOT", tmp_path)
    directory = tmp_path / "profiles"; directory.mkdir()
    write(directory / "good.json", {})
    write(directory / "wrong.json", {})
    monkeypatch.setattr(adapters, "_source_fact", lambda *args: {
        "nodes": [{"canonical_type": "std::__1::thread"}]})
    def reader(path, kind):
        return {"status": "verified" if path.stem == "good" else "unverified",
                "cxx_standard": "c++17", "target": "x86_64-pc-linux-gnu",
                "data_layout": "e-p:64:64", "vendor": "libc++", "cxx_abi": "itanium",
                "profile_id": path.stem, "kind": kind}
    selected = adapters._profiles(
        "profiles", reader, "Profile", scope([record(language="c++", standard="c++17")]), tmp_path)
    assert selected[0][1]["profile_id"] == "good"
    monkeypatch.setattr(adapters, "_source_fact", lambda *args: {
        "nodes": [{"qualified_name": "std::thread"}]})
    with pytest.raises(AnalysisError, match="unique"):
        adapters._profiles(
            "profiles", reader, "Profile", scope([record(language="c++", standard="c++17")]), tmp_path)


def test_provenance_and_r2_preserve_optional_dependencies(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir(); store = OutputStore(data)
    item = record(); mapping = {"artifact_key": "e" * 64}
    source_inputs = {"tu": {"request": {"source_path": "a.c", "profile": {
        "profile_id": "f" * 64, "compiler": {"family": "clang"},
        "source": {"path": "a.c", "sha256": "1" * 64}}}}}
    for relative, kind in (("entity-index/scope.json", "ProgramEntityIndex"),
                           ("source-ir-binding/scope.json", "SourceIRBinding"),
                           ("summaries/s.json", "EffectSummary")):
        value = {"kind": kind, "context_id": "ctx"}
        write(data / relative, value)
    write(data / "execution-roots/scope.json", {"roots": [{"id": "root"}]})
    (data / f"artifacts/{mapping['artifact_key']}.bc").parent.mkdir()
    (data / f"artifacts/{mapping['artifact_key']}.bc").write_bytes(b"BC\xc0\xde")
    captured = {}
    monkeypatch.setattr(adapters, "provenance_document", lambda kind, **fields: {"kind": kind, **fields})
    def analyze(path, artifact_store, output, source_worker, ir_worker):
        captured.update(json.loads(Path(path).read_text()))
        write(output / "graphs/g.json", {"kind": "BoundedObjectProvenanceGraph"})
        return {"status": "complete"}
    monkeypatch.setattr(adapters, "analyze_object_provenance", analyze)
    assert adapters.run_provenance(scope(), data, store, {"tu": mapping}, source_inputs,
                                   data / "out", "source", "ir")["status"] == "complete"
    assert captured["members"][0]["source_request"] and captured["members"][0]["llvm_request"]
    assert {value["kind"] for value in captured["dependencies"]} == {
        "ProgramEntityIndex", "SourceIRBinding", "EffectSummary"}

    for relative, kind in (("root-plans/scope.json", "RootDrivenAnalysisPlan"),
                           ("thread-entry-roots/scope.json", "ThreadEntryRootOverlay"),
                           ("graphs/scope.json", "ThreadContextGraph"),
                           ("cpp-thread-graphs/scope.json", "CppThreadLifecycleGraph"),
                           ("raii-graphs/scope.json", "CppRaiiSynchronizationGraph"),
                           ("provenance-graphs/scope.json", "BoundedObjectProvenanceGraph")):
        write(data / relative, {"kind": kind, "policy_id": "p", "schema_version": 1})
    refs = adapters._r2_evidence(scope(), data)
    assert {value["kind"] for value in refs} >= {
        "RootDrivenAnalysisPlan", "ThreadEntryRootOverlay", "EffectSummary",
        "BoundedObjectProvenanceGraph"}


def test_concurrent_and_atomic_include_source_binding_and_optional_graphs(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    item = record(); mapping = {"artifact_key": "e" * 64}
    source_inputs = {"tu": {"request": {"profile": {"profile_id": "f" * 64}}}}
    write(data / f"source-facts/{item['physical_tu_id']}.json", {
        "source_digest": "1" * 64, "kind": "SourceSemanticFacts"})
    write(data / "source-ir-binding/scope.json", {"semantic_digest": "2" * 64})
    monkeypatch.setattr(adapters, "read_source_document", lambda path, kind: json.loads(Path(path).read_text()))
    monkeypatch.setattr(adapters, "_r2_evidence", lambda *args: [
        {"kind": "RootDrivenAnalysisPlan"}, {"kind": "ThreadEntryRootOverlay"}, {"kind": "EffectSummary"}])
    captured = {}
    monkeypatch.setattr(adapters, "concurrent_access_document",
                        lambda kind, **fields: captured.update(fields) or {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "build_concurrent_access_candidates", lambda *args: {"status": "complete"})
    adapters.run_concurrent(scope(), data, {"tu": mapping}, source_inputs, data / "concurrent")
    member = captured["members"][0]
    assert member["source_digest"] == "1" * 64 and member["bc_digest"] == "c" * 64
    assert member["source_ir_binding_digest"] == "2" * 64

    write(data / f"facts/{mapping['artifact_key']}.json", {"kind": "ModuleFacts"})
    write(data / "report.json", {"record_artifacts": [{"record_id": "tu", "artifact_key": mapping["artifact_key"]}]})
    for relative in ("graphs/scope.json", "provenance-graphs/scope.json", "root-plans/scope.json",
                     "demand-graphs/scope.json", "analysis/scope/concurrent/candidate-graph.json",
                     "analysis/scope/publication/graphs/g.json"):
        write(data / relative, {"kind": Path(relative).stem})
    atomic_scope = scope([item, record("tu2", language="c++", standard="c++20")])
    atomic_scope["records"][1]["physical_tu_id"] = "9" * 64
    captured_atomic = []
    monkeypatch.setattr(adapters, "advanced_atomic_document",
                        lambda kind, **fields: captured_atomic.append(fields) or {"kind": kind, **fields})
    monkeypatch.setattr(adapters, "model_fence_rmw_publication", lambda *args: {"status": "complete"})
    reports = adapters.run_atomic(atomic_scope, data, data / "atomic")
    assert len(reports) == 2
    assert len(captured_atomic) == 1
    assert all(value["thread_graph"] and value["publication_graph"] for value in captured_atomic)
    assert reports[0]["status"] == "partial"
