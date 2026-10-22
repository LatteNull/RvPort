"""Truth comparison, completeness, sampling, performance and backend evidence for P5."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath

from .contracts import AnalysisError, canonical, file_hash, identity
from .validation_contracts import CAPABILITIES, diagnostic, validation_document


LAYER_NAMES = ("request_input", "compile", "p1", "p2", "p3", "p4", "truth", "sampling", "performance", "backend")
VOLATILE_KEYS = frozenset({
    "captured_at", "created_at", "duration", "duration_seconds", "wall_seconds",
    "cpu_seconds", "peak_rss_bytes", "output_bytes", "cache_hit", "cache_miss",
    "temporary_directory", "work_directory",
})


def safe_path(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AnalysisError("path_escape", f"Path escapes validation root: {relative}") from exc
    return candidate


def verify_entry(root, entry):
    path = safe_path(root, entry["path"])
    if not path.is_file() or file_hash(path) != entry["sha256"]:
        raise AnalysisError("input_digest", f"Missing or changed validation input: {entry['path']}")
    return path


def case_input_digest(root, case):
    entries = [*case["sources"], case["compile_commands"], case["scope"]]
    for entry in entries:
        verify_entry(root, entry)
    return identity({
        "case_id": case["id"],
        "profile_id": case["profile_id"],
        "category": case["category"],
        "layout": case["layout"],
        "roots": sorted(case["roots"]),
        "inputs": sorted(({"path": item["path"], "sha256": item["sha256"], "role": item["role"]}
                          for item in entries), key=lambda item: item["path"]),
    })


def bind_truth(root, suite, case, truth):
    verify_entry(root, case["truth"])
    if (truth["suite_id"], truth["suite_version"], truth["case_id"]) != (
            suite["suite_id"], suite["suite_version"], case["id"]):
        raise AnalysisError("truth_identity", f"Truth identity is stale for {case['id']}")
    if truth["input_digest"] != case_input_digest(root, case):
        raise AnalysisError("truth_stale", f"Truth input digest is stale for {case['id']}")
    if truth["review"]["status"] != "reviewed":
        raise AnalysisError("truth_unreviewed", f"Truth is not human-reviewed for {case['id']}")
    return truth


def assertion_key(item):
    return (item["code"], item.get("object"), item.get("thread_relation"), item.get("evidence_relation"))


def observed_assertions(graph):
    return {
        (item["code"], None, None, None)
        for item in graph.get("assessments", []) if item.get("status") == "finding"
    }


def _normalized_verdict(report):
    return {
        "risks_found": "risk",
        "no_supported_risk_found": "discharged",
        "inconclusive": "unknown",
        "failed": "failed",
    }.get(report.get("verdict"), "unknown")


def compare_case(case, truth, report, graph):
    required_items = truth["expected"]["required_findings"]
    forbidden_items = truth["expected"]["forbidden_findings"]
    required = {assertion_key(item) for item in required_items}
    forbidden = {assertion_key(item) for item in forbidden_items}
    observed = observed_assertions(graph)
    missing = required - observed
    forbidden_seen = forbidden & observed
    unexpected = observed - required
    unknown_codes = {item.get("code") for item in graph.get("assessments", [])
                     if item.get("status") in ("unknown", "unsupported")}
    unknown_codes.update(item.get("code") for item in report.get("frontier", []))
    expected_unknown = set(truth["expected"]["unknown_codes"])
    abstained = bool(unknown_codes) or _normalized_verdict(report) == "unknown"
    verdict_ok = _normalized_verdict(report) in truth["expected"]["verdicts"]
    status_ok = report.get("risk_evaluation") in truth["expected"]["statuses"]
    unknown_ok = expected_unknown.issubset(unknown_codes)
    matched = not missing and not forbidden_seen and not unexpected and verdict_ok and status_ok and unknown_ok
    strict_fn = len(missing)
    if abstained and required:
        strict_fn = max(strict_fn, len(required))
    return {
        "case_id": case["id"],
        "profile_id": case["profile_id"],
        "category": case["category"],
        "status": report.get("risk_evaluation", "failed") if report.get("risk_evaluation") in ("complete", "partial", "failed", "not_run") else "failed",
        "matched": matched,
        "strict_fn": strict_fn,
        "abstained": abstained,
        "required_missing": [item for item in required_items if assertion_key(item) in missing],
        "forbidden_observed": [item for item in forbidden_items if assertion_key(item) in forbidden_seen],
        "semantic_digests": {},
        "resources": {},
        "diagnostics": [] if matched else [diagnostic(
            "truth_mismatch",
            "观察结果与人工真值不一致",
            "Observed result does not match the human-reviewed truth",
            suggestion="检查缺失、额外 finding 与 unknown 证据",
            suggestion_en="Inspect missing/extra findings and unknown evidence",
        )],
        "_counts": {
            "tp": len(required & observed),
            "fp": len(unexpected | forbidden_seen),
            "fn": strict_fn,
            "supported_tp": 0 if abstained else len(required & observed),
            "supported_fp": 0 if abstained else len(unexpected | forbidden_seen),
            "supported_fn": 0 if abstained else len(missing),
        },
    }


def metric(hit, total):
    return {"hit": hit, "total": total, "value": hit / total if total else None}


def aggregate_metrics(results):
    tp = sum(item["_counts"]["tp"] for item in results)
    fp = sum(item["_counts"]["fp"] for item in results)
    fn = sum(item["_counts"]["fn"] for item in results)
    stp = sum(item["_counts"]["supported_tp"] for item in results)
    sfp = sum(item["_counts"]["supported_fp"] for item in results)
    sfn = sum(item["_counts"]["supported_fn"] for item in results)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": metric(tp, tp + fp),
        "recall": metric(tp, tp + fn),
        "supported_precision": metric(stp, stp + sfp),
        "supported_recall": metric(stp, stp + sfn),
        "exact_match": metric(sum(item["matched"] for item in results), len(results)),
        "abstention": metric(sum(item["abstained"] for item in results), len(results)),
    }


def public_case_result(result):
    return {key: deepcopy(value) for key, value in result.items() if not key.startswith("_")}


def layer_state(statuses):
    statuses = list(statuses)
    hit = sum(status == "complete" for status in statuses)
    if not statuses:
        return {"status": "not_run", "hit": 0, "total": 0}
    status = "complete" if hit == len(statuses) else "failed" if all(item == "failed" for item in statuses) else "partial"
    return {"status": status, "hit": hit, "total": len(statuses)}


def aggregate_layers(case_layers, backend_requested=False):
    result = {}
    for name in LAYER_NAMES:
        statuses = [item[name] for item in case_layers if name in item]
        if name == "backend" and not backend_requested:
            statuses = ["complete"]
        result[name] = layer_state(statuses)
    return result


def _semantic_value(value, roots):
    if isinstance(value, dict):
        return {key: _semantic_value(item, roots) for key, item in sorted(value.items()) if key not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [_semantic_value(item, roots) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for marker, root in roots:
            normalized = normalized.replace(str(root).replace("\\", "/"), marker)
        return normalized
    return value


def semantic_digest(value, *, roots=()):
    normalized_roots = sorted(((marker, Path(root).resolve()) for marker, root in roots),
                              key=lambda item: len(str(item[1])), reverse=True)
    return identity(_semantic_value(value, normalized_roots))


def stratified_sample(items, count, seed, stratum=lambda item: item["category"]):
    grouped = {}
    for item in items:
        grouped.setdefault(stratum(item), []).append(item)
    selected = []
    for name in sorted(grouped):
        ranked = sorted(grouped[name], key=lambda item: hashlib.sha256(
            f"{seed}:{name}:{item['id']}".encode()).hexdigest())
        selected.extend(ranked[:count])
    return sorted(selected, key=lambda item: item["id"])


def validate_real_project_profile(profile_path):
    profile_path = Path(profile_path).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    required = {"schema_version", "project", "upstream", "revision", "root", "source_tree_hash", "license", "compile_commands", "scope", "included", "excluded"}
    if set(profile) != required or profile["schema_version"] != 1:
        raise AnalysisError("profile_invalid", "Real-project profile fields/version are invalid")
    root = safe_path(profile_path.parent, profile["root"])
    license_path = safe_path(root, profile["license"]["path"])
    database_path = safe_path(root, profile["compile_commands"]["path"])
    scope_path = safe_path(root, profile["scope"]["path"])
    for path, expected in ((license_path, profile["license"]["sha256"]),
                           (database_path, profile["compile_commands"]["sha256"]),
                           (scope_path, profile["scope"]["sha256"])):
        if not path.is_file() or file_hash(path) != expected:
            raise AnalysisError("profile_digest", f"Real-project profile dependency changed: {path}")
    included_entries = profile["included"]
    if not all(isinstance(item, dict) and set(item) == {"path", "sha256"} for item in included_entries):
        raise AnalysisError("profile_invalid", "Included sources require path and sha256")
    for item in included_entries:
        path = safe_path(root, item["path"])
        if not path.is_file() or file_hash(path) != item["sha256"]:
            raise AnalysisError("profile_digest", f"Included source changed: {item['path']}")
    source_identity = identity(sorted(included_entries, key=lambda item: item["path"]))
    if source_identity != profile["source_tree_hash"]:
        raise AnalysisError("profile_digest", "Real-project source tree hash is stale")
    database = json.loads(database_path.read_text(encoding="utf-8").replace("${PROJECT_ROOT}", str(root)))
    if not isinstance(database, list):
        raise AnalysisError("profile_invalid", "compile_commands.json must be an array")
    files = []
    for record in database:
        file_path = Path(record["file"])
        candidate = file_path if file_path.is_absolute() else Path(record["directory"]) / file_path
        try:
            files.append(candidate.resolve().relative_to(root).as_posix())
        except ValueError as exc:
            raise AnalysisError("path_escape", f"Compile record escapes project root: {candidate}") from exc
    included = {item["path"] for item in included_entries if Path(item["path"]).suffix in (".c", ".cc", ".cpp", ".cxx")}
    missing = sorted(included - set(files))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    configurations = sorted({Path((record.get("arguments") or [record.get("command", "")])[0]).name
                             for record in database})
    return {
        "records": len(database),
        "unique_tus": len(set(files)),
        "included": len(included),
        "excluded": len(profile["excluded"]),
        "configurations": configurations,
        "scope_roots": len(scope.get("roots", [])),
        "missing": missing,
        "status": "complete" if not missing else "partial",
        "source_tree_hash": profile["source_tree_hash"],
        "revision": profile["revision"],
    }


def materialize_compile_database(profile_path, destination):
    profile_path, destination = Path(profile_path).resolve(), Path(destination)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    root = safe_path(profile_path.parent, profile["root"])
    source = safe_path(root, profile["compile_commands"]["path"])
    records = json.loads(source.read_text(encoding="utf-8").replace("${PROJECT_ROOT}", str(root)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(canonical(records) + "\n", encoding="utf-8")
    return {"path": str(destination.resolve()), "sha256": file_hash(destination), "records": len(records)}


def backend_bundle(backend, case_id, input_digest, *, version, license_id, command,
                   raw_output_paths=(), observation=None, applicability="applicable",
                   status="complete", captured_on="2026-09-18", diagnostics=()):
    hashes = [file_hash(path) for path in raw_output_paths]
    observation = deepcopy(observation or {})
    if status == "complete" and applicability == "applicable" and not observation:
        status = "partial"
        diagnostics = [*diagnostics, diagnostic(
            "empty_backend_output", "后端成功退出但没有可用观察", "Backend exited successfully without a usable observation")]
    return validation_document(
        "BackendEvidenceBundle", backend=backend, backend_version=version, license=license_id,
        case_id=case_id, applicability=applicability, status=status, command=list(command),
        input_digest=input_digest, raw_output_hashes=hashes, observation=observation,
        captured_on=captured_on, diagnostics=list(diagnostics),
    )


def normalize_genmc_output(case_id, input_digest, text, *, exit_code, version="0.8.1",
                           command=("genmc",), timed_out=False, truncated=False):
    lowered = text.lower()
    risk = any(marker in lowered for marker in ("error detected", "data race", "assertion violation"))
    complete = exit_code == 0 and bool(text.strip()) and not timed_out and not truncated
    status = "complete" if complete else "partial" if timed_out or truncated or exit_code == 0 else "failed"
    notes = []
    if timed_out:
        notes.append(diagnostic("backend_timeout", "GenMC 超时", "GenMC timed out"))
    if truncated:
        notes.append(diagnostic("backend_truncated", "GenMC 输出被截断", "GenMC output was truncated"))
    if exit_code == 0 and not text.strip():
        notes.append(diagnostic("empty_backend_output", "GenMC 成功退出但输出为空", "GenMC exited successfully with empty output"))
    observation = {"risk": risk, "normalized": "risk" if risk else "no-risk-observed"} if text.strip() else {}
    return backend_bundle("genmc", case_id, input_digest, version=version, license_id="GPL-3.0-or-later",
                          command=command, observation=observation, status=status, diagnostics=notes)


def normalize_herdtools_output(case_id, input_digest, text, *, exit_code, mapped,
                               version="7.58", command=("herd7",), timed_out=False, truncated=False):
    if not mapped:
        return backend_bundle("herdtools7", case_id, input_digest, version=version, license_id="CeCILL-B",
                              command=command, observation={}, applicability="not_applicable",
                              status="not_run", diagnostics=[diagnostic(
                                  "litmus_not_applicable", "源码无法可靠映射为 litmus", "Source cannot be reliably mapped to litmus")])
    lowered = text.lower()
    risk = "sometimes" in lowered or "witnesses" in lowered and "positive: 0" not in lowered
    complete = exit_code == 0 and bool(text.strip()) and not timed_out and not truncated
    status = "complete" if complete else "partial" if timed_out or truncated or exit_code == 0 else "failed"
    notes = [diagnostic("approximate_litmus", "litmus 映射是近似证据", "The litmus mapping is approximate evidence")]
    if timed_out:
        notes.append(diagnostic("backend_timeout", "herdtools7 超时", "herdtools7 timed out"))
    if truncated:
        notes.append(diagnostic("backend_truncated", "herdtools7 输出被截断", "herdtools7 output was truncated"))
    observation = {"risk": risk, "normalized": "allowed" if risk else "not-observed",
                   "source_equivalent": False} if text.strip() else {}
    return backend_bundle("herdtools7", case_id, input_digest, version=version, license_id="CeCILL-B",
                          command=command, observation=observation, applicability="approximate",
                          status=status, diagnostics=notes)


def import_devkit_evidence(manifest_path, case_id, input_digest):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    required = ("captured_on", "devkit_version", "llvm_version", "source_sha256", "bc_sha256", "command", "report_sha256")
    if any(name not in manifest for name in required):
        raise AnalysisError("backend_invalid", "DevKit evidence manifest is incomplete")
    if manifest["captured_on"] not in ("2026-09-10", "2026-09-11"):
        raise AnalysisError("backend_invalid", "DevKit historical evidence date is not recognized")
    return validation_document(
        "BackendEvidenceBundle", backend="devkit", backend_version=manifest["devkit_version"],
        license="external-proprietary-reference", case_id=case_id, applicability="approximate",
        status="complete", command=manifest["command"], input_digest=input_digest,
        raw_output_hashes=[manifest["source_sha256"], manifest["bc_sha256"], manifest["report_sha256"]],
        observation={"llvm_version": manifest["llvm_version"], "historical": True},
        captured_on=manifest["captured_on"], diagnostics=[],
    )


def compare_backend(truth, case_result, bundle):
    if bundle["applicability"] == "not_applicable":
        return "not_applicable"
    if bundle["status"] != "complete" or not bundle["observation"]:
        return "inconclusive"
    backend_risk = bool(bundle["observation"].get("risk"))
    truth_risk = bool(truth["expected"]["required_findings"])
    p4_risk = not case_result["matched"] or bool(case_result["_counts"]["tp"])
    return "agree" if backend_risk == truth_risk == p4_risk else "disagree"


def extension_decision(request_hash, report_hash, evidence):
    entries = []
    for capability in CAPABILITIES:
        item = evidence.get(capability, {})
        cases = int(item.get("blocking_cases", 0))
        candidates = int(item.get("blocking_candidates", 0))
        denominator = int(item.get("denominator", 0))
        gain = candidates / denominator if denominator else None
        state = "recommend" if cases and denominator else "defer" if denominator else "insufficient-evidence"
        entries.append({
            "capability": capability,
            "state": state,
            "blocking_cases": cases,
            "blocking_tus": int(item.get("blocking_tus", 0)),
            "blocking_candidates": candidates,
            "potential_coverage_gain": gain,
            "cost": item.get("cost", "unknown"),
            "compatibility": item.get("compatibility", "unknown"),
            "detail": f"{capability} 的量化证据状态为 {state}",
            "detail_en": f"Quantified evidence for {capability} is {state}",
            "suggestion": "由人工确认后另行创建 OpenSpec change",
            "suggestion_en": "Create a separate OpenSpec change only after human confirmation",
            "human_confirmed": False,
        })
    return validation_document("AnalysisExtensionDecision", request_hash=request_hash,
                               report_hash=report_hash, entries=entries)
