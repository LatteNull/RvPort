"""验证标量使用记录；残缺记录只能保留为 partial，不能成为排除证明。"""
from collections.abc import Mapping
import re
from ..frontends.cpp.usage_bindings import bind


def _key(value):
    return (isinstance(value, tuple) and len(value) == 3
            and type(value[0]) is int and type(value[1]) is int
            and 0 <= value[0] <= value[1] and isinstance(value[2], str) and bool(value[2]))


def _span(value):
    return (isinstance(value, tuple) and len(value) == 4
            and all(type(part) is int and part > 0 for part in value)
            and value[:2] <= value[2:])


def validate_usage(item):
    """返回结构错误；partial 的未采集端点允许保留，但绝不升级 complete。"""
    scope = item.metadata.get("usageScope")
    if not isinstance(scope, Mapping) or item.location is None:
        return ("usage-invalid-scope",)
    if "compilationContextId" in item.metadata and not re.fullmatch(
            r"[0-9a-f]{64}", str(item.metadata["compilationContextId"])):
        return ("usage-invalid-configuration",)
    records = scope.get("records")
    if (scope.get("version") != 1 or type(scope.get("version")) is not int
            or scope.get("status") not in {"complete", "partial"}
            or not isinstance(records, tuple)
            or type(scope.get("recordCount")) is not int
            or scope["recordCount"] != len(records)
            or type(scope.get("scopeLimit")) is not int
            or not 0 <= len(records) <= scope["scopeLimit"] <= 10000
            or not isinstance(scope.get("reasonCodes"), tuple)
            or not all(isinstance(reason, str) and reason for reason in scope["reasonCodes"])):
        return ("usage-invalid-summary",)
    complete = scope["status"] == "complete"
    if complete and (scope["reasonCodes"] or not records):
        return ("usage-inconsistent-completion",)
    by_key = {}
    start = (item.location.start.line, item.location.start.column)
    end = (item.location.end.line, item.location.end.column)
    for row in records:
        if (not isinstance(row, Mapping) or not _key(row.get("key"))
                or not _span(row.get("span")) or row.get("kind") != row["key"][2]
                or not isinstance(row.get("fields"), Mapping)
                or not isinstance(row.get("children"), tuple)
                or not isinstance(row.get("text"), str) or not isinstance(row.get("operator"), str)):
            return ("usage-invalid-record",)
        if start[1] is None or end[1] is None or not start <= row["span"][:2] <= row["span"][2:] <= end:
            return ("usage-invalid-span",)
        if row["key"] in by_key:
            return ("usage-duplicate-record",)
        by_key[row["key"]] = row
    for index, row in enumerate(records):
        parent = row.get("parent")
        if index == 0:
            if parent is not None or row["kind"] != "function_definition":
                return ("usage-invalid-owner",)
        elif not _key(parent) or parent not in by_key:
            return ("usage-invalid-parent",)
    # 先验证每个节点的 owner，避免同一损坏输入因边遍历顺序改变诊断。
    for row in records:
        references = (*row["children"], *row["fields"].values())
        for ref in references:
            if not _key(ref) or not row["key"][0] <= ref[0] <= ref[1] <= row["key"][1]:
                return ("usage-invalid-endpoint",)
            if complete and ref not in by_key:
                return ("usage-dangling-endpoint",)
            if ref in by_key and by_key[ref].get("parent") != row["key"]:
                return ("usage-conflicting-parent",)
    if any(row["key"] not in by_key[row["parent"]]["children"] for row in records[1:]):
        return ("usage-invalid-parent",)
    pending = [records[0]["key"]] if records else []
    seen = set()
    while pending:
        key = pending.pop()
        if key in seen or key not in by_key:
            continue
        seen.add(key)
        pending.extend(by_key[key]["children"])
    if len(seen) != len(records):
        return ("usage-disconnected-records",)
    order = {row["key"]: index for index, row in enumerate(records)}
    if any(order[row["parent"]] >= order[row["key"]] for row in records[1:]):
        return ("usage-invalid-order",)
    expected = bind(records)
    for row, bound in zip(records, expected):
        if row.get("binding") != bound.get("binding"):
            return ("usage-invalid-binding",)
        if complete and bound.get("binding", {}).get("reason") == "usage-binding-depth":
            return ("usage-inconsistent-completion",)
    return ()


def merge_usage(items, metadata):
    """同位置不同 producer 不任意挑选；配置冲突保留记录并关闭证明资格。"""
    result = dict(metadata)
    scoped = sorted((item for item in items if "usageScope" in item.metadata), key=lambda item: item.id)
    if not scoped:
        return result, False
    records = [item.metadata["usageScope"] for item in scoped]
    contexts = {item.metadata.get("compilationContextId") for item in scoped}
    conflict = len(contexts) > 1 or any(record != records[0] for record in records[1:])
    result["usageScope"] = records[0]
    if conflict:
        result["usageScope"] = {**records[0], "status": "partial",
            "reasonCodes": tuple(sorted(set(records[0]["reasonCodes"]) | {"usage-producer-conflict"}))}
    result["usageProvenance"] = tuple({"evidenceId": item.id, "producer": item.producer,
        "configuration": item.metadata.get("compilationContextId", "default")}
        for item in sorted(scoped, key=lambda value: value.id))
    return result, conflict
