"""归约候选的稳定分组和局部 AST/IR 证据筛选。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .canonical import semantic_digest, stable_id


@dataclass(frozen=True)
class ReductionCandidate:
    identity: str
    facts: tuple[Mapping[str, Any], ...]


def candidates(facts: Sequence[Mapping[str, Any]], context: str) -> list[ReductionCandidate]:
    from .evidence import _points

    groups: dict[str, dict[str, Mapping[str, Any]]] = {}
    for fact in facts:
        if fact.get("fact_kind") != "reduction":
            continue
        payload = fact.get("payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        loop, accumulator = payload.get("loop_id"), payload.get("accumulator_id")
        identity = stable_id(
            "reduction_candidate",
            {
                "context": context,
                "function": fact.get("function_id"),
                "loop": loop,
                "recurrence": accumulator
                if loop and accumulator
                else fact.get("fact_id") or semantic_digest(fact),
            },
        )
        groups.setdefault(identity, {})[semantic_digest(fact)] = fact
    result = [
        ReductionCandidate(key, tuple(members[k] for k in sorted(members)))
        for key, members in groups.items()
    ]
    return sorted(
        result,
        key=lambda item: (
            str(item.facts[0].get("function_id")),
            min(
                (point for fact in item.facts for point in _points(fact.get("location"))),
                default=("", 0, 0),
            ),
            item.identity,
        ),
    )


def bound_evidence(
    candidate: ReductionCandidate,
    ir_bundles: Sequence[Mapping[str, Any]],
    evidence_bundles: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], bool]:
    """返回本候选的 IR、binding 和歧义标志；不按 TU 猜测关联。"""
    from .evidence import _compatible, _points

    sources = {str(fact["fact_id"]): fact for fact in candidate.facts}
    ir = {str(fact["fact_id"]): fact for bundle in ir_bundles for fact in bundle.get("facts", [])}
    bindings = [binding for bundle in evidence_bundles for binding in bundle.get("bindings", [])]
    owners: dict[str, set[str]] = {}
    for binding in bindings:
        owners.setdefault(str(binding.get("ir_fact_id")), set()).add(
            str(binding.get("source_fact_id"))
        )
    ambiguous = any(
        set(item.get("source_fact_ids", [])) & sources.keys()
        for bundle in evidence_bundles
        for item in bundle.get("ambiguities", [])
    )
    selected_ir: dict[str, Mapping[str, Any]] = {}
    selected_bindings: dict[str, Mapping[str, Any]] = {}
    for binding in bindings:
        source_id = str(binding.get("source_fact_id"))
        if source_id not in sources:
            continue
        ir_id = str(binding.get("ir_fact_id"))
        source, target = sources[source_id], ir.get(ir_id)
        if (
            target is None
            or not binding.get("binding_id")
            or binding.get("confidence") not in {"exact", "strong"}
            or not owners[ir_id] <= sources.keys()
        ):
            ambiguous = True
            continue
        # 显式 sidecar 也必须与可得的函数/debug 信息相容。
        symbol, function = source.get("function_symbol"), target.get("function")
        source_points = _points(source.get("location"))
        target_points = _points(target.get("debug_location"))
        explicit = binding.get("method") == "explicit-sidecar"
        position_matches = position_matches_source(source, target.get("debug_location"))
        if (
            not _compatible(source, target)
            or (symbol and function and symbol != function)
            or (source_points and target_points and not position_matches)
            or (not explicit and (not symbol or symbol != function or not position_matches))
        ):
            ambiguous = True
            continue
        selected_ir[ir_id] = target
        selected_bindings[str(binding["binding_id"])] = binding
    return (
        [selected_ir[key] for key in sorted(selected_ir)],
        [selected_bindings[key] for key in sorted(selected_bindings)],
        ambiguous,
    )


def position_matches_source(source: Mapping[str, Any], location: Any) -> bool:
    """Clang 指向左值，LLVM 常指向复合运算符；允许已知表达式范围内的位置。"""
    from .evidence import _point, _points

    points = _points(location)
    if set(_points(source.get("location"))) & set(points):
        return True
    source_range = source.get("source_range")
    if not isinstance(source_range, Mapping):
        return False
    begin, end = _point(source_range.get("begin")), _point(source_range.get("end"))
    return bool(
        begin
        and end
        and begin[0] == end[0]
        and any(p[0] == begin[0] and begin[1:] <= p[1:] <= end[1:] for p in points)
    )
