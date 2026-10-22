"""Test-only materializer and semantic validator for the schema-v2 design assets.

This module deliberately lives under tests.  It is not a serializer, a v1-to-v2
mapper, or production runtime code.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "schema-v2"
SCHEMA_PATH = ROOT / "schemas" / "scan-result-v2.schema.json"

CODE_STEP_KINDS = {
    "build_selector",
    "target_selection",
    "source_selection",
    "source_evidence",
    "macro_invocation",
    "macro_definition",
    "macro_replacement",
    "intrinsic_call",
    "vector_type",
    "compiler_flag",
    "test_asset",
}
NON_CODE_STEP_KINDS = {"knowledge_match", "classification", "assessment"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _segments(path: str) -> list[str]:
    return path.split(".") if path else []


def _descend(document: Any, path: str) -> Any:
    value = document
    for segment in _segments(path):
        value = value[int(segment)] if isinstance(value, list) else value[segment]
    return value


def _parent(document: Any, path: str) -> tuple[Any, str]:
    segments = _segments(path)
    if not segments:
        raise ValueError("an operation path must not be empty")
    parent = document
    for segment in segments[:-1]:
        parent = parent[int(segment)] if isinstance(parent, list) else parent[segment]
    return parent, segments[-1]


def apply_operations(document: Any, operations: Iterable[dict[str, Any]]) -> Any:
    result = copy.deepcopy(document)
    for operation in operations:
        op = operation["op"]
        path = operation["path"]
        if op in {"append", "reverse", "sort"}:
            target = _descend(result, path)
            if op == "append":
                target.append(copy.deepcopy(operation["value"]))
            elif op == "reverse":
                target.reverse()
            else:
                keys = operation["keys"]
                target.sort(key=lambda item: tuple(item[key] for key in keys))
            continue
        parent, key = _parent(result, path)
        resolved_key: Any = int(key) if isinstance(parent, list) else key
        if op == "set":
            parent[resolved_key] = copy.deepcopy(operation["value"])
        elif op == "delete":
            del parent[resolved_key]
        elif op == "copy":
            parent[resolved_key] = copy.deepcopy(_descend(result, operation["from"]))
        else:
            raise ValueError(f"unsupported fixture operation: {op}")
    return result


def materialize_variants(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    base = load_json(manifest_path.parent / manifest["base"])
    return {
        variant["name"]: apply_operations(base, variant["operations"])
        for variant in manifest["variants"]
    }


def schema_errors(document: Any) -> list[str]:
    validator = Draft202012Validator(load_json(SCHEMA_PATH))
    return [error.message for error in validator.iter_errors(document)]


def _duplicate(values: Iterable[str]) -> bool:
    materialized = list(values)
    return len(materialized) != len(set(materialized))


def _is_sorted(items: list[dict[str, Any]], keys: tuple[str, ...]) -> bool:
    actual = [tuple(item[key] for key in keys) for item in items]
    return actual == sorted(actual)


def _sources(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for finding in document.get("findings", []):
        yield finding["fact"]["primaryLocation"]
        for occurrence in finding.get("occurrences", []):
            yield occurrence["location"]
        for step in finding.get("evidenceChain", {}).get("steps", []):
            if "source" in step:
                yield step["source"]
    for diagnostic in document.get("diagnostics", []):
        if "representativeLocation" in diagnostic:
            yield diagnostic["representativeLocation"]


def _source_errors(source: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    path = source.get("file", "")
    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if posix.is_absolute() or windows.is_absolute() or "\\" in path or ".." in posix.parts:
        errors.add("source.path-project-relative")
    context = source.get("context", {})
    lines = context.get("lines", [])
    budget = context.get("budget", {})
    if len(lines) > budget.get("maxLines", 256) or sum(len(line.get("text", "")) for line in lines) > budget.get("maxCharacters", 65536):
        errors.add("source.context-budget")
    highlights = context.get("highlights", [])
    line_numbers = [line.get("line") for line in lines]
    if line_numbers != sorted(line_numbers) or len(line_numbers) != len(set(line_numbers)):
        errors.add("source.context-lines-ordered")
    by_line = {line.get("line"): line.get("text", "") for line in lines}
    highlight_keys: list[tuple[int, int, int]] = []
    for highlight in highlights:
        line = highlight.get("line")
        start = highlight.get("startColumn", 0)
        end = highlight.get("endColumn", 0)
        highlight_keys.append((line, start, end))
        text = by_line.get(line)
        if text is None or start < 1 or end <= start or end > len(text) + 1:
            errors.add("source.highlight-resolves")
    if highlight_keys != sorted(highlight_keys):
        errors.add("result.stable-order")
    if context.get("status") == "complete" and (not lines or not highlights):
        errors.add("source.complete-context-has-highlight")
    return errors


def reference_errors(document: dict[str, Any]) -> list[str]:
    errors: set[str] = set()
    findings = document.get("findings", [])
    if _duplicate(finding.get("id", "") for finding in findings):
        errors.add("result.finding-id-unique")
    if not _is_sorted(findings, ("id",)):
        errors.add("result.stable-order")

    source_catalog = {item["id"]: item for item in document.get("scan", {}).get("knowledgeSources", [])}
    for finding in findings:
        occurrences = finding.get("occurrences", [])
        occurrence_ids = {item.get("id") for item in occurrences}
        if len(occurrence_ids) != len(occurrences):
            errors.add("finding.occurrence-id-unique")
        if finding.get("primaryOccurrenceId") not in occurrence_ids:
            errors.add("finding.primary-occurrence-resolves")
        occurrence_order = sorted(
            occurrences,
            key=lambda item: (
                item["location"]["file"],
                item["location"]["span"]["start"]["line"],
                item["location"]["span"]["start"]["column"],
                item["id"],
            ),
        )
        if occurrences != occurrence_order:
            errors.add("result.stable-order")

        chain = finding.get("evidenceChain", {})
        steps = chain.get("steps", [])
        edges = chain.get("edges", [])
        breaks = chain.get("breaks", [])
        step_ids = {step.get("id") for step in steps}
        step_by_id = {step.get("id"): step for step in steps}
        if len(step_ids) != len(steps):
            errors.add("chain.step-id-unique")
        if chain.get("rootStepId") not in step_ids:
            errors.add("chain.root-step-resolves")
        primary_path = chain.get("primaryPath", [])
        if primary_path and chain.get("rootStepId") != primary_path[0]:
            errors.add("chain.primary-path-resolves")
        if any(step_id not in step_ids for step_id in primary_path):
            errors.add("chain.primary-path-resolves")
        if any(step_id not in step_ids for step_id in chain.get("impactStepIds", [])):
            errors.add("chain.impact-step-resolves")
        else:
            for step_id in chain.get("impactStepIds", []):
                if step_by_id[step_id].get("kind") not in {"classification", "assessment"}:
                    errors.add("chain.impact-step-resolves")

        resolved_edge_pairs: set[tuple[str, str]] = set()
        for edge in edges:
            start, end = edge.get("fromStepId"), edge.get("toStepId")
            if start not in step_ids or end not in step_ids:
                errors.add("chain.edge-endpoints-resolve")
            else:
                resolved_edge_pairs.add((start, end))
        for start, end in zip(primary_path, primary_path[1:]):
            if start in step_ids and end in step_ids and (start, end) not in resolved_edge_pairs:
                errors.add("chain.primary-path-connected")

        for item in breaks:
            if item.get("fromStepId") is not None and item["fromStepId"] not in step_ids:
                errors.add("chain.break-references-resolve")
            if any(candidate not in step_ids for candidate in item.get("candidateStepIds", [])):
                errors.add("chain.break-references-resolve")
        if chain.get("status") == "complete":
            if breaks:
                errors.add("chain.complete-has-no-break")
            primary_edges = {
                (edge.get("fromStepId"), edge.get("toStepId")): edge for edge in edges
            }
            if any(step_by_id.get(step_id, {}).get("status") != "complete" for step_id in primary_path):
                errors.add("chain.complete-has-no-break")
            if any(primary_edges.get(pair, {}).get("status") != "complete" for pair in zip(primary_path, primary_path[1:])):
                errors.add("chain.complete-has-no-break")
        elif chain.get("status") in {"partial", "ambiguous", "unknown"} and not breaks:
            errors.add("chain.incomplete-has-break")

        for step in steps:
            kind = step.get("kind")
            if kind in CODE_STEP_KINDS and "source" not in step:
                errors.add("step.code-kind-has-source")
            if kind in NON_CODE_STEP_KINDS and "source" in step:
                errors.add("step.non-code-kind-has-no-source")
            if kind == "knowledge_match":
                knowledge = step.get("knowledge", {})
                source = source_catalog.get(knowledge.get("sourceId"))
                required = {"entryId", "category", "symbol", "producer", "sourceId", "sourceSha256", "provenance"}
                if not required.issubset(knowledge) or source is None or source.get("sha256") != knowledge.get("sourceSha256"):
                    errors.add("step.knowledge-projection-complete")

        if not _is_sorted(steps, ("id",)) or not _is_sorted(edges, ("id",)) or not _is_sorted(breaks, ("id",)):
            errors.add("result.stable-order")

    for source in _sources(document):
        errors.update(_source_errors(source))
    diagnostics = document.get("diagnostics", [])
    if not _is_sorted(diagnostics, ("severity", "code", "stage", "id")):
        errors.add("result.stable-order")
    scope = document.get("scan", {}).get("scope", {})
    if not (
        scope.get("staticAnalysisOnly") is True
        and scope.get("compiled") is False
        and scope.get("linked") is False
        and scope.get("testsExecuted") is False
    ):
        errors.add("result.static-scope")
    return sorted(errors)


def validate_document(document: dict[str, Any]) -> list[str]:
    errors = reference_errors(document)
    if schema_errors(document):
        errors.append("schema.invalid")
    return sorted(set(errors))


def canonicalize(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize only contract-declared set-like collections for determinism tests."""
    result = copy.deepcopy(document)
    result["findings"].sort(key=lambda item: item["id"])
    result["diagnostics"].sort(key=lambda item: (item["severity"], item["code"], item["stage"], item["id"]))
    result["scan"]["knowledgeSources"].sort(key=lambda item: item["id"])
    for finding in result["findings"]:
        finding["occurrences"].sort(
            key=lambda item: (
                item["location"]["file"],
                item["location"]["span"]["start"]["line"],
                item["location"]["span"]["start"]["column"],
                item["id"],
            )
        )
        chain = finding["evidenceChain"]
        for key in ("steps", "edges", "breaks"):
            chain[key].sort(key=lambda item: item["id"])
        for source in [
            finding["fact"]["primaryLocation"],
            *(occurrence["location"] for occurrence in finding["occurrences"]),
            *(step["source"] for step in chain["steps"] if "source" in step),
        ]:
            source["context"]["lines"].sort(key=lambda item: item["line"])
            source["context"]["highlights"].sort(
                key=lambda item: (item["line"], item["startColumn"], item["endColumn"])
            )
    return result


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(canonicalize(document), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
