"""真实 Clang 源码事实必须映射到头文件快照，而不是翻译单元主文件。"""

import os
import json
import subprocess
from pathlib import Path

from memory_order_analyzer.contracts import file_hash, identity
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.finding_locations import candidate_locations, assessment_locations
from memory_order_analyzer.source_context import snapshot_source
from memory_order_analyzer.source_contracts import source_document, expected_source_protocol
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_worker import analyze_source


def test_real_header_source_location(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "atomic.h").write_text("#include <stdatomic.h>\nstatic _Atomic int flag;\nstatic void publish(void) { atomic_store_explicit(&flag, 1, memory_order_relaxed); }\n")
    main = root / "main.c"
    main.write_text('#include "atomic.h"\nvoid run(void) { publish(); }\n')
    profile = build_profile({"directory": str(root), "file": "main.c",
                             "arguments": ["clang", "-std=c11", "-c", "main.c"]},
                            compiler_version="21.1.8", path_map=[{"from": str(root), "to": "."}])
    tu = identity(profile)
    request = source_document("SourceSemanticRequest", profile=profile, physical_tu_id=tu,
                              source_path=str(main), budgets=expected_source_protocol()["budgets"])
    worker = Path(os.environ["MOA_WORKER"]).with_name("memory-order-source-worker")
    facts = analyze_source(request, str(worker), tmp_path)
    assert facts["status"] == "complete"
    record = {"record_id": "r", "physical_tu_id": tu}
    store = OutputStore(tmp_path / "out")
    snapshots = {name: snapshot_source(store, root, name, file_hash(root / name)) for name in ("main.c", "atomic.h")}
    candidate = {"physical_tu_ids": [tu], "node_ids": [item["id"] for item in facts["nodes"]],
                 "relation_ids": [item["id"] for item in facts["relations"]]}
    locations = candidate_locations(candidate, {"r": facts}, {"records": [record]}, snapshots, store.root,
                                    {"budgets": {"context_lines": 256, "context_characters": 65536}}, root)
    assert any(item["location"]["file"] == "atomic.h" for item in locations), [item["source"] for item in facts["nodes"]]
    assert all(item["location"]["context"]["status"] == "complete" for item in locations)


def test_real_bitcode_events_resolve_debug_source(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "main.c"
    source.write_text("#include <stdatomic.h>\n_Atomic int ready;\nvoid publish(void) { atomic_store_explicit(&ready, 1, memory_order_release); }\nint consume(void) { return atomic_load_explicit(&ready, memory_order_acquire); }\n")
    bitcode = root / "main.bc"
    subprocess.run(["clang", "-std=c11", "-g", "-O0", "-emit-llvm", "-c", str(source), "-o", str(bitcode)], check=True, capture_output=True)
    result = subprocess.run([os.environ["MOA_WORKER"], str(bitcode), "0" * 64], check=True, capture_output=True, text=True)
    module = json.loads(result.stdout)
    events = [event for event in module["events"] if event.get("source", {}).get("inline_chain")]
    assert events, module
    store = OutputStore(tmp_path / "out")
    snapshots = {"main.c": snapshot_source(store, root, "main.c", file_hash(source))}
    (store.root / "facts").mkdir()
    (store.root / "facts/key.json").write_text(json.dumps(module))
    record = {"record_id": "r", "physical_tu_id": "tu"}
    locations = assessment_locations(
        {"evidence": [{"artifact_key": "key", "id": event["id"]} for event in events]},
        {"records": [record], "target_id": "scope"}, {"r": {"artifact_key": "key"}},
        store.root, snapshots, store.root, {"budgets": {"context_lines": 256, "context_characters": 65536}},
        lambda path: json.loads(path.read_text()), root)
    assert locations
    assert all(item["location"]["file"] == "main.c" for item in locations)
    assert all(item["location"]["context"]["status"] == "complete" for item in locations)
    assert {item["location"]["span"]["start"]["line"] for item in locations} >= {3, 4}
