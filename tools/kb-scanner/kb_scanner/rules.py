from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

import yaml

from .models import Finding, ProjectFacts, Rule


def load_rules(rule_dir: Path) -> tuple[list[Rule], list[str]]:
    diagnostics: list[str] = []
    rules: list[Rule] = []
    for path in sorted((rule_dir / "rules").rglob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(f"{path}: YAML 加载失败: {exc}")
            continue
        if not isinstance(payload, dict):
            diagnostics.append(f"{path}: 规则必须是对象")
            continue
        try:
            rules.append(
                Rule(
                    id=str(payload["id"]),
                    language=str(payload.get("language", "cpp")),
                    severity=str(payload.get("severity", "medium")),
                    confidence=str(payload.get("confidence", "medium")),
                    capability=[str(item) for item in payload.get("capability", [])],
                    match=dict(payload.get("match", {})),
                    message=dict(payload.get("message", {})),
                )
            )
        except KeyError as exc:
            diagnostics.append(f"{path}: 缺少字段 {exc}")
    return rules, diagnostics


def load_generated_entries(rule_dir: Path) -> dict[str, set[str]]:
    generated_dir = rule_dir / "generated"
    if not generated_dir.exists():
        return {}
    merged: dict[str, set[str]] = {}
    for path in sorted(generated_dir.glob("*-x86-entries.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key, value in payload.items():
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                entries = set(value)
                if key == "compilerFlags":
                    entries -= {"-march", "-mtune", "-mcpu"}
                merged.setdefault(key, set()).update(entries)
    return merged


def evaluate_rules(
    project: ProjectFacts,
    rules: list[Rule],
    locale: str = "zh-CN",
    generated_entries: dict[str, set[str]] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    counter = 1
    generated_entries = generated_entries or {}
    file_facts_by_path = {str(file_facts.path.resolve()): file_facts for file_facts in project.files}
    for rule in rules:
        for file_facts in project.files:
            if not _rule_applies_to_file(rule, file_facts.path):
                continue
            for candidate in _iter_matches(rule, file_facts, generated_entries):
                conditions = candidate.get("conditions", [])
                classification = _classify_candidate(project, file_facts, candidate)
                if classification["hide_by_default"] and not project.include_inactive_branches:
                    continue
                message = _message(rule, locale)
                message_en = _message(rule, "en-US")
                condition_macros = _condition_macros(conditions)
                finding_type = str(classification.get("finding_type") or candidate.get("finding_type", "issue"))
                source_kind = str(candidate.get("source_kind", "code"))
                is_actionable = bool(candidate.get("is_actionable", True)) and bool(classification["is_blocking"])
                is_reference_source = bool(candidate.get("is_reference_source", True))
                severity = _apply_severity_policy(
                    rule_id=rule.id,
                    base_severity=rule.severity,
                    finding_type=finding_type,
                    is_reference_source=is_reference_source,
                    condition_macros=condition_macros,
                    source_kind=source_kind,
                    snippet=candidate.get("snippet", ""),
                )
                finding = Finding(
                    id=f"finding-{counter:04d}",
                    rule_id=rule.id,
                    severity=severity,
                    confidence=rule.confidence,
                    title=message.get("title", rule.id),
                    title_en=message_en.get("title", message.get("title", rule.id)),
                    file=candidate["file"],
                    line=candidate["line"],
                    column=None,
                    symbol=candidate.get("symbol"),
                    reason=_augment_reason(message.get("reason", ""), condition_macros, candidate),
                    reason_en=_augment_reason_en(
                        message_en.get("reason", message.get("reason", "")),
                        condition_macros,
                        candidate,
                    ),
                    suggestion=message.get("suggestion", ""),
                    suggestion_en=message_en.get("suggestion", message.get("suggestion", "")),
                    snippet=candidate.get("snippet", ""),
                    scan_mode=project.scan_mode,
                    finding_type=finding_type,
                    source_kind=source_kind,
                    is_actionable=is_actionable,
                    is_reference_source=is_reference_source,
                    is_blocking=bool(classification["is_blocking"]),
                    arch_reachability=str(classification["arch_reachability"]),
                    branch_group_id=classification.get("branch_group_id"),
                    branch_role=classification.get("branch_role"),
                    compatible_sibling_branch=bool(classification["compatible_sibling_branch"]),
                    compatible_branch_kind=classification.get("compatible_branch_kind"),
                    build_context=dict(classification["build_context"]),
                    alternative_impl=dict(classification["alternative_impl"]),
                    condition_macros=condition_macros,
                    trace={**candidate.get("trace", {}), "reachability": classification["trace"]},
                )
                findings.append(finding)
                counter += 1
        for candidate, file_facts in _iter_compile_command_matches(project, rule, generated_entries, file_facts_by_path):
            classification = _classify_candidate(project, file_facts, candidate)
            if classification["hide_by_default"] and not project.include_inactive_branches:
                continue
            message = _message(rule, locale)
            message_en = _message(rule, "en-US")
            finding_type = str(classification.get("finding_type") or candidate.get("finding_type", "issue"))
            source_kind = str(candidate.get("source_kind", "code"))
            condition_macros: list[str] = []
            severity = _apply_severity_policy(
                rule_id=rule.id,
                base_severity=rule.severity,
                finding_type=finding_type,
                is_reference_source=True,
                condition_macros=condition_macros,
                source_kind=source_kind,
                snippet=candidate.get("snippet", ""),
            )
            finding = Finding(
                id=f"finding-{counter:04d}",
                rule_id=rule.id,
                severity=severity,
                confidence=rule.confidence,
                title=message.get("title", rule.id),
                title_en=message_en.get("title", message.get("title", rule.id)),
                file=candidate["file"],
                line=candidate["line"],
                column=None,
                symbol=candidate.get("symbol"),
                reason=message.get("reason", ""),
                reason_en=message_en.get("reason", message.get("reason", "")),
                suggestion=message.get("suggestion", ""),
                suggestion_en=message_en.get("suggestion", message.get("suggestion", "")),
                snippet=candidate.get("snippet", ""),
                scan_mode=project.scan_mode,
                finding_type=finding_type,
                source_kind=source_kind,
                is_actionable=bool(candidate.get("is_actionable", True)) and bool(classification["is_blocking"]),
                is_reference_source=True,
                is_blocking=bool(classification["is_blocking"]),
                arch_reachability=str(classification["arch_reachability"]),
                branch_group_id=classification.get("branch_group_id"),
                branch_role=classification.get("branch_role"),
                compatible_sibling_branch=bool(classification["compatible_sibling_branch"]),
                compatible_branch_kind=classification.get("compatible_branch_kind"),
                build_context=dict(classification["build_context"]),
                alternative_impl=dict(classification["alternative_impl"]),
                condition_macros=condition_macros,
                trace={**candidate.get("trace", {}), "reachability": classification["trace"]},
            )
            if _merge_compile_command_evidence(findings, finding):
                continue
            findings.append(finding)
            counter += 1
    findings = _deduplicate(findings)
    if project.include_comment_hints:
        counter = len(findings) + 1
        for candidate in _iter_comment_hint_candidates(project):
            findings.append(
                Finding(
                    id=f"finding-{counter:04d}",
                    rule_id="COMMENT.ARCH.HINT",
                    severity="info",
                    confidence="medium",
                    title="注释中的架构线索",
                    title_en="Architecture hint in comment",
                    file=candidate["file"],
                    line=candidate["line"],
                    column=None,
                    symbol=candidate["symbol"],
                    reason="注释中出现架构、ISA 或 SIMD feature 线索，可用于理解该文件的多架构上下文，但本身不代表需要修复的代码问题。",
                    reason_en="The comment contains an architecture, ISA, or SIMD feature hint. It can help understand the file's multi-architecture context, but it is not actionable code by itself.",
                    suggestion="建议结合源码 finding 判断该线索是否对应真实后端、兼容层或能力检测逻辑。",
                    suggestion_en="Use this hint together with source-code findings to decide whether it points to a real backend, compatibility layer, or capability-detection path.",
                    snippet=candidate["snippet"],
                    scan_mode=project.scan_mode,
                    finding_type="hint",
                    source_kind="comment",
                    is_actionable=False,
                    is_reference_source=False,
                    is_blocking=False,
                    arch_reachability="unknown",
                    condition_macros=_condition_macros(candidate.get("conditions", [])),
                    trace={"commentHintRegex": ARCH_COMMENT_HINT_RE.pattern},
                )
            )
            counter += 1
    return _deduplicate(findings)


X86_MACROS = {
    "__x86_64__",
    "_M_X64",
    "__i386__",
    "_M_IX86",
    "__amd64__",
    "__SSE__",
    "__SSE2__",
    "__SSE3__",
    "__SSSE3__",
    "__SSE4_1__",
    "__SSE4_2__",
    "__AVX__",
    "__AVX2__",
    "__AVX512F__",
}

RISCV_MACROS = {
    "__riscv",
    "__riscv__",
    "__riscv_xlen",
    "__riscv_vector",
}

ARCH_COMMENT_HINT_RE = re.compile(
    r"\b("
    r"x86(?:_64)?|x86-64|amd64|i386|"
    r"avx(?:512[a-z0-9_]*)?|avx2|sse(?:[0-9.]+)?|ssse3|aesni"
    r")\b",
    re.IGNORECASE,
)

CRITICAL_RULES = {
    "ASM.X86.INSTRUCTION",
    "C_CPP.X86.HEADER",
    "C_CPP.X86.INTRINSIC_CALL",
    "C_CPP.X86.BUILTIN_CALL",
    "C_CPP.X86.VECTOR_TYPE",
    "C_CPP.X86.REGISTER_NAME",
}

HIGH_RULES = {
    "C_CPP.X86.API_CALL",
    "C_CPP.X86.ASM_MACRO",
    "C_CPP.X86.MACRO_EXPANDS_TO_INTRINSIC",
    "C_CPP.X86.TARGET_ATTRIBUTE",
    "C_CPP.GCC.VECTOR_SIZE",
}

MEDIUM_RULES = {
    "BUILD.X86.FEATURE_MACRO",
    "C_CPP.X86.COMPILER_FLAG",
    "C_CPP.X86.PLATFORM_MACRO",
    "C_CPP.X86.LOCAL_ARCH_HEADER",
}

LOW_RULES = {
    "C_CPP.ARCH.ALIGNMENT_ASSUMPTION",
    "C.X86.GENERIC_DISPATCH",
    "C.GNU.X86_STATEMENT_EXPRESSION",
    "CPP.X86.TEMPLATE_SPECIALIZATION",
    "CPP.X86.CONSTEXPR_ARCH_BRANCH",
}

C_SUFFIXES = {".c"}
CPP_SUFFIXES = {".cc", ".cpp", ".cxx", ".c++", ".hh", ".hpp", ".hxx", ".h++"}
HEADER_SUFFIXES = {".h"}
ASM_SUFFIXES = {".s", ".S", ".asm", ".inc"}
BUILD_FILE_NAMES = {
    "CMakeLists.txt",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "meson.build",
    "BUILD",
    "BUILD.bazel",
    "configure.ac",
    "build.zig",
}
BUILD_FILE_SUFFIXES = {".mk", ".cmake", ".bzl", ".am", ".m4", ".in", ".sh", ".zig", ".vcxproj", ".props", ".targets"}
RPM_SPEC_SUFFIXES = {".spec"}


def _rule_applies_to_file(rule: Rule, path: Path) -> bool:
    language = rule.language.lower().replace("-", "_")
    if path.suffix.lower() in RPM_SPEC_SUFFIXES and language != "rpm_spec":
        return False
    if language in {"*", "any"}:
        return True
    if language == "build":
        return path.name in BUILD_FILE_NAMES or path.suffix.lower() in BUILD_FILE_SUFFIXES
    if language == "rpm_spec":
        return path.suffix.lower() in RPM_SPEC_SUFFIXES
    if language == "asm":
        return path.suffix in ASM_SUFFIXES
    if language == "c_cpp":
        return path.suffix.lower() in C_SUFFIXES | CPP_SUFFIXES | HEADER_SUFFIXES
    if language == "c":
        return path.suffix.lower() in C_SUFFIXES
    if language == "cpp":
        return path.suffix.lower() in CPP_SUFFIXES
    return True


def _apply_severity_policy(
    rule_id: str,
    base_severity: str,
    finding_type: str,
    is_reference_source: bool,
    condition_macros: list[str],
    source_kind: str,
    snippet: str,
) -> str:
    if finding_type == "hint" or source_kind == "comment":
        return "info"
    if finding_type in {"inactive", "guarded"}:
        return "info"
    if finding_type == "portability_gap" and rule_id in CRITICAL_RULES:
        return "high"
    if not is_reference_source:
        return "medium"
    if rule_id in LOW_RULES:
        return "low"
    if rule_id in MEDIUM_RULES:
        return "medium"
    if rule_id in HIGH_RULES:
        return "high"
    if rule_id in CRITICAL_RULES:
        return "high" if condition_macros else "critical"
    return base_severity


def _classify_candidate(project: ProjectFacts, file_facts: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    conditions = candidate.get("conditions", [])
    branch = _branch_context(file_facts, conditions)
    build_context = _build_context(project, candidate["file"])
    alternative = _alternative_impl(project, candidate["file"])

    trace = {
        "branch": branch,
        "buildContext": build_context,
        "alternativeImpl": alternative,
    }

    classification = {
        "finding_type": "issue",
        "arch_reachability": build_context["included_in_riscv_build"],
        "is_blocking": True,
        "hide_by_default": False,
        "branch_group_id": branch.get("branch_group_id"),
        "branch_role": branch.get("branch_role"),
        "compatible_sibling_branch": branch.get("compatible_sibling_branch", False),
        "compatible_branch_kind": branch.get("compatible_branch_kind"),
        "build_context": build_context,
        "alternative_impl": alternative,
        "trace": trace,
    }

    if build_context["included_in_riscv_build"] == "false":
        classification.update(
            {
                "finding_type": "inactive",
                "arch_reachability": "inactive_on_riscv",
                "is_blocking": False,
                "hide_by_default": True,
            }
        )
        return classification

    if branch["is_x86_guarded"] and branch["compatible_sibling_branch"]:
        classification.update(
            {
                "finding_type": "guarded",
                "arch_reachability": "inactive_on_riscv",
                "is_blocking": False,
                "hide_by_default": True,
            }
        )
        return classification

    if branch["is_x86_guarded"] and branch["branch_role"] == "x86_branch":
        classification.update(
            {
                "finding_type": "inactive",
                "arch_reachability": "inactive_on_riscv",
                "is_blocking": False,
                "hide_by_default": True,
            }
        )
        return classification

    if branch["is_x86_guarded"] and not branch["compatible_sibling_branch"]:
        classification.update(
            {
                "finding_type": "portability_gap",
                "arch_reachability": "unknown" if build_context["included_in_riscv_build"] == "unknown" else "active_on_riscv",
                "is_blocking": True,
            }
        )
        return classification

    if alternative["is_x86_scoped"] and alternative["has_compatible_alternative"]:
        classification.update(
            {
                "finding_type": "inactive",
                "arch_reachability": "inactive_on_riscv",
                "is_blocking": False,
                "hide_by_default": True,
            }
        )
        return classification

    if alternative["is_x86_scoped"] and not alternative["has_compatible_alternative"]:
        classification.update(
            {
                "finding_type": "portability_gap",
                "arch_reachability": "unknown" if build_context["included_in_riscv_build"] == "unknown" else "active_on_riscv",
                "is_blocking": True,
            }
        )
        return classification

    classification["arch_reachability"] = (
        "active_on_riscv" if build_context["included_in_riscv_build"] == "true" else "unknown"
    )
    return classification


def _branch_context(file_facts: Any, conditions: list[Any]) -> dict[str, Any]:
    branch_frame = next((condition for condition in reversed(conditions) if getattr(condition, "branch_group_id", None)), None)
    if not branch_frame:
        return {
            "is_x86_guarded": False,
            "branch_group_id": None,
            "branch_role": None,
            "compatible_sibling_branch": False,
            "compatible_branch_kind": None,
        }

    group_id = getattr(branch_frame, "branch_group_id", None)
    group = file_facts.branch_groups.get(group_id)
    compatible_kind = None
    if group:
        for branch in group.branches:
            if branch.line == getattr(branch_frame, "line", None):
                continue
            if branch.role == "riscv_branch":
                compatible_kind = "riscv"
                break
            if branch.role == "generic_branch":
                compatible_kind = "generic"
            elif branch.role == "fallback_branch" and compatible_kind is None:
                compatible_kind = "fallback"

    return {
        "is_x86_guarded": _is_guarded_x86_candidate(conditions, getattr(branch_frame, "branch_role", "unknown")),
        "branch_group_id": group_id,
        "branch_role": getattr(branch_frame, "branch_role", "unknown"),
        "compatible_sibling_branch": compatible_kind is not None,
        "compatible_branch_kind": compatible_kind,
    }


def _is_guarded_x86_candidate(conditions: list[Any], branch_role: str) -> bool:
    if not conditions:
        return False
    if branch_role == "riscv_branch":
        return False
    return True


def _build_context(project: ProjectFacts, file_path: Path) -> dict[str, Any]:
    if not project.compile_contexts:
        return {"included_in_riscv_build": "unknown", "source": "source_context"}
    resolved = str(file_path.resolve())
    is_build_file = file_path.name in BUILD_FILE_NAMES or file_path.suffix.lower() in BUILD_FILE_SUFFIXES | RPM_SPEC_SUFFIXES
    if is_build_file:
        return {
            "included_in_riscv_build": "unknown",
            "source": "compile_commands.json",
            "reason": "build_file_not_represented_in_compile_database",
        }
    included = resolved in project.compile_reachable_files
    if not included:
        return {
            "included_in_riscv_build": "unknown",
            "source": "compile_commands.json",
            "reason": "not_reached_from_compile_database",
        }
    return {
        "included_in_riscv_build": "true",
        "source": "compile_commands.json",
    }


ARCH_PATH_PARTS = {
    "x86",
    "x86_64",
    "x64",
    "amd64",
    "i386",
    "i686",
    "sse",
    "sse2",
    "ssse3",
    "avx",
    "avx2",
    "avx512",
}
COMPATIBLE_ARCH_PARTS = {"riscv", "riscv64", "rvv", "generic", "portable", "scalar", "fallback", "common"}


def _alternative_impl(project: ProjectFacts, file_path: Path) -> dict[str, Any]:
    cache = getattr(project, "_alternative_impl_cache", None)
    if cache is None:
        cache = {}
        setattr(project, "_alternative_impl_cache", cache)
    relative = _safe_relative(file_path, project.root)
    cache_key = relative.as_posix()
    if cache_key in cache:
        return dict(cache[cache_key])

    parts = [part.lower() for part in relative.parts]
    is_x86_scoped = any(part in ARCH_PATH_PARTS for part in parts) or any(
        token in relative.stem.lower() for token in ("x86", "sse", "avx", "amd64")
    )
    if not is_x86_scoped:
        result = {
            "is_x86_scoped": False,
            "has_riscv_alternative": False,
            "has_generic_alternative": False,
            "has_compatible_alternative": False,
            "matched_by": None,
        }
        cache[cache_key] = result
        return dict(result)

    known_files = getattr(project, "_known_files_cache", None)
    if known_files is None:
        known_files = {_safe_relative(facts.path, project.root).as_posix() for facts in project.files}
        setattr(project, "_known_files_cache", known_files)
    candidates: list[str] = []
    for index, part in enumerate(relative.parts):
        if part.lower() not in ARCH_PATH_PARTS:
            continue
        for replacement in COMPATIBLE_ARCH_PARTS:
            new_parts = list(relative.parts)
            new_parts[index] = replacement
            candidates.append(Path(*new_parts).as_posix())

    for replacement in COMPATIBLE_ARCH_PARTS:
        candidates.append(relative.with_name(_replace_arch_token(relative.name, replacement)).as_posix())

    matched = next((candidate for candidate in candidates if candidate in known_files), None)
    matched_by = "sibling_file" if matched else None
    matched_text = matched.lower() if matched else ""
    has_riscv = bool(matched and any(part in matched_text for part in ("riscv", "rvv")))
    has_generic = bool(matched and any(part in matched_text for part in ("generic", "portable", "scalar", "fallback", "common")))
    result = {
        "is_x86_scoped": True,
        "has_riscv_alternative": has_riscv,
        "has_generic_alternative": has_generic,
        "has_compatible_alternative": matched is not None,
        "matched_by": matched_by,
        "matched_path": str(project.root / Path(matched)) if matched else None,
    }
    cache[cache_key] = result
    return dict(result)


def _replace_arch_token(name: str, replacement: str) -> str:
    return re.sub(r"(?i)(x86_64|x86|amd64|i386|i686|avx512|avx2|avx|sse2|sse)", replacement, name)


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        try:
            return path.absolute().relative_to(root.absolute())
        except ValueError:
            return Path(path.name)


def _is_inactive_for_target(conditions: list[Any], target_arch: str) -> bool:
    normalized_target = target_arch.lower().replace("-", "")
    if not normalized_target.startswith("riscv"):
        return False
    if not conditions:
        return False
    return any(_condition_is_x86_only(condition) for condition in conditions)


def _condition_is_x86_only(condition: Any) -> bool:
    kind = getattr(condition, "kind", "")
    expr = str(getattr(condition, "expr", ""))
    if kind in {"else", "ifndef"}:
        return False
    macros = set(re.findall(r"[A-Za-z_]\w*", expr))
    if not macros:
        return False
    has_x86 = bool(macros & X86_MACROS)
    has_riscv = bool(macros & RISCV_MACROS)
    unknown = macros - X86_MACROS - RISCV_MACROS - {"defined"}
    return has_x86 and not has_riscv and not unknown


def _iter_comment_hint_candidates(project: ProjectFacts):
    for file_facts in project.files:
        in_block_comment = False
        for text in file_facts.texts:
            comment = _comment_text(text.text, in_block_comment)
            stripped = text.text.lstrip()
            if in_block_comment and "*/" in stripped:
                in_block_comment = False
            elif not in_block_comment and "/*" in stripped and "*/" not in stripped:
                in_block_comment = True
            if not comment:
                continue
            match = ARCH_COMMENT_HINT_RE.search(comment)
            if not match:
                continue
            yield {
                "file": text.file,
                "line": text.line,
                "symbol": match.group(1),
                "snippet": text.text.strip(),
                "conditions": text.conditions,
            }


def _comment_text(line: str, in_block_comment: bool) -> str | None:
    stripped = line.lstrip()
    if in_block_comment:
        return stripped.split("*/", 1)[0].strip(" *")
    if stripped.startswith("//"):
        return stripped[2:].strip()
    if stripped.startswith("/*"):
        return stripped[2:].split("*/", 1)[0].strip(" *")
    if stripped.startswith("*"):
        return stripped[1:].strip()
    if "//" in line:
        return line.split("//", 1)[1].strip()
    return None


def _iter_matches(rule: Rule, file_facts: Any, generated_entries: dict[str, set[str]]):
    clauses = rule.match.get("any")
    if clauses is None:
        clauses = [rule.match]
    for clause in clauses:
        if "include" in clause:
            include_rule = clause["include"]
            paths = set(include_rule.get("pathIn", []))
            if generated_set := include_rule.get("generatedSet"):
                paths.update(generated_entries.get(str(generated_set), set()))
            for include in file_facts.includes:
                if include.path in paths:
                    open_mark = "<" if include.system else '"'
                    close_mark = ">" if include.system else '"'
                    yield {
                        "file": include.file,
                        "line": include.line,
                        "symbol": include.path,
                        "snippet": f"#include {open_mark}{include.path}{close_mark}",
                        "conditions": include.conditions,
                        "is_reference_source": True,
                        "trace": {"include": include.path},
                    }
        if "call" in clause:
            call_rule = clause["call"]
            name_regex = call_rule.get("nameRegex")
            generated_set = set()
            if generated_name := call_rule.get("generatedSet"):
                generated_set = generated_entries.get(str(generated_name), set())
            if not name_regex and not generated_set:
                continue
            pattern = re.compile(name_regex) if name_regex else None
            for call in file_facts.calls:
                if (pattern and pattern.search(call.name)) or call.name in generated_set:
                    trace = {"call": call.name}
                    if call.via_macro:
                        trace["macro"] = call.via_macro
                        trace["macroDefinitionLine"] = call.macro_definition_line
                    yield {
                        "file": call.file,
                        "line": call.line,
                        "symbol": call.name,
                        "snippet": call.text,
                        "conditions": call.conditions,
                        "is_reference_source": call.via_macro is None,
                        "trace": trace,
                    }
        if "macroExpansion" in clause:
            expansion_rule = clause["macroExpansion"]
            name_regex = expansion_rule.get("expandedCallNameRegex")
            if not name_regex:
                continue
            pattern = re.compile(name_regex)
            for call in file_facts.calls:
                if call.via_macro and pattern.search(call.name):
                    yield {
                        "file": call.file,
                        "line": call.line,
                        "symbol": call.name,
                        "snippet": call.text,
                        "conditions": call.conditions,
                        "is_reference_source": False,
                        "trace": {
                            "call": call.name,
                            "macro": call.via_macro,
                            "macroDefinitionLine": call.macro_definition_line,
                        },
                    }
        if "text" in clause:
            text_rule = clause["text"]
            patterns = []
            if "regex" in text_rule:
                patterns.append(re.compile(text_rule.get("regex", "a^")))
            if generated_set := text_rule.get("generatedSet"):
                values = sorted(generated_entries.get(str(generated_set), set()), key=len, reverse=True)
                if values:
                    patterns.append(
                        re.compile(
                            r"(?<![A-Za-z0-9_./+-])("
                            + "|".join(re.escape(item) for item in values)
                            + r")(?![A-Za-z0-9_./+-])"
                        )
                    )
            if not patterns:
                patterns.append(re.compile("a^"))
            for text in file_facts.texts:
                if not _path_allowed(text.file, text_rule):
                    continue
                if not _rpm_section_allowed(text, text_rule):
                    continue
                if text_rule.get("ignoreCommentLines") and _is_comment_line(text.text, text.file):
                    continue
                if text_rule.get("ignoreRpmChangelog") and _rpm_metadata(text).get("changelog"):
                    continue
                if text_rule.get("ignoreEndifLines") and text.text.lstrip().startswith("#endif"):
                    continue
                matched_line = False
                for pattern in patterns:
                    match = pattern.search(text.text)
                    if match:
                        symbol = _match_symbol(match, text_rule)
                        yield {
                            "file": text.file,
                            "line": text.line,
                            "symbol": symbol,
                            "snippet": text.text.strip(),
                            "conditions": text.conditions,
                            "source_kind": text_rule.get("sourceKind") or _rpm_metadata(text).get("sourceKind") or "code",
                            "finding_type": text_rule.get("findingType", "issue"),
                            "is_reference_source": text_rule.get("isReferenceSource", True),
                            "trace": {"textRegex": pattern.pattern, **_text_metadata_trace(text, text_rule)},
                        }
                        matched_line = True
                        if text_rule.get("singleFindingPerLine"):
                            break
                if matched_line and text_rule.get("singleFindingPerLine"):
                    continue


def _iter_compile_command_matches(
    project: ProjectFacts,
    rule: Rule,
    generated_entries: dict[str, set[str]],
    file_facts_by_path: dict[str, Any],
):
    if not project.compile_contexts:
        return
    if rule.id not in {"C_CPP.X86.COMPILER_FLAG", "C_CPP.X86.PLATFORM_MACRO"}:
        return

    emitted: set[tuple[str, str, str]] = set()
    for source_path, context in sorted(project.compile_contexts.items(), key=lambda item: item[1].entry_index):
        resolved = str(Path(source_path).resolve())
        file_facts = file_facts_by_path.get(resolved)
        if file_facts is None:
            project.diagnostics.append(
                f"跳过未在扫描范围内的 compile command: entry={context.entry_index}"
            )
            continue
        if not _path_is_under(file_facts.path, project.root):
            project.diagnostics.append(
                f"跳过源码根目录外的 compile command: entry={context.entry_index}"
            )
            continue

        if rule.id == "C_CPP.X86.COMPILER_FLAG":
            for token, token_index in _compile_command_flag_tokens(context.tokens, rule, generated_entries):
                relative_file = _safe_relative(file_facts.path, project.root).as_posix()
                key = (rule.id, relative_file, token)
                if key in emitted:
                    continue
                emitted.add(key)
                yield {
                    "file": file_facts.path,
                    "line": 1,
                    "symbol": token,
                    "snippet": f"compile command token: {token}",
                    "conditions": [],
                    "source_kind": "compile_command",
                    "is_reference_source": True,
                    "trace": {
                        "compileCommand": _compile_command_evidence(
                            context=context,
                            project=project,
                            source_path=file_facts.path,
                            token=token,
                            token_kind="compiler_flag",
                            token_index=token_index,
                        )
                    },
                }, file_facts
        elif rule.id == "C_CPP.X86.PLATFORM_MACRO":
            for macro, value in sorted(context.defines.items()):
                if not _is_x86_platform_macro(macro, generated_entries):
                    continue
                relative_file = _safe_relative(file_facts.path, project.root).as_posix()
                key = (rule.id, relative_file, macro)
                if key in emitted:
                    continue
                emitted.add(key)
                symbol = macro if value is None else f"{macro}={value}"
                yield {
                    "file": file_facts.path,
                    "line": 1,
                    "symbol": macro,
                    "snippet": f"compile command define: -D{symbol}",
                    "conditions": [],
                    "source_kind": "compile_command",
                    "is_reference_source": True,
                    "trace": {
                        "compileCommand": _compile_command_evidence(
                            context=context,
                            project=project,
                            source_path=file_facts.path,
                            token=f"-D{symbol}",
                            token_kind="define",
                            token_index=_token_index(context.tokens, f"-D{symbol}", macro),
                        )
                    },
                }, file_facts


def _compile_command_flag_tokens(
    tokens: list[str],
    rule: Rule,
    generated_entries: dict[str, set[str]],
) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        compound = token
        if token in {"-march", "-mtune", "-mcpu"} and index + 1 < len(tokens):
            compound = f"{token}={tokens[index + 1]}"
        if _compile_command_token_matches_text_rule(compound, rule, generated_entries):
            result.append((compound, index))
        index += 1
    return result


def _compile_command_token_matches_text_rule(
    token: str,
    rule: Rule,
    generated_entries: dict[str, set[str]],
) -> bool:
    clauses = rule.match.get("any")
    if clauses is None:
        clauses = [rule.match]
    for clause in clauses:
        text_rule = clause.get("text")
        if not isinstance(text_rule, dict):
            continue
        if generated_set := text_rule.get("generatedSet"):
            if token in generated_entries.get(str(generated_set), set()):
                return True
        if regex := text_rule.get("regex"):
            if re.compile(str(regex)).search(token):
                return True
    return False


def _is_x86_platform_macro(macro: str, generated_entries: dict[str, set[str]]) -> bool:
    platform_macros = {item.upper() for item in generated_entries.get("platformMacros", set())}
    return macro.upper() in platform_macros or macro.upper() in {item.upper() for item in X86_MACROS}


def _compile_command_evidence(
    context: Any,
    project: ProjectFacts,
    source_path: Path,
    token: str,
    token_kind: str,
    token_index: int | None,
) -> dict[str, Any]:
    return {
        "sourceKind": "compile_command",
        "entryIndex": context.entry_index,
        "sourceFile": _safe_relative(source_path, project.root).as_posix(),
        "token": token,
        "tokenKind": token_kind,
        "tokenIndex": token_index,
        "compiler": Path(context.compiler).name if context.compiler else None,
    }


def _token_index(tokens: list[str], raw_token: str, macro: str) -> int | None:
    for index, token in enumerate(tokens):
        if token == raw_token or token == f"-D{macro}":
            return index
        if token == "-D" and index + 1 < len(tokens) and tokens[index + 1].split("=", 1)[0] == macro:
            return index
    return None


def _path_is_under(path: Path, root: Path) -> bool:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _merge_compile_command_evidence(findings: list[Finding], compile_finding: Finding) -> bool:
    if compile_finding.source_kind != "compile_command":
        return False
    evidence = compile_finding.trace.get("compileCommand")
    if not evidence:
        return False
    for existing in findings:
        if existing.source_kind == "compile_command":
            continue
        if existing.rule_id != compile_finding.rule_id:
            continue
        if existing.symbol != compile_finding.symbol:
            continue
        trace = dict(existing.trace)
        evidence_list = list(trace.get("compileCommandEvidence") or [])
        evidence_key = (evidence.get("entryIndex"), evidence.get("sourceFile"), evidence.get("token"))
        existing_keys = {
            (item.get("entryIndex"), item.get("sourceFile"), item.get("token"))
            for item in evidence_list
            if isinstance(item, dict)
        }
        if evidence_key not in existing_keys:
            evidence_list.append(evidence)
        trace["compileCommandEvidence"] = evidence_list
        existing.trace = trace
        return True
    return False


def _message(rule: Rule, locale: str) -> dict[str, str]:
    message = rule.message.get(locale) or rule.message.get("zh-CN") or rule.message.get("en-US") or {}
    return {str(k): str(v) for k, v in message.items()}


def _match_symbol(match: re.Match[str], text_rule: dict[str, Any]) -> str:
    symbol_group = text_rule.get("symbolGroup")
    if symbol_group is not None:
        try:
            group = match.group(int(symbol_group))
        except (IndexError, ValueError):
            group = None
        if group:
            return group
    return next((group for group in reversed(match.groups()) if group), match.group(0))


def _is_comment_line(line: str, path: Path) -> bool:
    stripped = line.lstrip()
    if path.name in {"Makefile", "makefile", "GNUmakefile"} or path.suffix.lower() in {".mk", ".cmake", ".am", ".m4", ".spec"}:
        return stripped.startswith("#")
    return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")


def _path_allowed(path: Path, text_rule: dict[str, Any]) -> bool:
    names = {str(item) for item in text_rule.get("pathNameIn", [])}
    if names and path.name not in names:
        return False
    suffixes = {str(item) for item in text_rule.get("pathSuffixIn", [])}
    if suffixes and path.suffix.lower() not in {suffix.lower() for suffix in suffixes}:
        return False
    return True


def _rpm_section_allowed(text: Any, text_rule: dict[str, Any]) -> bool:
    sections = {str(item).lower() for item in text_rule.get("rpmSections", [])}
    if not sections:
        return True
    return str(_rpm_metadata(text).get("section") or "").lower() in sections


def _rpm_metadata(text: Any) -> dict[str, Any]:
    metadata = getattr(text, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _text_metadata_trace(text: Any, text_rule: dict[str, Any]) -> dict[str, Any]:
    metadata = _rpm_metadata(text)
    if not metadata:
        return {}
    keys = text_rule.get("traceMetadataKeys") or []
    if not keys:
        keys = ["sourceKind", "section", "rpmTag", "archTokens", "rpmMacro", "rpmMacroRelevant"]
    selected = {}
    for key in keys:
        if key not in metadata:
            continue
        value = metadata[key]
        if value is None or value == "" or value == []:
            continue
        selected[key] = value
    return {"metadata": selected} if selected else {}


def _condition_macros(conditions: list[Any]) -> list[str]:
    result: list[str] = []
    for condition in conditions:
        macro = getattr(condition, "macro", None)
        if macro and macro not in result:
            result.append(macro)
    return result


def _augment_reason(reason: str, condition_macros: list[str], candidate: dict[str, Any]) -> str:
    if not condition_macros:
        return reason
    symbol = candidate.get("symbol") or "该代码"
    macros = ", ".join(condition_macros)
    return f"{reason} 该风险位于条件编译块内，受自定义宏 {macros} 控制；宏名本身不一定包含架构信息，风险来自其保护的代码内容 {symbol}。"


def _augment_reason_en(reason: str, condition_macros: list[str], candidate: dict[str, Any]) -> str:
    if not condition_macros:
        return reason
    symbol = candidate.get("symbol") or "this code"
    macros = ", ".join(condition_macros)
    return (
        f"{reason} This risk is inside a conditional compilation block controlled by custom macro(s) "
        f"{macros}. The macro name itself may not encode the architecture; the risk comes from the "
        f"guarded code content: {symbol}."
    )


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int, str | None]] = set()
    result: list[Finding] = []
    for finding in findings:
        key = (finding.rule_id, str(finding.file), finding.line, finding.symbol)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result

