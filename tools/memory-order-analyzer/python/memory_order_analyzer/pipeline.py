"""Read and publish immutable LLVM bitcode; this module never produces IR."""

import json
from pathlib import Path

from .contracts import AnalysisError, canonical, document, file_hash, identity, read_document, validate
from .execution import OutputStore, run
from .protocol import expected_protocol, check_worker


def write_json(store, value, name):
    with store.temporary() as temporary:
        source = temporary / "document.json"
        source.write_text(canonical(value) + "\n", encoding="utf-8")
        return store.publish(source, name)


def map_sources(facts, inputs):
    located, verified = 0, 0
    for item in [*facts["events"], *facts["calls"]]:
        source = item["source"]
        states = []
        for entry in source["inline_chain"]:
            path = (Path(entry["directory"]) / entry["file"]).resolve()
            expected = inputs.get(str(path))
            state = "unverified"
            if expected:
                state = "matched" if path.is_file() and file_hash(path) == expected else "source_mismatch"
            entry["recorded_hash"] = expected
            entry["consistency"] = state
            states.append(state)
        source["consistency"] = "source_mismatch" if "source_mismatch" in states else "matched" if states and all(s == "matched" for s in states) else "unverified"
    for event in facts["events"]:
        located += bool(event["source"]["inline_chain"])
        verified += event["source"]["consistency"] == "matched"
    facts["source_mapping"] = "unavailable" if not located else "complete" if verified == len(facts["events"]) else "partial"
    return facts


def read_facts(path, key, worker, *, inputs=None, expected=None, runner=run,
               timeout=None, output_limit=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise AnalysisError("artifact_missing", f"Missing or empty bitcode: {path}")
    check_worker(worker, path.parent, runner)
    result = runner(
        [str(worker), str(path), key], str(path.parent),
        timeout=timeout or 60,
        log_limit=output_limit or expected_protocol()["policy"]["max_output_bytes"],
    )
    if result["status"] != "completed":
        detail = result["stderr"]
        code = next((stage for stage in ("format_invalid", "reader_failed", "verify_failed", "extraction_budget_exceeded") if detail.startswith(stage)), result["code"])
        raise AnalysisError(code, detail)
    try:
        facts = validate(json.loads(result["stdout"]), "ModuleFacts")
    except ValueError as exc:
        raise AnalysisError("worker_protocol", str(exc)) from exc
    if facts["artifact_key"] != key or facts["module_hash"] != file_hash(path):
        raise AnalysisError("worker_identity", "Worker output does not match requested artifact")
    for field in ("target", "layout"):
        if expected and field in expected and facts[field] != expected[field]:
            raise AnalysisError("provenance_mismatch", f"{field}: manifest={expected[field]}, actual={facts[field]}")
    return map_sources(facts, inputs or {})


def import_bc(path, store, worker, *, manifest=None, runner=run):
    path = Path(path).resolve()
    if path.is_symlink() or not path.is_file() or not path.stat().st_size:
        raise AnalysisError("artifact_missing", str(path))
    from .external_bitcode_ingestion import classify_bitcode, stable_copy
    classify_bitcode(path)
    digest = file_hash(path)
    if manifest:
        validate(manifest, "BCArtifact")
        if manifest["sha256"] != digest:
            raise AnalysisError("provenance_mismatch", "Manifest hash differs from input")
        key = manifest["artifact_key"] if manifest["toolchain"].get("extraction") == expected_protocol() else identity({"previous": manifest["artifact_key"], "import": digest, "protocol": expected_protocol()})
    else:
        key = identity({"import": digest, "protocol": expected_protocol()})
    inputs = manifest["inputs"] if manifest else {}
    facts = read_facts(path, key, worker, inputs=inputs, expected=manifest["toolchain"] if manifest else None, runner=runner)
    with store.temporary() as temporary:
        staged = temporary / "module.bc"
        stable_copy(path, staged, digest, 1024 * 1024 * 1024)
        destination = store.publish(staged, f"artifacts/{key}.bc")
    artifact = dict(manifest) if manifest else document("BCArtifact", artifact_key=key, context_id=None,
                    path=str(destination), sha256=digest, profile="imported", provenance="unknown", inputs={}, toolchain={}, lineage=[])
    artifact["path"] = str(destination)
    artifact["artifact_key"] = key
    artifact["toolchain"] = {**artifact["toolchain"], "extraction": expected_protocol()}
    if manifest and manifest["artifact_key"] != key:
        artifact["lineage"] = sorted({manifest["artifact_key"], *manifest["lineage"]})
        artifact["toolchain"]["migration_from"] = manifest["artifact_key"]
    write_json(store, artifact, f"artifacts/{key}.json")
    write_json(store, facts, f"facts/{key}.json")
    return artifact, facts
