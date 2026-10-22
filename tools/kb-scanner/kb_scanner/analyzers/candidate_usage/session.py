"""按配置与源码位置定位候选，缓存作用域索引并限制全扫描工作量。"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass

from .closure import QueryBudget, query
from .index import ScopeIndex


@dataclass(frozen=True)
class ScanBudget:
    records: int = 100000
    visits: int = 1000000

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in vars(self).values()):
            raise ValueError("usage scan budgets must be nonnegative integers")
        if self.records > 100000 or self.visits > 1000000:
            raise ValueError("usage scan budgets exceed hard limits")


class UsageSession:
    def __init__(self, facts, roots, scan_budget=None, query_budget=None):
        self.budget = scan_budget or ScanBudget()
        self.query_budget = query_budget or QueryBudget()
        self.evidence = {item.id: item for item in facts.evidence}
        self.indexes, self.cache = {}, {}
        self.record_ids, self.materialized_entities, self.materialized_relations = {}, {}, {}
        self.materialized_queries = {}
        self.record_count = self.visits = self.cache_hits = 0
        self.scopes, self.starts = defaultdict(list), {}
        demanded = {(root.subject_id, root.configuration) for root in roots}
        for fact in sorted(facts.facts, key=lambda item: item.id):
            configuration = fact.metadata.get("compilationContextId", "default")
            key = fact.subject_id, configuration
            if fact.kind != "usage_scope" or key not in demanded:
                continue
            sources = [self.evidence[eid] for eid in fact.evidence_ids if eid in self.evidence]
            if not sources or any(item.location is None for item in sources):
                continue
            span = sources[0].location
            if any(item.location != span or item.subject_id != fact.subject_id for item in sources):
                continue
            start = span.start.line, span.start.column
            end = span.end.line, span.end.column
            self.scopes[key].append((start, end, fact))
        for key, scopes in self.scopes.items():
            scopes.sort(key=lambda value: (value[0], value[1], value[2].id))
            self.starts[key] = [value[0] for value in scopes]

    def resolve(self, root):
        reasons, bindings, grouped = set(), [], defaultdict(list)
        if not root.configuration_complete:
            reasons.add("usage-configuration-unknown")
        lookup = root.subject_id, root.configuration
        for eid in root.matched_evidence_ids:
            evidence = self.evidence.get(eid)
            if (evidence is None or evidence.location is None or evidence.subject_id != root.subject_id
                    or evidence.kind not in {"enum_member_reference", "enum_member_declaration", "macro_expansion"}):
                reasons.add("usage-root-unresolved")
                continue
            point = evidence.location.start.line, evidence.location.start.column
            scopes = self.scopes.get(lookup, ())
            position = bisect_right(self.starts.get(lookup, ()), point)-1
            if position < 0 or not point < scopes[position][1]:
                reasons.add("usage-open-scope")
                continue
            start, end, fact = scopes[position]
            if (evidence.location.end.line, evidence.location.end.column) > end:
                reasons.add("usage-root-range-unknown")
                continue
            # 同一配置重叠 owner 不能随意选一份 producer 的结论。
            if position > 0 and scopes[position-1][1] > start:
                reasons.add("usage-scope-ambiguous")
                continue
            scope = fact.metadata.get("usageScope")
            if scope is None:
                reasons.add("usage-scope-unavailable")
                continue
            # 采集预算已耗尽时，闭包无法证明全使用穷尽；原始记录留在事实快照，
            # 不再为注定 unknown 的范围构造非执行图或消耗查询预算。
            if scope["status"] != "complete" and any("budget" in reason for reason in scope["reasonCodes"]):
                reasons.update(scope["reasonCodes"])
                reasons.add("usage-scope-incomplete")
                continue
            if fact.id not in self.indexes:
                count = scope["recordCount"]
                if self.record_count + count > self.budget.records:
                    reasons.add("usage-scan-record-budget")
                    continue
                self.record_count += count
                self.indexes[fact.id] = ScopeIndex(scope)
            index = self.indexes[fact.id]
            reasons.update(index.scope["reasonCodes"])
            if index.scope["status"] != "complete":
                reasons.add("usage-scope-incomplete")
            keys = index.roots_at((*point, evidence.location.end.line, evidence.location.end.column))
            name = str(evidence.value).rsplit("::", 1)[-1]
            keys = tuple(key for key in keys if index.rows[key]["text"] == name)
            if len(keys) != 1:
                reasons.add("usage-root-binding-unknown")
                continue
            bindings.append((eid, fact.id, keys[0]))
            grouped[fact.id].extend(keys)
        if not bindings or len(bindings) != len(root.matched_evidence_ids):
            reasons.add("usage-roots-incomplete")
        results = []
        for scope_id, keys in sorted(grouped.items()):
            cache_key = scope_id, tuple(sorted(set(keys)))
            if cache_key in self.cache:
                result = self.cache[cache_key]
                self.cache_hits += 1
            else:
                remaining = max(0, self.budget.visits-self.visits)
                result = query(self.indexes[scope_id], keys, QueryBudget(
                    self.query_budget.depth, min(remaining, self.query_budget.nodes), self.query_budget.edges))
                self.visits += result["visited"]
                if remaining < self.query_budget.nodes and result["truncated"]:
                    result = {**result, "reasonCodes": tuple(sorted(set(result["reasonCodes"]) | {"usage-scan-visit-budget"}))}
                self.cache[cache_key] = result
            reasons.update(result["reasonCodes"])
            results.append((scope_id, result))
        if (sum(result["visited"] for _, result in results) > self.query_budget.nodes
                or sum(result["edgeCount"] for _, result in results) > self.query_budget.edges):
            reasons.add("usage-query-budget")
        return {"status": "unknown" if reasons else "complete", "reasonCodes": tuple(sorted(reasons)),
                "bindings": tuple(sorted(bindings)), "queries": tuple(results)}
