"""Strict contracts for the additive degraded source-analysis wrapper."""

from copy import deepcopy
import json
from pathlib import Path

import jsonschema

from .contracts import AnalysisError, canonical, file_hash, identity
from .language_standards import C_STANDARDS, CXX_STANDARDS


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/degraded_source_analysis.json"
PROTOCOL = ROOT / "protocols/degraded-source-analysis-protocol.json"
KINDS = (
    "DegradedSourceAnalysisRequest", "TUEvidenceAvailability", "SourceCandidate",
    "SynchronizationGap", "DegradedSourceAnalysisReport", "DegradedValidationSuite",
    "DegradedValidationTruth", "DegradedValidationReport",
)
MODES = ("ast-ir", "ir-only", "ast-only", "failed")


def _load(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError(code, f"Invalid or missing JSON: {path}") from exc


def expected_degraded_protocol(path=PROTOCOL):
    value = _load(path, "degraded_protocol")
    schema = _load(SCHEMA, "degraded_schema")
    try:
        maxima = {name: rule["maximum"] for name, rule in schema["$defs"]["Budgets"]["properties"].items()}
        expected = {
            "protocol_version": 1, "analysis_version": "0.1.0",
            "policy_id": "degraded-source-analysis-v1", "kinds": dict.fromkeys(KINDS, 1),
            "budgets": maxima,
        }
    except (KeyError, TypeError) as exc:
        raise AnalysisError("degraded_schema", "Degraded source-analysis budget schema is invalid") from exc
    if canonical(value) != canonical(expected):
        raise AnalysisError("degraded_protocol", "Degraded source-analysis protocol does not match its schema")
    return value


def semantic_digest(value):
    payload = deepcopy(value)
    payload.pop("semantic_digest", None)
    if payload.get("kind") == "DegradedSourceAnalysisReport":
        payload.pop("cache", None)
    return identity(payload)


def dependency(kind, key, value):
    return {"kind": kind, "id": key, "digest": identity(value)}


def input_hash(path):
    value = Path(path).resolve()
    return {"path": str(value), "sha256": file_hash(value)}


def stage_counts(planned, completed=0, failed=0, budget=0):
    values = (planned, completed, failed, budget)
    if any(type(item) is not int or item < 0 for item in values):
        raise AnalysisError("counts_invalid", "Stage counts must be non-negative integers")
    if completed + failed + budget > planned:
        raise AnalysisError("counts_invalid", "Stage counts exceed their planned denominator")
    return {"planned": planned, "completed": completed, "failed": failed, "budget": budget,
            "ratio": None if planned == 0 else completed / planned}


def diagnostic(code, detail, detail_en, *, suggestion=None, suggestion_en=None, source=None,
               limit=4096):
    def bounded(value):
        value = str(value or "")
        while len(value.encode("utf-8")) > limit:
            value = value[:-1]
        return value
    return {"code": code, "detail": bounded(detail), "detail_en": bounded(detail_en),
            "suggestion": None if suggestion is None else bounded(suggestion),
            "suggestion_en": None if suggestion_en is None else bounded(suggestion_en),
            "source": deepcopy(source)}


_FAILURE_TEXT = {
    "frontend-invalid": ("源文件无法由所选 profile 正确解析", "The source cannot be parsed under the selected profile",
                         "修复源文件、头文件或编译参数", "Repair the source, headers, or compilation arguments"),
    "profile-replay-incompatible": ("GCC 编译 profile 无法由 Clang 兼容重放", "The GCC compilation profile cannot be compatibly replayed by Clang",
                                    "移除不兼容选项或提供等价的 Clang profile", "Remove incompatible options or provide an equivalent Clang profile"),
    "external-artifact-missing": ("计划内的外部 LLVM BC 缺失", "A planned external LLVM bitcode artifact is missing",
                                  "在上游构建中补齐 BC 或登记真实失败项", "Produce the bitcode upstream or register the actual failed item"),
    "external-build-failed": ("上游构建未能生成计划内 LLVM BC", "The upstream build failed to produce planned LLVM bitcode",
                              "检查上游构建诊断并重新生成 bundle", "Inspect the upstream build diagnostic and regenerate the bundle"),
    "artifact-format-unsupported": ("外部输入不是受支持的 raw LLVM BC", "The external input is not supported raw LLVM bitcode",
                                    "提供逐 TU raw LLVM BC，而非容器、文本 IR 或 GCC LTO", "Provide per-TU raw LLVM bitcode, not a container, textual IR, or GCC LTO"),
    "reader-incompatible": ("LLVM reader 与外部 BC 或协议不兼容", "The LLVM reader is incompatible with the external bitcode or protocol",
                            "使用匹配的 reader 重新导入，不要在分析器内转换", "Re-import with a matching reader; do not convert inside the analyzer"),
    "ir-generation-failed": ("历史报告记录的 LLVM BC 生成失败", "Historical report: LLVM bitcode generation failed",
                             "仅用于读取旧报告；当前流程应检查外部 bundle", "Legacy reports only; inspect the external bundle in the current workflow"),
    "worker-budget": ("分析 worker 超出显式预算", "The analysis worker exceeded an explicit budget",
                      "收紧 scope 或显式提高预算后重试", "Narrow the scope or explicitly raise the budget and retry"),
    "artifact-validation-failed": ("显式分析产物缺失、损坏或已被替换", "An explicit analysis artifact is missing, corrupt, or replaced",
                                   "重新生成产物并更新其摘要引用", "Regenerate the artifact and update its digest reference"),
    "analysis-stage-failed": ("后续分析阶段失败", "A downstream analysis stage failed",
                              "检查阶段诊断并在新的输出目录重试", "Inspect the stage diagnostic and retry in a fresh output directory"),
}


def classify_failure(code, detail=""):
    value = f"{code} {detail}".lower()
    normalized = str(code).lower().replace("_", "-")
    exact = {
        "external-artifact-missing": "external-artifact-missing",
        "artifact-missing": "external-artifact-missing",
        "external-build-failed": "external-build-failed",
        "artifact-format-unsupported": "artifact-format-unsupported",
        "reader-incompatible": "reader-incompatible",
        "worker-protocol": "reader-incompatible",
        "reader-failed": "reader-incompatible",
        "ir-generation-failed": "ir-generation-failed",
    }
    if normalized in exact:
        return exact[normalized], "deterministic"
    if any(token in value for token in ("timeout", "budget", "output_limit", "resource")):
        return "worker-budget", "transient" if "resource" in value or "timeout" in value else "deterministic"
    if any(token in value for token in ("profile", "unsupported option", "unknown argument", "replay")):
        return "profile-replay-incompatible", "deterministic"
    if any(token in value for token in ("parse", "syntax", "include", "declaration", "type error", "frontend")):
        return "frontend-invalid", "deterministic"
    if any(token in value for token in ("elf", "gimple", "gcc lto", "textual ir", "raw llvm")):
        return "artifact-format-unsupported", "deterministic"
    if any(token in value for token in ("bitcode", "verify", "llvm reader", "worker protocol")):
        return "reader-incompatible", "deterministic"
    if any(token in value for token in ("digest", "reference", "schema", "artifact", "identity", "cache")):
        return "artifact-validation-failed", "deterministic"
    return "analysis-stage-failed", "transient" if any(token in value for token in ("crash", "io_failed", "nonzero")) else "deterministic"


def failure_record(physical_tu_id, stage, code, detail, *, dependency_value=None,
                   failure_class=None, stability=None, limit=4096):
    failure_class, inferred = (failure_class, stability or "deterministic") if failure_class else classify_failure(code, detail)
    stability = stability or inferred
    cn, en, suggestion, suggestion_en = _FAILURE_TEXT[failure_class]
    safe_detail = diagnostic(code, f"{cn}：{detail}", f"{en}: {detail}",
                             suggestion=suggestion, suggestion_en=suggestion_en, limit=limit)
    seed = {"physical_tu_id": physical_tu_id, "stage": stage, "failure_class": failure_class,
            "stability": stability, "code": code, "dependency": dependency_value}
    return {"id": identity(seed), **seed, "detail": safe_detail["detail"],
            "detail_en": safe_detail["detail_en"], "suggestion": safe_detail["suggestion"],
            "suggestion_en": safe_detail["suggestion_en"]}


def _unique_sorted(items, key, detail):
    keys = [key(item) for item in items]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise AnalysisError("invalid_reference", detail)
    return set(keys)


def _validate_request(value):
    for field in ("source_requests", "ir_requests"):
        _unique_sorted(value[field], lambda item: (item["path"], item["sha256"]),
                       f"{field} must be unique and sorted")
    _unique_sorted(value["module_facts"], lambda item: (item["kind"], item["id"]),
                   "ModuleFacts dependencies must be unique and sorted")
    _unique_sorted(value["declared_failures"], lambda item: item["id"],
                   "Declared failures must be unique and sorted")
    for field in ("source_requests", "ir_requests"):
        for item in value[field]:
            if Path(item["path"]).is_absolute() and Path(item["path"]).is_file() and file_hash(item["path"]) != item["sha256"]:
                raise AnalysisError("invalid_reference", f"Referenced request changed: {item['path']}")


def _validate_availability(value):
    valid = ({"compiler-default", "c89", "c99", "c11", "c17", "c23"} if value["language"] == "c" else {"compiler-default", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"})
    if value["standard"] not in valid:
        raise AnalysisError("profile_conflict", "Availability language and standard disagree")
    _unique_sorted(value["products"], lambda item: item["stage"], "Product states must be unique and sorted")
    failure_ids = _unique_sorted(value["failures"], lambda item: item["id"], "Failures must be unique and sorted")
    for product in value["products"]:
        if not set(product["failure_ids"]) <= failure_ids:
            raise AnalysisError("invalid_reference", "Product state has a dangling failure")
    _unique_sorted(value["dependencies"], lambda item: (item["kind"], item["id"]),
                   "Availability dependencies must be unique and sorted")


def _validate_candidate(value):
    supported = C_STANDARDS if value["language"] == "c" else CXX_STANDARDS
    if value["standard"] not in supported | {"compiler-default"}:
        raise AnalysisError("profile_conflict", "Source candidate language and standard disagree")
    for name in ("physical_tu_ids", "profile_ids", "node_ids", "relation_ids", "assumptions", "missing_evidence"):
        if value[name] != sorted(set(value[name])):
            raise AnalysisError("invalid_reference", f"Source candidate {name} must be unique and sorted")
    _unique_sorted(value["dependencies"], lambda item: (item["kind"], item["id"]),
                   "Source candidate dependencies must be unique and sorted")


def _validate_gap(value):
    for name in ("physical_tu_ids", "node_ids", "relation_ids", "object_candidates", "thread_candidates", "path_candidates"):
        if value[name] != sorted(set(value[name])):
            raise AnalysisError("invalid_reference", f"Synchronization gap {name} must be unique and sorted")
    _unique_sorted(value["dependencies"], lambda item: (item["kind"], item["id"]),
                   "Synchronization gap dependencies must be unique and sorted")


def _validate_report(value):
    expected = 1 if value["status"] == "failed" else 2 if value["status"] == "partial" else 3 if any(item["effective_status"] == "finding" for item in value["formal_assessments"]) else 0
    if value["exit_code"] != expected:
        raise AnalysisError("report_status", "Degraded report exit code does not match completeness precedence")
    if sum(value["mode_counts"].values()) != len(value["availabilities"]):
        raise AnalysisError("counts_invalid", "Mode counts do not match availability denominator")
    for name in ("availabilities", "source_candidates", "synchronization_gaps", "dependencies"):
        _unique_sorted(value[name], lambda item: (item["kind"], item["id"]), f"Report {name} must be unique and sorted")
    _unique_sorted(value["formal_assessments"], lambda item: item["id"], "Formal assessments must be unique and sorted")


def _validate_validation(value):
    if value["kind"] == "DegradedValidationSuite":
        _unique_sorted(value["cases"], lambda item: item["id"], "Validation cases must be unique and sorted")
        standards = {item["standard"] for item in value["cases"]}
        if standards != {"c11", "c17", "c++17", "c++20"}:
            raise AnalysisError("validation_denominator", "Validation suite must independently cover all four language profiles")
    elif value["kind"] == "DegradedValidationTruth":
        values = [item.get("case_id") for item in value["cases"]]
        if values != sorted(values) or len(values) != len(set(values)):
            raise AnalysisError("validation_denominator", "Truth cases must be unique and sorted")


def validate_degraded_document(value, kind):
    if kind not in KINDS:
        raise AnalysisError("schema_invalid", f"Unknown degraded source-analysis contract: {kind}")
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise AnalysisError("schema_version", f"{kind} requires schema_version=1")
    if value.get("kind") != kind:
        raise AnalysisError("schema_invalid", f"Expected kind {kind}")
    schema = _load(SCHEMA, "degraded_schema")
    try:
        jsonschema.Draft202012Validator({"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}).validate(value)
    except jsonschema.ValidationError as exc:
        raise AnalysisError("schema_invalid", str(exc)) from exc
    if kind == "DegradedSourceAnalysisRequest":
        _validate_request(value)
    elif kind == "TUEvidenceAvailability":
        _validate_availability(value)
    elif kind == "SourceCandidate":
        _validate_candidate(value)
    elif kind == "SynchronizationGap":
        _validate_gap(value)
    elif kind == "DegradedSourceAnalysisReport":
        _validate_report(value)
    elif kind.startswith("DegradedValidation"):
        _validate_validation(value)
    if "semantic_digest" in value and value["semantic_digest"] != semantic_digest(value):
        raise AnalysisError("semantic_digest", f"{kind} semantic digest does not match content")
    return value


def degraded_document(kind, **fields):
    protocol = expected_degraded_protocol()
    result = {"schema_version": 1, "kind": kind, "analysis_version": protocol["analysis_version"],
              "policy_id": protocol["policy_id"], **fields}
    if "semantic_digest" in result and result["semantic_digest"] is None:
        result["semantic_digest"] = semantic_digest(result)
    return validate_degraded_document(result, kind)


def read_degraded_document(path, kind):
    return validate_degraded_document(_load(path, "input_invalid"), kind)
