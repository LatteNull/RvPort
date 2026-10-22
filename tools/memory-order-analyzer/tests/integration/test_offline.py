"""External fixture preparation followed by production read-only ingestion."""
import json
import os
from pathlib import Path
import subprocess
import pytest

from memory_order_analyzer import cli
from memory_order_analyzer.contracts import AnalysisError, canonical, document, file_hash, identity, read_document
from memory_order_analyzer.external_bitcode_contracts import diagnostic, external_document, expected_external_bitcode_protocol
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.pipeline import import_bc
from memory_order_analyzer.scope import index_scope

WORKER = os.environ.get("MOA_WORKER", "/output/build/moa-worker")


def collect(root, sources, driver="clang", std="c11", flags=()):
    """Prepare BC before the product starts; the product only ingests the bundle."""
    records, references, compile_records = [], [], []
    bundle_dir = root / ".external-bundle"
    (bundle_dir / "records").mkdir(parents=True)
    (bundle_dir / "bc").mkdir()
    for name, content in sources.items():
        if isinstance(content, dict):
            local_driver = content.get("driver", driver)
            local_std = content.get("standard", std)
            local_flags = tuple(content.get("flags", flags))
            content = content["content"]
        else:
            local_driver, local_std, local_flags = driver, std, tuple(flags)
        (root / name).write_text(content)
        compile_record = {"directory": str(root), "file": name,
                          "arguments": [local_driver, "-std=" + local_std, *local_flags, "-c", name, "-o", name + ".o"]}
        compile_records.append(compile_record)
        record_id = "tu-" + identity(compile_record)[:16]
        bc = bundle_dir / "bc" / f"{record_id}.bc"
        clang = "clang++" if "+" in local_std else "clang"
        prepared = subprocess.run([clang, "-std=" + local_std, *local_flags, "-O0", "-g", "-emit-llvm", "-c",
                                   str(root / name), "-o", str(bc)], capture_output=True, text=True)
        source = {"path": name, "sha256": file_hash(root / name)}
        target = {"triple": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64", "abi": {}}
        status, bitcode, upstream = "failed", None, diagnostic(
            "external_build_failed", "测试准备阶段编译失败", prepared.stderr or "fixture preparation failed",
            record_id=record_id)
        if prepared.returncode == 0:
            raw = subprocess.run([WORKER, str(bc), "0" * 64], capture_output=True, text=True, check=True)
            module = json.loads(raw.stdout)
            target = {"triple": module["target"], "data_layout": module["layout"], "abi": {}}
            status, upstream = "produced", None
            bitcode = {"path": f".external-bundle/bc/{record_id}.bc", "sha256": file_hash(bc),
                       "bytes": bc.stat().st_size}
        record = external_document(
            "ExternalBitcodeArtifactRecord", record_id=record_id,
            physical_tu_id=identity({"source": source, "compile_record": compile_record}), status=status,
            diagnostic=upstream, bitcode=bitcode,
            producer={"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8",
                      "host_triple": "x86_64-pc-linux-gnu"}, target=target,
            language="c++" if "+" in local_std else "c", standard=local_std, optimization="O0", debug="full",
            module_kind="translation-unit", source=source,
            compile_record_digest=identity(compile_record), input_digests={})
        record_path = bundle_dir / "records" / f"{record_id}.json"
        record_path.write_text(canonical(record) + "\n")
        references.append({"path": f".external-bundle/records/{record_id}.json", "sha256": file_hash(record_path)})
        records.append(record)
    db = root / "compile_commands.json"
    db.write_text(json.dumps(compile_records))
    producer = {"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8",
                "host_triple": "x86_64-pc-linux-gnu"}
    manifest = external_document(
        "ExternalBitcodeBundleManifest", bundle_id="fixture-" + identity(references)[:16], producer=producer,
        records=sorted(references, key=lambda item: item["path"]),
        scopes=[{"target_id": "fixture", "record_ids": sorted(item["record_id"] for item in records),
                 "evidence": "integration fixture preparation", "closed": True,
                 "external_boundaries": [], "target_triple": records[0]["target"]["triple"]}],
        budgets=expected_external_bitcode_protocol()["budgets"])
    bundle = root / "bundle.json"
    bundle.write_text(canonical(manifest) + "\n")
    output = root / "out"
    ingestion, _ = cli.execute(cli.parser().parse_args([
        "ingest-bc-bundle", "--bundle", str(bundle), "--output", str(output), "--worker", WORKER]))
    artifacts = {key: read_document(output / "artifacts" / f"{key}.json", "BCArtifact") for key in ingestion["artifacts"]}
    facts = {key: read_document(output / "facts" / f"{key}.json", "ModuleFacts") for key in ingestion["artifacts"]}
    planned = len(records)
    all_produced = ingestion["counts"]["produced"] == planned and len(artifacts) == planned
    failed_inputs = [item for item in ingestion["frontier"]
                     if item["code"] in {"external_artifact_missing", "external_build_failed",
                                         "artifact_format_unsupported", "hash_mismatch", "reader_failed", "verify_failed"}]
    report = {"schema_version": 2, "build_status": "complete" if all_produced else "partial" if artifacts else "failed",
              "ir_status": "complete" if len(artifacts) == planned else "partial" if artifacts else "failed",
              "scope_status": "unknown", "safety": "not_evaluated", "semantic_analysis": "not_run",
              "findings": None, "exit_code": ingestion["exit_code"], "artifacts": ingestion["artifacts"],
              "counts": {"original_records": planned, "planned_tus": planned,
                         "verified": len(artifacts)}, "failures": ingestion["frontier"],
              "fact_extraction": {"planned": planned,
                                  "complete": ingestion["counts"]["facts_complete"],
                                  "partial": ingestion["counts"]["facts_partial"]},
              "ingestion_report": ingestion}
    report["failures"] = failed_inputs
    return report, artifacts, facts, db


@pytest.mark.parametrize("family", ["gcc", "clang"])
@pytest.mark.parametrize("standard", ["c11", "c17", "c++17", "c++20"])
def test_compiler_language_matrix(tmp_path, family, standard):
    cpp = "+" in standard
    driver = {"gcc": "g++", "clang": "clang++"}[family] if cpp else family
    source = "#include <atomic>\nstd::atomic<int> x; __attribute__((noinline)) void wrapped(std::atomic<int>* p,int v,std::memory_order o){p->store(v,o);} void publish(){wrapped(&x,1,std::memory_order_release);}\n" if cpp else "#include <stdatomic.h>\n_Atomic int x; void publish(void){atomic_store_explicit(&x,1,memory_order_release);}\n"
    report, artifacts, facts, _ = collect(tmp_path, {"main.cpp" if cpp else "main.c": source}, driver, standard)
    assert report["build_status"] == "complete", report["failures"]
    assert report["ir_status"] == "complete" and report["counts"]["planned_tus"] == 1
    assert report["scope_status"] == "unknown" and report["safety"] == "not_evaluated"
    production = tmp_path / "production-only"
    production.mkdir()
    subprocess.run([driver, "-std=" + standard, "-c", str(tmp_path / ("main.cpp" if cpp else "main.c")), "-o", str(production / "object.o")], check=True)
    assert (production / "object.o").stat().st_size > 0
    module = next(iter(facts.values()))
    assert module["schema_version"] == report["schema_version"] == 2
    assert module["values"] and report["fact_extraction"]["planned"] == 1
    assert all(e["range_status"] in ("available", "unknown", "not_applicable") for e in module["events"])
    assert any(event.get("ordering") == "release" for event in module["events"])
    assert not module["capabilities"]["callsite_specialization"]
    assert not list(tmp_path.glob("*.o"))
    if cpp:
        assert module["calls"] and any(len(fn.get("blocks", [])) > 1 for fn in module["functions"])
        values = {v["id"]: v for v in module["values"]}
        # O0 libstdc++ wrapper: actual arguments and stack traffic remain raw facts.
        assert any(len(c["arguments"]) >= 3 for c in module["calls"])
        assert any(len(f.get("parameters", [])) >= 3 for f in module["functions"])
        assert any(values[e["inputs"]["value"]]["kind"] == "argument" for e in module["events"] if "value" in e["inputs"])
        assert any(b["terminator"]["condition_ref"] is not None for f in module["functions"] for b in f.get("blocks", []))
        assert {e.get("ordering") for e in module["events"]} >= {"monotonic", "release", "seq_cst"}
        assert report["semantic_analysis"] == "not_run" and report["findings"] is None


def test_physical_tus_link_extern_static_overloads_and_lineage(tmp_path):
    report, artifacts, facts, _ = collect(tmp_path, {
        "caller.cpp": "extern int shared; int worker(int); double worker(double); static int local(){return 1;} int entry(){return worker(shared)+int(worker(2.0))+local();}",
        "integer.cpp": "int shared; static int local(){return 2;} int worker(int x){shared=x;return local();}",
        "double.cpp": "double worker(double x){return x;}",
    }, "g++", "c++20")
    assert report["build_status"] == "complete", report["failures"]
    scope = document("ScopeManifest", target_id="unit-program", members=sorted(artifacts), evidence="explicit three physical TUs", closed=True, external_boundaries=[])
    index = index_scope(scope, artifacts, facts)
    names = {binding["reference"]["symbol"] for binding in index["bindings"]}
    assert {"_Z6workeri", "_Z6workerd", "shared"} <= names
    assert len({fn["id"] for module in facts.values() for fn in module["functions"] if fn["linkage"] == "internal" and "local" in fn["name"]}) == 2
    assert len(index["members"]) == 3


def test_missing_header_and_invalid_bc(tmp_path):
    report, _, _, _ = collect(tmp_path, {"good.c": "int value;", "missing.c": '#include "not_generated.h"\n'})
    assert report["exit_code"] == 2 and report["counts"]["planned_tus"] == 2
    assert report["counts"]["verified"] == 1 and len(report["failures"]) == 1
    bad = tmp_path / "bad.bc"
    bad.write_bytes(b"not bitcode")
    with pytest.raises(AnalysisError) as caught:
        import_bc(bad, OutputStore(tmp_path / "bad"), WORKER)
    assert caught.value.code == "artifact_format_unsupported"


def test_nodebug_and_incompatible_targets(tmp_path):
    source = tmp_path / "input.c"
    source.write_text("int x; int read_x(void){return x;}\n")
    artifacts, facts = {}, {}
    for name, target in (("native", "x86_64-pc-linux-gnu"), ("arm", "aarch64-unknown-linux-gnu")):
        bc = tmp_path / f"{name}.bc"
        subprocess.run(["clang", "--target=" + target, "-O0", "-g0", "-emit-llvm", "-c", str(source), "-o", str(bc)], check=True)
        artifact, module = import_bc(bc, OutputStore(tmp_path / name), WORKER)
        assert module["events"] and module["source_mapping"] == "unavailable"
        assert module["values"] and module["events"][0]["ranges"]
        assert artifact["provenance"] == "unknown"
        artifacts[artifact["artifact_key"]] = artifact
        facts[artifact["artifact_key"]] = module
    scope = document("ScopeManifest", target_id="invalid", members=sorted(artifacts), evidence="unit deliberate mismatch", closed=True, external_boundaries=[])
    with pytest.raises(AnalysisError) as caught:
        index_scope(scope, artifacts, facts)
    assert caught.value.code == "target_conflict"
