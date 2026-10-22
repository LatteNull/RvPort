"""Bounded context scheduler for explicit roots and adopted direct calls."""

from collections import Counter, defaultdict
from copy import deepcopy
import time

from .contracts import AnalysisError, identity
from .effect_cache import DerivedCache, instance_key, scc_key, template_key
from .effect_summary import (
    compose, conservative_widen, finite, fixed_point, make_request, strongly_connected,
    summary_from_result, unknown,
)
from .effect_worker import evaluate_batch


def function_ref(key, function_id):
    return {"artifact_key": key, "function_id": None, "id": function_id}


class Scheduler:
    def __init__(self, inputs, local_facts, adoptions, worker, store, budgets, *, cache=None,
                 evaluator=evaluate_batch, clock=time.monotonic):
        self.inputs, self.local_facts, self.adoptions = inputs, local_facts, adoptions
        self.worker, self.store, self.budgets = worker, store, budgets
        self.cache, self.evaluator, self.clock = cache, evaluator, clock
        self.started, self.bytes = clock(), 0
        self.contexts, self.failures, self.cache_hits = {}, [], 0
        self.per_function = Counter()
        self.adoption_map = {(item["call"]["artifact_key"], item["call"]["id"]): item for item in adoptions}
        self.calls = {(key, call["id"]): call for key, module in inputs.modules.items() for call in module["calls"]}
        self.graph = self._call_graph()
        self.components = strongly_connected(self.graph)
        self.scc_group = {}
        for component in self.components:
            members = [f"{key}/{function}" for key, function in component]
            member_keys = [identity(local_facts[key]) for key, _ in component]
            group = scc_key(inputs.scope_id, members, member_keys, budgets)
            for node in component:
                self.scc_group[node] = group
        seeds = {node: {node} for node in self.graph}
        self.reachability, self.scc_converged, self.scc_turns = fixed_point(
            self.graph, seeds,
            lambda node, state: set().union(*(state[target] for target in self.graph[node]))
            if self.graph[node] else set(), budgets["scc_iterations"])

    def _call_graph(self):
        graph = {(key, function["id"]): set() for key, module in self.inputs.modules.items()
                 for function in module["functions"] if not function["declaration"]}
        for adoption in self.adoptions:
            if adoption["kind"] == "unknown":
                continue
            source = adoption["call"]["artifact_key"], adoption["call"]["function_id"]
            target = adoption["target"]["artifact_key"], adoption["target"]["id"]
            if source in graph and target in graph:
                graph[source].add(target)
        return graph

    def _check_total(self):
        if self.clock() - self.started > self.budgets["request_seconds"]:
            raise AnalysisError("request_timed_out", "Effect request wall-clock budget exceeded")
        if self.bytes > self.budgets["request_output_bytes"]:
            raise AnalysisError("request_output_limit", "Effect request output budget exceeded")
        if len(self.contexts) >= self.budgets["contexts_per_request"]:
            raise AnalysisError("context_budget", "Effect request context budget exceeded")

    def _cache_key(self, request):
        closure = sorted((key, identity(value)) for key, value in self.local_facts.items())
        return template_key(self.inputs.scope_id,
            {"artifact_key": request["function"]["artifact_key"], "function_id": request["function"]["id"],
             "arguments": request["arguments"]}, self.budgets, self.adoptions, closure)

    def analyze(self, function, domains, stack=()):
        request = make_request(self.inputs, function, domains, self.local_facts, self.budgets, self.adoptions)
        context = request["context_id"]
        if context in self.contexts:
            return deepcopy(self.contexts[context])
        self._check_total()
        pair = function["artifact_key"], function["id"]
        if self.per_function[pair] >= self.budgets["contexts_per_function"]:
            return self._budget_summary(request, function, "contexts_per_function_budget")
        key = self._cache_key(request)
        instance = instance_key(key, request["invocations"])
        if self.cache:
            template = self.cache.load("templates", key, "EffectSummary")
            cached = self.cache.load("instances", instance, "EffectSummary") if template is not None else None
            if cached is not None:
                self.cache_hits += 1; self.contexts[context] = cached
                return deepcopy(cached)
        self.per_function[pair] += 1
        entries = self.evaluator(self.inputs, [request], self.worker, self.store,
                                 local_facts=self.local_facts, summaries={})
        entry = next(iter(entries.values()))
        if entry["error"] is not None:
            self.failures.append({"context_id": context, **entry["error"]})
            summary = self._budget_summary(request, function, entry["error"]["code"])
        else:
            self.bytes += len(str(entry["result"]).encode())
            summary = summary_from_result(entry["result"])
            children, widenings = [], []
            for call in entry["result"]["call_requests"]:
                adoption = self.adoption_map.get((call["source"]["artifact_key"], call["source"]["id"]))
                if not adoption or adoption["kind"] == "unknown":
                    continue
                target = adoption["target"]
                child_function = function_ref(target["artifact_key"], target["id"])
                child_pair = target["artifact_key"], target["id"]
                if child_pair in stack or child_pair == pair:
                    widenings.append((call["source"], "recursive_budget"))
                    continue
                try:
                    child_domains = self._template_arguments(child_function, call["arguments"])
                    child = self.analyze(child_function, child_domains, (*stack, pair))
                    children.append((call, child))
                except AnalysisError as exc:
                    if exc.code not in {"context_budget", "request_timed_out", "request_output_limit"}:
                        raise
                    widenings.append((call["source"], exc.code))
            if children:
                bound = deepcopy(request)
                bound["dependencies"] = []
                bound["call_bindings"] = []
                summaries = {}
                for call, child in children:
                    dependency = {"context_id": child["context_id"], "digest": identity(child)}
                    if dependency not in bound["dependencies"]:
                        bound["dependencies"].append(dependency)
                    bound["call_bindings"].append({"source": deepcopy(call["source"]),
                                                   "context_id": child["context_id"]})
                    summaries[child["context_id"]] = child
                rebound = self.evaluator(self.inputs, [bound], self.worker, self.store,
                                          local_facts=self.local_facts, summaries=summaries)
                rebound_entry = next(iter(rebound.values()))
                if rebound_entry["error"] is not None:
                    self.failures.append({"context_id": context, **rebound_entry["error"]})
                    widenings.append((function, rebound_entry["error"]["code"]))
                else:
                    self.bytes += len(str(rebound_entry["result"]).encode())
                    summary = summary_from_result(rebound_entry["result"])
                for call, child in children:
                    summary = compose(summary, child, call["source"], call["arguments"])
            for source, code in widenings:
                summary = conservative_widen(summary, source, code)
        self.contexts[context] = summary
        if self.cache:
            self.cache.publish("templates", key, summary)
            self.cache.publish("instances", instance, summary)
        return deepcopy(summary)

    def _template_arguments(self, function, domains):
        key, fn = function["artifact_key"], function["id"]
        raw = next(item for item in self.inputs.modules[key]["functions"] if item["id"] == fn)
        values = {item["id"]: item for item in self.inputs.modules[key]["values"]}
        result = deepcopy(domains)
        for index, parameter_id in enumerate(raw.get("parameters", [])):
            if values[parameter_id]["type_kind"] != "pointer":
                continue
            result[index] = finite({"kind": "parameter", "source": {"artifact_key": key,
                "function_id": fn, "id": parameter_id}, "invocation_id": None})
        return result

    def _budget_summary(self, request, function, code):
        source = deepcopy(function)
        diagnostic = {"code": code, "detail": "Local context was not completed within its explicit budget",
                      "source": source, "context_id": request["context_id"]}
        root = {"artifact_key": function["artifact_key"], "function_id": function["id"],
                "arguments": [{"kind": "unknown", "reason": "not_evaluated"} for _ in request["arguments"]]}
        from .effect_contracts import effect_document
        return effect_document("EffectSummary", scope_id=request["scope_id"], context_id=request["context_id"],
            root=root, root_invocation_id=request["invocation_id"], invocations=request["invocations"],
            origins=request["origins"], budgets=request["budgets"], effects=[], order=[], returns=[], escape=[],
            adoptions=request["adoptions"], dependencies=[], local_dependencies=request["local_dependencies"],
            resolutions=[], diagnostics=[diagnostic], status="failed")


