"""Real BC re-extraction and bounded measurements, never execute analyzed code."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import time
import pytest
from memory_order_analyzer.contracts import AnalysisError, canonical, document, file_hash, validate
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.pipeline import import_bc
from memory_order_analyzer.scope import index_scope
from memory_order_analyzer.report import make_report


def test_real_bitcode_migration_scope_and_measurement(tmp_path):
    worker = os.environ["MOA_WORKER"]
    source, bc = tmp_path / "input.c", tmp_path / "input.bc"
    source.write_text("int x; int read_x(void) {return x;}\n")
    subprocess.run(["clang", "-g", "-O0", "-emit-llvm", "-c", str(source), "-o", str(bc)], check=True)
    old = document("BCArtifact", artifact_key="a" * 64, context_id="b" * 64, path=str(bc), sha256=file_hash(bc),
                   profile="source-preserving", provenance="verified", inputs={str(source): file_hash(source)},
                   toolchain={"extractor": "0.1.0"}, lineage=["c" * 64])
    old_path = tmp_path / "old-manifest.json"
    old_path.write_text(canonical(old))
    original_hash = file_hash(old_path)
    begin = time.monotonic()
    new, facts = import_bc(bc, OutputStore(tmp_path / "new"), worker, manifest=old)
    elapsed = time.monotonic() - begin
    repeat, repeated = import_bc(bc, OutputStore(tmp_path / "repeat"), worker, manifest=old)
    assert new["artifact_key"] == repeat["artifact_key"] and facts == repeated
    assert file_hash(old_path) == original_hash and file_hash(bc) == old["sha256"]
    assert new["lineage"] == sorted([old["artifact_key"], *old["lineage"]])
    report = make_report("import-bc", planned=1, artifacts=[new], facts=[facts])
    assert report["artifact_migrations"] == [{"from": old["artifact_key"], "to": new["artifact_key"]}]
    historic = deepcopy(facts)
    historic["schema_version"] = 1
    with pytest.raises(AnalysisError, match="schema_version"):
        validate(historic, "ModuleFacts")
    a = new["artifact_key"]
    old_scope = document("ScopeManifest", members=[old["artifact_key"]], target_id="app", evidence="explicit", closed=True, external_boundaries=[])
    with pytest.raises(AnalysisError, match="Missing references"):
        index_scope(old_scope, {a: new}, {a: facts})
    new_scope = {**old_scope, "members": [a]}
    index_scope(new_scope, {a: new}, {a: facts})
    assert index_scope(new_scope, {a: new}, {a: facts})["members"] == [a]
    assert old_scope["members"] == [old["artifact_key"]]
    memory_probe = subprocess.run(["python3", "-c",
        "import json,resource,subprocess,sys; p=subprocess.run(sys.argv[1:],capture_output=True,check=True); "
        "print(json.dumps({'peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'stdout_bytes':len(p.stdout)}))",
        worker, str(bc), a], capture_output=True, text=True, check=True)
    memory = json.loads(memory_probe.stdout)
    assert memory["peak_rss_kib"] > 0 and memory["stdout_bytes"] > 0
    measurement = {"sample": "single-TU global load", "bc_bytes": bc.stat().st_size,
                   "facts_bytes": len(canonical(facts).encode()), "wall_seconds": round(elapsed, 6),
                   "nodes": facts["extraction"]["nodes"], "references": facts["extraction"]["references"],
                   "policy": facts["protocol"]["policy"], "worker_peak_rss_kib": memory["peak_rss_kib"]}
    assert 0 < measurement["facts_bytes"] < measurement["policy"]["max_output_bytes"]
    assert measurement["nodes"] < measurement["policy"]["max_nodes"]
    # Per-run evidence stays in the isolated test output; integration tests do not mutate the source tree.
    (tmp_path / "semantic-resource-sample.json").write_text(canonical(measurement) + "\n")
