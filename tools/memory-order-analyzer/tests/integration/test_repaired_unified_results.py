"""5 TU / 2 Scope 离线真实 worker 回归；编译仅用于预生成输入 BC。"""

import json
import os
import subprocess
from pathlib import Path

from memory_order_analyzer.contracts import canonical, file_hash, identity
from memory_order_analyzer.external_bitcode_contracts import external_document, expected_external_bitcode_protocol, diagnostic
from memory_order_analyzer.source_contracts import source_document, expected_source_protocol
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.unified_contracts import unified_document, expected_unified_protocol
from memory_order_analyzer.unified_coordinator import analyze_project


def test_real_mixed_evidence_keeps_denominators_and_diagnostics(tmp_path):
    worker = os.environ["MOA_WORKER"]
    source_worker = str(Path(worker).with_name("memory-order-source-worker"))
    records, source_refs = [], []
    target = layout = None
    for index in range(5):
        standard = "c17" if index < 3 else "c11"
        source = tmp_path / f"input{index}.c"
        source.write_text((f"int f{index}(int *v) {{ int sum=0; for(int i=0;i<8;i++) sum+=v[i]; return sum; }}\n"
                           if index < 3 else "#include <stdatomic.h>\n_Atomic int flag;\nvoid publish(void) { atomic_store_explicit(&flag, 1, memory_order_relaxed); }\n"))
        bc = tmp_path / f"input{index}.bc"
        if index < 3:
            subprocess.run(["clang", f"-std={standard}", "-O0", "-g", "-emit-llvm", "-c", str(source), "-o", str(bc)],
                           check=True, capture_output=True)
            facts = json.loads(subprocess.run([worker, str(bc), "0" * 64], check=True, capture_output=True, text=True).stdout)
            target, layout = facts["target"], facts["layout"]
        profile = build_profile({"directory": str(tmp_path), "file": source.name,
            "arguments": ["clang", f"-std={standard}", "-g", "-O0", "-c", source.name]},
            compiler_version="21.1.8", path_map=[{"from": str(tmp_path), "to": "."}])
        tu = identity({"profile": profile["profile_id"], "index": index})
        producer = {"family": "clang", "version": "21.1.8", "llvm_version": "21.1.8", "host_triple": target}
        record = external_document("ExternalBitcodeArtifactRecord", record_id=f"tu-{index}", physical_tu_id=tu,
            status="produced" if index < 3 else "failed", diagnostic=None if index < 3 else
            diagnostic("external_build_failed", "合成上游构建缺口", "Synthetic upstream build gap", record_id=f"tu-{index}"),
            bitcode={"path": bc.name, "sha256": file_hash(bc), "bytes": bc.stat().st_size} if index < 3 else None,
            producer=producer, target={"triple": target, "data_layout": layout, "abi": {}},
            language="c", standard=standard, optimization="O0", debug="full", module_kind="translation-unit",
            source={"path": source.name, "sha256": file_hash(source)}, compile_record_digest=identity(profile), input_digests={})
        path = tmp_path / f"record-{index}.json"
        path.write_text(canonical(record))
        records.append({"path": path.name, "sha256": file_hash(path)})
        if index in {0, 1, 3}:
            request = source_document("SourceSemanticRequest", profile=profile, physical_tu_id=tu,
                source_path=str(source), budgets=expected_source_protocol()["budgets"])
            path = tmp_path / f"source-{index}.json"
            path.write_text(canonical(request))
            source_refs.append({"record_id": f"tu-{index}", "path": path.name, "sha256": file_hash(path), "schema_version": 2})
    manifest = external_document("ExternalBitcodeBundleManifest", bundle_id="mixed-regression", producer=producer,
        records=records, scopes=[{"target_id": name, "record_ids": ids, "evidence": "synthetic offline fixture",
        "closed": True, "external_boundaries": [], "target_triple": target}
        for name, ids in [("atomic", ["tu-3", "tu-4"]), ("ordinary", ["tu-0", "tu-1", "tu-2"])]],
        budgets=expected_external_bitcode_protocol()["budgets"])
    bundle = tmp_path / "bundle.json"
    bundle.write_text(canonical(manifest))
    request = unified_document("UnifiedMemoryOrderAnalysisRequest", policy_preset="bounded-default-v1",
        project={"id": "regression", "name": "混合证据回归"}, bundle={"path": bundle.name, "sha256": file_hash(bundle)},
        scope_selection={"mode": "all", "scope_ids": []}, source_assistance="auto", source_requests=source_refs,
        explicit_roots=[], cache={"mode": "read-write", "resume": True}, cancel_file=None,
        budgets=expected_unified_protocol()["budgets"])
    request_path = tmp_path / "request.json"
    request_path.write_text(canonical(request))
    results = [analyze_project(request_path, tmp_path / name, ir_worker=worker, source_worker=source_worker,
                               cache_path=tmp_path / "cache") for name in ("cold", "warm")]
    for report in results:
        assert report["summary"]["translation_units"] == 5 and report["summary"]["scopes"] == 2
        assert report["status"] == "partial" and report["exit_code"] == 2
        assert report["diagnostics"] and report["frontier"]
        assert report["finding_schema_version"] == "3.0"
        assert report["source_candidates"] and all(item["scopeId"] == "atomic" for item in report["source_candidates"])
        assert all(item["conclusion"]["confidence"] is None for item in report["source_candidates"])
        detail = canonical(report["diagnostics"])
        assert "LLVM binding requests must be unique" not in detail
        assert "R3 request members must be unique" not in detail
        assert "invalid literal for int()" not in detail
    assert results[0]["summary"] == results[1]["summary"]