def select_roots(inputs, request):
    functions = {(key, item["id"]): item for key, module in inputs.modules.items()
                 for item in module["functions"]}
    if request["mode"] == "roots":
        roots = request["roots"]
    else:
        roots = [{"artifact_key": key, "function_id": item["id"], "arguments": []}
                 for (key, _), item in sorted(functions.items()) if not item["declaration"]]
    selected = []
    for root in roots:
        pair = root["artifact_key"], root["function_id"]
        if pair not in functions or functions[pair]["declaration"]:
            raise AnalysisError("invalid_root", f"Root is not a defined scope member: {pair}")
        parameters = functions[pair].get("parameters", [])
        if len(root["arguments"]) not in {0, len(parameters)}:
            raise AnalysisError("invalid_root", "Root argument count does not match function")
        domains = [finite(value) for value in root["arguments"]]
        if not domains:
            domains = [unknown("unbound_root_argument") for _ in parameters]
        selected.append((function_ref(*pair), domains))
    if not selected:
        raise AnalysisError("invalid_root", "Analysis request selected no defined functions")
    return selected


def run_scheduler(inputs, request, local_facts, adoptions, worker, store, *, cache_root=None,
                  evaluator=evaluate_batch):
    cache = DerivedCache(cache_root) if cache_root else None
    scheduler = Scheduler(inputs, local_facts, adoptions, worker, store, request["budgets"],
                          cache=cache, evaluator=evaluator)
    roots = []
    for function, domains in select_roots(inputs, request):
        try:
            roots.append(scheduler.analyze(function, domains))
        except AnalysisError as exc:
            scheduler.failures.append({"context_id": None, **exc.as_dict()})
    if not scheduler.scc_converged:
        for index, summary in enumerate(roots):
            source = function_ref(summary["root"]["artifact_key"], summary["root"]["function_id"])
            roots[index] = conservative_widen(summary, source, "scc_iteration_budget")
            scheduler.contexts[summary["context_id"]] = roots[index]
    return {"roots": roots, "contexts": scheduler.contexts, "failures": scheduler.failures,
            "cache_hits": scheduler.cache_hits,
            "scc": {"groups": len(scheduler.components), "iterations": scheduler.scc_turns,
                    "converged": scheduler.scc_converged}}
