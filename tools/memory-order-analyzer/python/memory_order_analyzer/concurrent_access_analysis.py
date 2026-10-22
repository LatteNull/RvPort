"""R2 access projection, execution binding, bounded pairing and protection."""

from collections import defaultdict
from copy import deepcopy
from itertools import combinations

from .contracts import canonical, identity
from .concurrent_access_contracts import concurrent_access_document, dependency, diagnostic


WRITE_KINDS = {"write", "rmw", "cas-success", "cas-failure"}
ADVANCED_KINDS = {"rmw", "cas-success", "cas-failure", "fence"}


def _dedupe(items, key="id"):
    values = {}
    for item in items:
        marker = item[key]
        if marker in values:
            prior = values[marker]
            for field in ("evidence", "guards", "proof"):
                if field in item or field in prior:
                    prior[field] = sorted(set(prior.get(field, ())) | set(item.get(field, ())))
        else:
            values[marker] = deepcopy(item)
    return [values[item] for item in sorted(values)]


def normalize_operation(effect):
    raw = str(effect.get("kind", "unknown")).lower().replace("_", "-")
    if raw in {"read", "load", "atomic-load"}:
        return "read"
    if raw in {"write", "store", "atomic-store", "memcpy", "memset"}:
        return "write"
    if raw in {"rmw", "atomic-rmw", "atomicrmw"}:
        return "rmw"
    if raw in {"cas", "cmpxchg", "cas-success"}:
        return "cas-success"
    if raw in {"cas-failure", "cmpxchg-failure"}:
        return "cas-failure"
    if raw == "fence":
        return "fence"
    return "unknown"


def _entry_key(value):
    if not isinstance(value, dict):
        return None
    artifact = value.get("artifact_key")
    function = value.get("function_id") or value.get("id")
    return canonical({"artifact_key": artifact, "function_id": function}) if artifact and function else None


def _demand_index(plan, root_overlay):
    contexts, functions, roots, tus = set(), set(), set(), set()
    for item in [*plan.get("demands", []), *root_overlay.get("demands", [])]:
        if item.get("context"):
            contexts.add(str(item["context"]))
        if item.get("context_id"):
            contexts.add(str(item["context_id"]))
        if item.get("root_id"):
            roots.add(str(item["root_id"]))
        entry = item.get("function") or item.get("entry")
        key = _entry_key(entry)
        if key:
            functions.add(key)
        if item.get("physical_tu_id"):
            tus.add(str(item["physical_tu_id"]))
    for item in plan.get("reachable_functions", []):
        key = _entry_key(item.get("entry"))
        if key:
            functions.add(key)
        if item.get("root_id"):
            roots.add(str(item["root_id"]))
    return {"contexts": contexts, "functions": functions, "roots": roots, "tus": tus}


def _summary_demand(summary, demand):
    root_key = _entry_key(summary.get("root"))
    context = str(summary.get("context_id"))
    return context in demand["contexts"] or (root_key is not None and root_key in demand["functions"])


def _domain_index(provenance_graph):
    if not provenance_graph:
        return {}
    return {str(item["id"]): deepcopy(item["domain"]) for item in provenance_graph.get("domains", [])}


def _effect_domain(effect, domains):
    keys = [effect.get("object_domain_id"), effect.get("object_key"), effect.get("address_ref")]
    address = effect.get("address")
    if isinstance(address, dict):
        keys.extend((address.get("domain_id"), address.get("id"),
                     (address.get("source") or {}).get("id") if isinstance(address.get("source"), dict) else None))
    for key in keys:
        if key is not None and str(key) in domains:
            return deepcopy(domains[str(key)]), str(key)
    return {"state": "unknown", "candidates": [], "reason": "object-provenance-missing"}, None


def _byte_range(effect):
    offset = effect.get("offset_bytes")
    size = effect.get("size_bytes")
    try:
        offset = int(offset) if offset is not None else None
        size = int(size) if size is not None else None
    except (TypeError, ValueError):
        offset = size = None
    if offset is None:
        address = effect.get("address")
        if isinstance(address, dict):
            raw = address.get("byte_range", {})
            offset, size = raw.get("offset"), raw.get("size", size)
    return {"offset": offset, "size": size}


def _instance_for_summary(summary, demand, execution):
    context = str(summary.get("context_id"))
    candidates = [item for item in execution.get("instances", [])
                  if str(item.get("context_id")) == context]
    if len(candidates) == 1:
        return candidates[0]["id"]
    root_key = _entry_key(summary.get("root"))
    root_ids = {item.get("root_id") for item in demand.get("items", [])
                if _entry_key(item.get("function") or item.get("entry")) == root_key}
    candidates = [item for item in execution.get("instances", []) if item.get("root_id") in root_ids]
    return candidates[0]["id"] if len(candidates) == 1 else None


def _model_family(value):
    value = str(value or "").lower()
    for family in ("pthread", "thrd", "std-thread", "std-jthread", "std-async"):
        if family in value:
            return family
    return value


def _creation_tokens(value):
    if isinstance(value, dict):
        return {str(item) for key in ("id", "callsite_id", "source_site_id", "creation_site_id")
                if (item := value.get(key)) is not None}
    return {str(value)} if value is not None else set()


def build_execution_overlay(request, plan, root_overlay, *, root_indexes=(), thread_graphs=(),
                            lifecycle_graphs=()):
    budgets = request["budgets"]
    frontier = [deepcopy(item) for item in [*plan.get("frontier", []), *root_overlay.get("frontier", [])]]
    roots, contexts, instances, invocations, mhp, exclusions = {}, {}, {}, {}, [], []
    root_keys = {}

    if not request["closed_scope"]:
        frontier.append(diagnostic("open-scope", "R2 分析 scope 未闭合",
                                   "The R2 analysis scope is open"))

    def add_root(item, source_kind):
        root_id = str(item["id"])
        value = {
            "id": root_id, "kind": item.get("kind", "unknown"), "entry": deepcopy(item.get("entry")),
            "creation_site_id": item.get("creation_site_id"), "source_site_id": item.get("source_site_id"),
            "context_id": item.get("thread_context_key") or item.get("context_id"),
            "instance_id": item.get("thread_instance_key"), "cardinality": item.get("cardinality", "single"),
            "guard": deepcopy(item.get("guard")), "source_kind": source_kind,
            "adopted_from": [root_id],
        }
        binding_key = None
        if value["creation_site_id"] is not None:
            binding_key = canonical({"site": value["creation_site_id"], "model": value["kind"],
                                     "callback": value["entry"]})
        if binding_key is not None and binding_key in root_keys and root_keys[binding_key] != root_id:
            previous = roots[root_keys[binding_key]]
            comparable = ("kind", "entry", "creation_site_id", "source_site_id", "context_id",
                          "instance_id", "cardinality", "guard")
            if all(previous.get(field) == value.get(field) for field in comparable):
                previous["adopted_from"] = sorted(set(previous["adopted_from"] + [root_id]))
            else:
                frontier.append(diagnostic(
                    "root-binding-conflict", "同一物理创建点、模型和 callback 存在冲突绑定",
                    "One physical creation site, model, and callback has conflicting bindings",
                    source={"root_ids": sorted((previous["id"], root_id))}))
            return
        if root_id in roots and canonical(roots[root_id]) != canonical(value):
            frontier.append(diagnostic("root-binding-conflict", "同一执行根存在冲突绑定",
                                       "One execution root has conflicting bindings", source={"root_id": root_id}))
        else:
            roots[root_id] = value
            if binding_key is not None:
                root_keys[binding_key] = root_id

    for graph in root_indexes:
        frontier.extend(deepcopy(graph.get("frontier", [])))
        for item in graph.get("roots", []):
            if item.get("status") == "complete":
                add_root(item, "ExecutionRootIndex")
            else:
                frontier.append(diagnostic("root-evidence-incomplete", "执行根证据不完整",
                                           "Execution-root evidence is incomplete", source={"root_id": item.get("id")}))
    for item in root_overlay.get("roots", []):
        add_root(item, "ThreadEntryRootOverlay")
    for item in [*plan.get("contexts", []), *root_overlay.get("contexts", [])]:
        contexts[str(item["id"])] = deepcopy(item)

    p3_id_maps = []
    for graph_index, graph in enumerate(thread_graphs):
        graph_map = {}
        for item in graph.get("contexts", []):
            contexts.setdefault(str(item["id"]), deepcopy(item))
        for item in graph.get("instances", []):
            semantic = item.get("semantic_key") or identity({
                "model": graph.get("model_id", "pthread"), "context": item.get("context_id"),
                "parent": item.get("parent_id"), "create": item.get("create"),
                "cardinality": item.get("cardinality", "single"),
            })
            instance_id = str(semantic)
            graph_map[str(item["id"])] = instance_id
            value = {
                "id": instance_id, "observed_ids": sorted(set([str(item["id"]),
                    *instances.get(instance_id, {}).get("observed_ids", [])])),
                "root_id": item.get("root_id"), "context_id": item.get("context_id"),
                "parent_id": item.get("parent_id"), "creation": deepcopy(item.get("create")),
                "model": graph.get("model_id", "posix-pthread-v1"),
                "cardinality": item.get("cardinality", "single"), "guard": deepcopy(item.get("guard")),
                "status": "partial" if item.get("cardinality") == "unknown" else "complete",
                "evidence": sorted(set(item.get("evidence", []))),
            }
            instances[instance_id] = value
        p3_id_maps.append(graph_map)
        for invocation in graph.get("invocations", []):
            invocations[str(invocation["id"])] = deepcopy(invocation)
        for relation in graph.get("mhp", []):
            left = graph_map.get(str(relation.get("left")), str(relation.get("left")))
            right = graph_map.get(str(relation.get("right")), str(relation.get("right")))
            raw = relation.get("relation")
            disposition = ("parallel-possible" if raw in {"may_parallel", "may-parallel"} else
                           "not-parallel" if raw in {"not_parallel", "not-parallel"} else "unknown")
            pair = sorted((left, right))
            mhp.append({"id": identity({"instances": pair, "disposition": disposition}),
                        "left": pair[0], "right": pair[1], "disposition": disposition,
                        "guards": sorted(relation.get("guards", [])),
                        "proof": sorted(set([str(relation.get("id")),
                            *(str(item) for item in relation.get("proof", []))])),
                        "reason": relation.get("reason")})
        frontier.extend(deepcopy(graph.get("frontier", [])))

    program_instances = [item for item in instances.values() if item.get("parent_id") is None]
    for graph in lifecycle_graphs:
        lifecycle_map = {}
        for item in graph.get("contexts", []):
            contexts.setdefault(str(item["id"]), deepcopy(item))
        for item in graph.get("instances", []):
            instance_id = str(item.get("semantic_key") or item["id"])
            lifecycle_map[str(item["id"])] = instance_id
            instances.setdefault(instance_id, {
                "id": instance_id, "observed_ids": [str(item["id"])], "root_id": item.get("root_id"),
                "context_id": item.get("context_id"), "parent_id": item.get("parent_id"),
                "creation": item.get("construct_operation_id"), "model": "std-thread-lifecycle-v1",
                "cardinality": item.get("cardinality", "single"), "guard": deepcopy(item.get("guard")),
                "status": item.get("status", "complete"), "evidence": sorted(item.get("evidence", [])),
            })
        for relation in graph.get("relations", []):
            raw = relation.get("relation")
            if raw not in {"may-parallel", "may_parallel", "not-parallel", "not_parallel"}:
                continue
            left, right = relation.get("from"), relation.get("to")
            left = lifecycle_map.get(str(left), str(left))
            right = lifecycle_map.get(str(right), str(right))
            if left == "root" or right == "root":
                if len(program_instances) != 1:
                    frontier.append(diagnostic("lifecycle-root-ambiguous",
                        "C++ 生命周期中的抽象 root 无法唯一绑定执行实例",
                        "The abstract root in a C++ lifecycle cannot be bound to one execution instance",
                        source={"relation_id": relation.get("id")}))
                    continue
                replacement = program_instances[0]["id"]
                left = replacement if left == "root" else left
                right = replacement if right == "root" else right
            disposition = "parallel-possible" if raw in {"may-parallel", "may_parallel"} else "not-parallel"
            pair = sorted((left, right))
            mhp.append({"id": identity({"instances": pair, "disposition": disposition}),
                        "left": pair[0], "right": pair[1], "disposition": disposition,
                        "guards": [relation["guard"]] if relation.get("guard") else [],
                        "proof": sorted(set([str(relation.get("id")),
                                            *(str(item) for item in relation.get("evidence", []))])),
                        "reason": "cpp-lifecycle"})
        frontier.extend(deepcopy(graph.get("frontier", [])))

    # Align a discovered entry root with an already proven lifecycle instance only when its
    # execution context is unique.  ExecutionRoot and ThreadInstance remain distinct identities;
    # this merely records their exact binding and avoids inventing a second dynamic instance.
    represented_roots = {item.get("root_id") for item in instances.values() if item.get("root_id")}
    for root in roots.values():
        if root["id"] in represented_roots:
            continue
        context_matches = [item for item in instances.values()
                           if root.get("context_id") is not None and
                           item.get("context_id") == root.get("context_id") and
                           _model_family(item.get("model")) == _model_family(root.get("kind"))]
        root_creation = _creation_tokens(root.get("creation_site_id")) | \
            _creation_tokens(root.get("source_site_id"))
        exact_creation = [item for item in context_matches
                          if root_creation & _creation_tokens(item.get("creation"))]
        if root_creation:
            context_matches = exact_creation
        if len(context_matches) == 1:
            root["instance_id"] = context_matches[0]["id"]
            continue
        if len(context_matches) > 1:
            frontier.append(diagnostic(
                "root-instance-binding-ambiguous",
                "线程入口无法唯一绑定动态执行实例",
                "The thread entry cannot be bound to one dynamic execution instance",
                source={"root_id": root["id"],
                        "instance_ids": sorted(item["id"] for item in context_matches)}))
            continue
        # Roots not represented by P3/A3 still remain explicit instances. They are not guessed away.
        instance_id = root.get("instance_id") or identity({"root": root["id"], "site": root.get("creation_site_id")})
        instances[instance_id] = {
            "id": instance_id, "observed_ids": [], "root_id": root["id"],
            "context_id": root.get("context_id"), "parent_id": None,
            "creation": root.get("creation_site_id"), "model": root.get("kind", "execution-root"),
            "cardinality": root.get("cardinality", "single"), "guard": root.get("guard"),
            "status": "complete", "evidence": [root["id"]],
        }
        root["instance_id"] = instance_id

    # An adopted exact creation root proves a bounded may-parallel interval with its
    # unique explicit parent root.  Multiple possible parents remain unknown.
    base_instances = [root.get("instance_id") for root in roots.values()
                      if root.get("source_kind") == "ExecutionRootIndex" and
                      root.get("creation_site_id") is None and root.get("instance_id") in instances]
    base_instances = sorted(set(base_instances))
    if len(base_instances) == 1:
        parent_id = base_instances[0]
        for root in roots.values():
            child_id = root.get("instance_id")
            if root.get("source_kind") != "ThreadEntryRootOverlay" or child_id not in instances or \
                    child_id == parent_id or root.get("creation_site_id") is None:
                continue
            if _model_family(root.get("kind")) not in {
                    "pthread", "thrd", "std-thread", "std-jthread", "std-async"}:
                continue
            child = instances[child_id]
            child["parent_id"] = child.get("parent_id") or parent_id
            pair = sorted((parent_id, child_id))
            if any([item["left"], item["right"]] == pair and
                   item["disposition"] == "parallel-possible" for item in mhp):
                continue
            mhp.append({"id": identity({"instances": pair, "disposition": "parallel-possible",
                                        "site": root["creation_site_id"]}),
                        "left": pair[0], "right": pair[1], "disposition": "parallel-possible",
                        "guards": [root["guard"]] if root.get("guard") else [],
                        "proof": sorted(set(root.get("adopted_from", []) +
                                            [str(root["creation_site_id"])])),
                        "reason": "exact-thread-entry-creation"})

    # A merged/repeated bucket can represent two dynamic instances and therefore has self-MHP.
    for item in instances.values():
        if item.get("cardinality") in {"merged", "repeated"}:
            mhp.append({"id": identity({"self": item["id"], "disposition": "parallel-possible"}),
                        "left": item["id"], "right": item["id"],
                        "disposition": "parallel-possible", "guards": [],
                        "proof": item.get("evidence", []), "reason": "repeated-dynamic-instances"})

    known_mhp = {(item["left"], item["right"]) for item in mhp}
    instance_values = sorted(instances.values(), key=lambda item: item["id"])
    query_hit = 0
    for left, right in combinations(instance_values, 2):
        if query_hit >= budgets["mhp_queries"]:
            frontier.append(diagnostic("mhp-query-budget-exhausted", "MHP 查询预算已耗尽",
                                       "The MHP query budget is exhausted",
                                       source={"hit": query_hit, "limit": budgets["mhp_queries"]}))
            break
        query_hit += 1
        pair = (left["id"], right["id"])
        if pair in known_mhp:
            continue
        mhp.append({"id": identity({"instances": pair, "disposition": "unknown"}),
                    "left": pair[0], "right": pair[1], "disposition": "unknown",
                    "guards": [], "proof": [], "reason": "cross-root-lifecycle-not-proven"})
        frontier.append(diagnostic("mhp-unknown", "执行实例之间的可能并行关系未知",
                                   "Possible parallelism between execution instances is unknown",
                                   source={"left": pair[0], "right": pair[1]}))

    roots_values = sorted(roots.values(), key=lambda item: item["id"])
    contexts_values = sorted(contexts.values(), key=lambda item: item["id"])
    if len(roots_values) > budgets["roots"]:
        roots_values = roots_values[:budgets["roots"]]
        frontier.append(diagnostic("roots-budget-exhausted", "执行根预算已耗尽", "The execution-root budget is exhausted"))
    if len(contexts_values) > budgets["contexts"]:
        contexts_values = contexts_values[:budgets["contexts"]]
        frontier.append(diagnostic("contexts-budget-exhausted", "执行上下文预算已耗尽", "The execution-context budget is exhausted"))
    if len(instance_values) > budgets["instances"]:
        instance_values = instance_values[:budgets["instances"]]
        frontier.append(diagnostic("instances-budget-exhausted", "执行实例预算已耗尽", "The execution-instance budget is exhausted"))
    valid_instances = {item["id"] for item in instance_values}
    mhp = [item for item in _dedupe(mhp) if item["left"] in valid_instances and item["right"] in valid_instances]
    status = "partial" if frontier or plan.get("status") != "complete" or \
        root_overlay.get("status") != "complete" else "complete"
    dependencies = [dependency("RootDrivenAnalysisPlan", plan["scope_id"], plan),
                    dependency("ThreadEntryRootOverlay", root_overlay["scope_id"], root_overlay)]
    dependencies.extend(dependency(item["kind"], item.get("scope_id", item["semantic_digest"]), item)
                        for item in [*root_indexes, *thread_graphs, *lifecycle_graphs])
    dependencies = sorted({(item["kind"], item["id"]): item for item in dependencies}.values(),
                          key=lambda item: (item["kind"], item["id"]))
    return concurrent_access_document(
        "ExecutionInstanceBindingOverlay", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=status,
        roots=roots_values, contexts=contexts_values, instances=instance_values,
        invocations=sorted(invocations.values(), key=lambda item: item["id"]), mhp=mhp,
        exclusions=sorted(exclusions, key=lambda item: item["id"]),
        counts={"roots": len(roots_values), "contexts": len(contexts_values),
                "instances": len(instance_values), "invocations": len(invocations),
                "mhp": len(mhp), "mhp_queries": query_hit},
        dependencies=dependencies, diagnostics=frontier[:budgets["frontier_items"]],
        frontier=frontier[:budgets["frontier_items"]], semantic_digest=None)


def build_projection(request, plan, root_overlay, summaries, execution, *, thread_graphs=(),
                     provenance_graph=None):
    budgets = request["budgets"]
    demand = _demand_index(plan, root_overlay)
    demand["items"] = [*plan.get("demands", []), *root_overlay.get("demands", [])]
    domains = _domain_index(provenance_graph)
    accesses, observed, frontier = [], [], []
    for member in request["members"]:
        if member["bc_digest"] is None:
            frontier.append(diagnostic("ast-only-access-evidence",
                                       "AST-only TU 缺少运行时 alias 与访问事件证据",
                                       "An AST-only TU lacks runtime alias and access-event evidence",
                                       source={"physical_tu_id": member["physical_tu_id"]}))
        elif member["source_digest"] is None:
            frontier.append(diagnostic("ir-only-source-evidence",
                                       "IR-only TU 缺少源码线程入口与控制证据",
                                       "An IR-only TU lacks source thread-entry and control evidence",
                                       source={"physical_tu_id": member["physical_tu_id"]}))
    for summary in summaries:
        if summary.get("status") != "complete":
            frontier.extend(deepcopy(summary.get("frontier", [])) or [diagnostic(
                "effect-summary-incomplete", "demanded EffectSummary 不完整",
                "A demanded EffectSummary is incomplete",
                source={"context_id": summary.get("context_id")})])
    if provenance_graph and provenance_graph.get("status") != "complete":
        frontier.extend(deepcopy(provenance_graph.get("frontier", [])) or [diagnostic(
            "object-provenance-incomplete", "对象 provenance 图不完整",
            "The object-provenance graph is incomplete")])
    instance_context = {item["id"]: item.get("context_id") for item in execution.get("instances", [])}
    instance_root = {item["id"]: item.get("root_id") for item in execution.get("instances", [])}
    observed_instances = {observed: item["id"] for item in execution.get("instances", [])
                          for observed in item.get("observed_ids", [])}

    raw_effects = []
    for graph in thread_graphs:
        for effect in graph.get("effects", []):
            effect = deepcopy(effect)
            original_instance = effect.get("thread_instance_id")
            effect["thread_instance_id"] = observed_instances.get(str(original_instance), original_instance)
            effect["_context_id"] = instance_context.get(effect.get("thread_instance_id"))
            effect["_origin"] = "ThreadContextGraph"
            raw_effects.append(effect)
    for summary in summaries:
        for effect in summary.get("effects", []):
            matching_instances = [item["id"] for item in execution.get("instances", [])
                                  if str(item.get("context_id")) == str(summary.get("context_id"))]
            for target_instance in matching_instances or [None]:
                instance_effect = deepcopy(effect)
                instance_effect["_context_id"] = summary.get("context_id")
                instance_effect["thread_instance_id"] = target_instance
                instance_effect["_summary"] = summary
                instance_effect["_origin"] = "EffectSummary"
                raw_effects.append(instance_effect)
    raw_effects.sort(key=lambda item: (str(item.get("_context_id")),
                                       str(item.get("thread_instance_id")), str(item.get("id"))))
    if len(raw_effects) > budgets["effects"]:
        raw_effects = raw_effects[:budgets["effects"]]
        frontier.append(diagnostic("effects-budget-exhausted", "effect 预算已耗尽",
                                   "The effect budget is exhausted",
                                   source={"limit": budgets["effects"]}))

    seen = {}
    demanded_effects = 0
    for effect in raw_effects:
        summary = effect.get("_summary")
        demanded = ((effect.get("_context_id") and str(effect["_context_id"]) in demand["contexts"]) or
                    (summary is not None and _summary_demand(summary, demand)))
        if not demanded:
            observed.append({"id": identity({"origin": effect["_origin"], "effect": effect.get("id")}),
                             "origin": effect["_origin"], "effect_id": str(effect.get("id")),
                             "reason": "observed-but-not-demanded"})
            continue
        demanded_effects += 1
        operation = normalize_operation(effect)
        if operation == "fence":
            frontier.append(diagnostic("advanced-atomic-semantics-unsupported",
                                       "fence 需要 A6 高级原子语义",
                                       "A fence requires A6 advanced atomic semantics",
                                       source={"effect_id": effect.get("id")}))
            continue
        domain, domain_id = _effect_domain(effect, domains)
        if domain["state"] == "unknown":
            frontier.append(diagnostic("object-domain-unknown", "访问对象 provenance 未知",
                                       "Access-object provenance is unknown",
                                       source={"effect_id": effect.get("id"), "reason": domain.get("reason")}))
        instance_id = effect.get("thread_instance_id")
        if instance_id is None and summary is not None:
            instance_id = _instance_for_summary(summary, demand, execution)
        if instance_id is None:
            frontier.append(diagnostic("execution-instance-unknown", "访问无法唯一绑定执行实例",
                                       "The access cannot be bound to one execution instance",
                                       source={"effect_id": effect.get("id")}))
        access_range = _byte_range(effect)
        seed = {"source": effect.get("source"), "context": effect.get("_context_id"),
                "invocation": effect.get("invocation_id"), "instance": instance_id,
                "operation": operation, "atomic": bool(effect.get("atomic")),
                "guards": sorted(set(str(item) for item in effect.get("guards", []))),
                "cardinality": effect.get("multiplicity", "single")}
        observation_id = identity(seed)
        evidence = [str(effect.get("id"))]
        evidence.extend(str(item) for item in effect.get("proof", []))
        source_access_ids = sorted(set(str(item) for item in effect.get("protection_access_ids", [])))
        value = {
            "id": observation_id, "origin": effect["_origin"], "effect_id": str(effect.get("id")),
            "effect_ids": [str(effect.get("id"))],
            "source": deepcopy(effect.get("source")), "context_id": effect.get("_context_id"),
            "invocation_id": effect.get("invocation_id"), "execution_instance_id": instance_id,
            "operation": operation, "atomic": bool(effect.get("atomic")),
            "volatile": bool(effect.get("volatile")), "ordering": effect.get("ordering"),
            "failure_ordering": effect.get("failure_ordering"), "guards": sorted(set(
                str(item) for item in effect.get("guards", []))),
            "object_domain_id": domain_id, "object_domain": domain,
            "byte_range": access_range, "cardinality": effect.get("multiplicity", "single"),
            "source_access_ids": source_access_ids, "evidence": sorted(set(evidence)),
        }
        if observation_id in seen:
            prior = seen[observation_id]
            opposed = False
            if prior["object_domain"]["state"] == "unknown" and domain["state"] != "unknown":
                prior["object_domain"], prior["object_domain_id"] = domain, domain_id
            elif domain["state"] != "unknown" and prior["object_domain"]["state"] != "unknown" and \
                    canonical(prior["object_domain"]) != canonical(domain):
                opposed = True
            for field in ("offset", "size"):
                if prior["byte_range"].get(field) is None:
                    prior["byte_range"][field] = access_range.get(field)
                elif access_range.get(field) is not None and \
                        prior["byte_range"][field] != access_range[field]:
                    opposed = True
            if opposed:
                conflict_id = identity({"observation": observation_id, "origin": effect["_origin"],
                                        "domain": domain, "range": access_range})
                seen[conflict_id] = value
                frontier.append(diagnostic(
                    "source-ir-access-conflict", "同一动态访问的 source/IR 对象或范围证据冲突",
                    "Source/IR object or range evidence conflicts for one dynamic access",
                    source={"effect_id": effect.get("id")}))
                continue
            prior["evidence"] = sorted(set(prior["evidence"]) | set(value["evidence"]))
            prior["source_access_ids"] = sorted(set(prior["source_access_ids"]) | set(source_access_ids))
            prior["effect_ids"] = sorted(set(prior["effect_ids"]) | set(value["effect_ids"]))
        else:
            seen[observation_id] = value
    accesses = []
    for value in seen.values():
        value["id"] = identity({
            "scope": request["scope_id"],
            "profiles": sorted({item["profile_id"] for item in request["members"]}),
            "root": instance_root.get(value["execution_instance_id"]),
            "context": value["context_id"], "invocation": value["invocation_id"],
            "source": value["source"], "instance": value["execution_instance_id"],
            "operation": value["operation"], "atomic": value["atomic"],
            "guards": value["guards"], "object_domain": value["object_domain"],
            "byte_range": value["byte_range"], "cardinality": value["cardinality"],
        })
        accesses.append(value)
    accesses.sort(key=lambda item: item["id"])
    if demand["functions"] and demanded_effects == 0:
        frontier.append(diagnostic("demanded-effect-missing", "可达 demand 没有可用内存 effect",
                                   "A reachable demand has no usable memory effect"))
    if len(accesses) > budgets["accesses"]:
        accesses = accesses[:budgets["accesses"]]
        frontier.append(diagnostic("accesses-budget-exhausted", "访问实例预算已耗尽",
                                   "The access-instance budget is exhausted",
                                   source={"limit": budgets["accesses"]}))
    status = "partial" if frontier or execution.get("status") != "complete" or \
        plan.get("status") != "complete" or root_overlay.get("status") != "complete" else "complete"
    dependencies = [dependency("RootDrivenAnalysisPlan", plan["scope_id"], plan),
                    dependency("ThreadEntryRootOverlay", root_overlay["scope_id"], root_overlay)]
    dependencies.extend(dependency("EffectSummary", item["context_id"], item) for item in summaries)
    dependencies.extend(dependency("ThreadContextGraph", item["scope_id"], item) for item in thread_graphs)
    if provenance_graph:
        dependencies.append(dependency("BoundedObjectProvenanceGraph", provenance_graph["scope_id"], provenance_graph))
    dependencies = sorted({(item["kind"], item["id"]): item for item in dependencies}.values(),
                          key=lambda item: (item["kind"], item["id"]))
    return concurrent_access_document(
        "ConcurrentAccessProjectionFacts", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=status,
        accesses=accesses, observed_not_demanded=sorted(observed, key=lambda item: item["id"]),
        counts={"effects": len(raw_effects), "demanded_effects": demanded_effects,
                "planned_effects": max(demanded_effects, len(demand["functions"])),
                "accesses": len(accesses),
                "observed_not_demanded": len(observed),
                "unknown_objects": sum(item["object_domain"]["state"] == "unknown" for item in accesses),
                "unknown_instances": sum(item["execution_instance_id"] is None for item in accesses)},
        dependencies=dependencies, diagnostics=frontier[:budgets["frontier_items"]],
        frontier=frontier[:budgets["frontier_items"]], semantic_digest=None)


def object_overlap(left, right):
    left_domain, right_domain = left["object_domain"], right["object_domain"]
    if left_domain.get("state") == "unknown" or right_domain.get("state") == "unknown":
        return "unknown", []
    left_candidates = left_domain.get("candidates", [])
    right_candidates = right_domain.get("candidates", [])
    if not left_candidates or not right_candidates:
        return "unknown", []
    relations, evidence = [], []
    for first in left_candidates:
        for second in right_candidates:
            a, b = first.get("object", {}), second.get("object", {})
            evidence.extend([a.get("id"), b.get("id")])
            a_storage, b_storage = a.get("storage", {}), b.get("storage", {})
            if not a_storage or not b_storage or "unknown" in {a_storage.get("kind"), b_storage.get("kind")}:
                relations.append("unknown"); continue
            if a_storage.get("id") != b_storage.get("id"):
                relations.append("disjoint"); continue
            a_range = a.get("byte_range", left.get("byte_range", {}))
            b_range = b.get("byte_range", right.get("byte_range", {}))
            union_a = {item.get("union_group") for item in a.get("path", []) if item.get("union_group")}
            union_b = {item.get("union_group") for item in b.get("path", []) if item.get("union_group")}
            if union_a & union_b:
                relations.append("overlap"); continue
            ao, az = a_range.get("offset"), a_range.get("size")
            bo, bz = b_range.get("offset"), b_range.get("size")
            if None in {ao, az, bo, bz}:
                relations.append("unknown")
            elif ao < bo + bz and bo < ao + az:
                relations.append("overlap")
            else:
                relations.append("disjoint")
    evidence = sorted({item for item in evidence if item})
    if relations and all(item == "disjoint" for item in relations):
        return "must-disjoint", evidence
    if "overlap" in relations:
        exact = (left_domain.get("state") == right_domain.get("state") == "must" and
                 len(relations) == 1)
        return ("must-overlap" if exact else "may-overlap"), evidence
    return "unknown", evidence


def _bucket_keys(access):
    domain = access["object_domain"]
    if domain.get("state") == "unknown":
        return []
    keys = []
    for candidate in domain.get("candidates", []):
        obj = candidate.get("object", {})
        storage = obj.get("storage", {})
        if not storage.get("id") or storage.get("kind") == "unknown":
            continue
        keys.append(canonical({"storage": storage["id"],
                               "address_space": obj.get("address_space",
                                                        storage.get("address_space", 0))}))
    return sorted(set(keys))


def pair_accesses(request, projection, execution):
    budgets = request["budgets"]
    accesses = {item["id"]: item for item in projection["accesses"]}
    instances = {item["id"]: item for item in execution["instances"]}
    mhp = {(item["left"], item["right"]): item for item in execution["mhp"]}
    buckets = defaultdict(list)
    frontier, candidates, exclusions = [], {}, {}
    bucket_hit = object_hit = 0
    for access in accesses.values():
        keys = _bucket_keys(access)
        if not keys:
            frontier.append(diagnostic("object-bucket-unknown", "未知对象访问无法进入有限配对桶",
                                       "An unknown-object access cannot enter a finite pairing bucket",
                                       source={"access_id": access["id"], "context_id": access.get("context_id")}))
            continue
        for key in keys:
            object_hit += 1
            if object_hit > budgets["object_candidates"]:
                frontier.append(diagnostic("object-candidate-budget-exhausted", "对象候选预算已耗尽",
                                           "The object-candidate budget is exhausted"))
                break
            buckets[key].append(access["id"])
    bucket_items = sorted(buckets.items())
    if len(bucket_items) > budgets["buckets"]:
        bucket_items = bucket_items[:budgets["buckets"]]
        frontier.append(diagnostic("buckets-budget-exhausted", "配对桶预算已耗尽",
                                   "The pairing-bucket budget is exhausted"))

    comparisons = mhp_queries = 0
    pair_markers = set()
    for bucket, ids in bucket_items:
        bucket_hit += 1
        ordered = sorted(set(ids))
        pairs = list(combinations(ordered, 2))
        for access_id in ordered:
            instance = instances.get(accesses[access_id].get("execution_instance_id"))
            if instance and instance.get("cardinality") in {"merged", "repeated"}:
                pairs.append((access_id, access_id))
        for left_id, right_id in pairs:
            marker = tuple(sorted((left_id, right_id)))
            if marker in pair_markers:
                continue
            pair_markers.add(marker)
            if comparisons >= budgets["alias_comparisons"]:
                frontier.append(diagnostic("alias-comparison-budget-exhausted", "别名比较预算已耗尽",
                                           "The alias-comparison budget is exhausted"))
                break
            comparisons += 1
            left, right = accesses[left_id], accesses[right_id]
            left_instance, right_instance = left.get("execution_instance_id"), right.get("execution_instance_id")
            if not left_instance or not right_instance:
                frontier.append(diagnostic("execution-instance-unknown", "访问对缺少执行实例",
                                           "An access pair lacks execution instances",
                                           source={"left": left_id, "right": right_id}))
                continue
            if left_instance == right_instance and instances[left_instance].get("cardinality") == "single":
                reason, relation = "same-single-instance", None
            else:
                mhp_queries += 1
                if mhp_queries > budgets["mhp_queries"]:
                    frontier.append(diagnostic("mhp-query-budget-exhausted", "MHP 查询预算已耗尽",
                                               "The MHP query budget is exhausted"))
                    break
                key = tuple(sorted((left_instance, right_instance)))
                relation = mhp.get(key)
                if relation is None or relation["disposition"] == "unknown":
                    frontier.append(diagnostic("mhp-unknown", "访问对的 MHP 关系未知",
                                               "The access pair has an unknown MHP relation",
                                               source={"left": left_id, "right": right_id}))
                    continue
                reason = "proven-not-parallel" if relation["disposition"] == "not-parallel" else None
            overlap, overlap_evidence = object_overlap(left, right)
            if overlap == "unknown":
                frontier.append(diagnostic("object-overlap-unknown", "访问对的对象重叠关系未知",
                                           "The access pair has an unknown object-overlap relation",
                                           source={"left": left_id, "right": right_id}))
                continue
            if reason is None and overlap == "must-disjoint":
                reason = "must-disjoint"
            if reason is None and left["operation"] == right["operation"] == "read":
                reason = "read-read"
            pair_id = identity({"left": marker[0], "right": marker[1]})
            provenance_guards = {
                str(guard) for access in (left, right)
                for candidate in access.get("object_domain", {}).get("candidates", [])
                for guard in candidate.get("guards", [])
            }
            base = {"id": pair_id, "left": marker[0], "right": marker[1],
                    "execution_instances": sorted((left_instance, right_instance)),
                    "overlap": overlap, "overlap_evidence": overlap_evidence,
                    "guards": sorted(set(left.get("guards", ())) | set(right.get("guards", ())) |
                                     provenance_guards),
                    "atomic": bool(left.get("atomic") or right.get("atomic")),
                    "protection": "unprotected", "evidence": sorted(set(
                        left.get("evidence", ())) | set(right.get("evidence", ())) |
                        set((relation or {}).get("proof", ()))), "bucket": bucket}
            if reason is not None:
                if len(exclusions) >= budgets["exclusions"]:
                    frontier.append(diagnostic("exclusions-budget-exhausted", "排除项预算已耗尽",
                                               "The exclusion budget is exhausted"))
                    continue
                exclusions[pair_id] = {**base, "reason": reason}
            elif (left["operation"] in WRITE_KINDS or right["operation"] in WRITE_KINDS):
                if len(candidates) >= budgets["candidate_pairs"]:
                    frontier.append(diagnostic("candidate-pair-budget-exhausted", "候选访问对预算已耗尽",
                                               "The candidate-pair budget is exhausted",
                                               source={"hit": len(candidates),
                                                       "limit": budgets["candidate_pairs"]}))
                    continue
                candidates[pair_id] = base
    return {
        "candidates": [candidates[key] for key in sorted(candidates)],
        "exclusions": [exclusions[key] for key in sorted(exclusions)],
        "frontier": frontier[:budgets["frontier_items"]],
        "counts": {"buckets": bucket_hit, "object_candidates": object_hit,
                   "alias_comparisons": comparisons, "mhp_queries": mhp_queries},
    }


def build_protection_overlay(request, projection, execution, pairs, *, raii_graphs=()):
    budgets = request["budgets"]
    accesses = {item["id"]: item for item in projection["accesses"]}
    protections, frontier = [], []
    for graph in raii_graphs:
        if graph.get("status") != "complete":
            frontier.extend(deepcopy(graph.get("frontier", [])) or [diagnostic(
                "synchronization-evidence-incomplete", "mutex/RAII 同步证据不完整",
                "Mutex/RAII synchronization evidence is incomplete",
                source={"scope_id": graph.get("scope_id")})])
    queries = 0
    for pair in pairs["candidates"]:
        queries += 1
        if queries > budgets["protection_queries"]:
            frontier.append(diagnostic("protection-query-budget-exhausted", "保护证明查询预算已耗尽",
                                       "The protection-proof query budget is exhausted"))
            break
        left, right = accesses[pair["left"]], accesses[pair["right"]]
        left_ids, right_ids = set(left.get("source_access_ids", [])), set(right.get("source_access_ids", []))
        relevant = False
        for graph in raii_graphs:
            mutexes = {item["id"]: item for item in graph.get("mutexes", [])}
            regions = {item["id"]: item for item in graph.get("held_regions", [])}
            for proof in graph.get("proofs", []):
                if proof.get("proof_kind") != "mutual-exclusion" or proof.get("status") != "complete":
                    continue
                selected = [regions.get(item) for item in proof.get("region_ids", [])]
                if len(selected) != 2 or any(item is None or item.get("status") != "complete" for item in selected):
                    continue
                first, second = selected
                direct = bool(left_ids & set(first.get("access_ids", [])) and
                              right_ids & set(second.get("access_ids", [])))
                reverse = bool(right_ids & set(first.get("access_ids", [])) and
                               left_ids & set(second.get("access_ids", [])))
                if not direct and not reverse:
                    if left_ids & set(first.get("access_ids", [])) or right_ids & set(second.get("access_ids", [])):
                        relevant = True
                    continue
                mutex = mutexes.get(proof.get("mutex_id"), {})
                mutex_kind = str(mutex.get("mutex_kind") or mutex.get("kind") or "plain")
                region_threads = (first.get("thread_id"), second.get("thread_id"))
                pair_threads = (left.get("execution_instance_id"), right.get("execution_instance_id"))
                thread_binding = region_threads == pair_threads if direct else \
                    region_threads == tuple(reversed(pair_threads))
                guards_complete = all(region.get("guard") is None or
                                      region.get("guard") in access.get("guards", [])
                                      for region, access in ((first, left), (second, right)))
                exact = (mutex.get("resolution") == "exact" and
                         not any(token in mutex_kind for token in ("robust", "recursive", "unknown")) and
                         mutex.get("object_id") is not None and
                         all(proof.get("mutex_id") in item.get("mutex_ids", []) for item in selected) and
                         all(item.get("owner_id") is not None for item in selected) and
                         thread_binding and guards_complete and
                         len(proof.get("thread_ids", [])) == 2 and
                         "bounded-same-plain-mutex" in proof.get("limitations", []))
                if not exact:
                    relevant = True; continue
                protections.append({
                    "id": identity({"pair": pair["id"], "proof": proof["id"]}),
                    "pair_id": pair["id"], "status": "protected-within-bounded-model",
                    "mutex_id": proof["mutex_id"], "region_ids": sorted(proof["region_ids"]),
                    "thread_ids": sorted(proof["thread_ids"]),
                    "evidence": sorted(set(proof.get("evidence", []))),
                    "limitations": ["bounded-same-plain-mutex", "not-general-happens-before",
                                    "not-whole-program-safety"],
                })
        if relevant and not any(item["pair_id"] == pair["id"] for item in protections):
            frontier.append(diagnostic("protection-unknown", "候选访问对的 mutex 保护证据不闭合",
                                       "Mutex-protection evidence for the candidate pair is incomplete",
                                       source={"pair_id": pair["id"]}))
    status = "partial" if frontier or projection.get("status") != "complete" or \
        execution.get("status") != "complete" or \
        any(item.get("status") != "complete" for item in raii_graphs) else "complete"
    dependencies = [dependency("ConcurrentAccessProjectionFacts", projection["scope_id"], projection),
                    dependency("ExecutionInstanceBindingOverlay", execution["scope_id"], execution)]
    dependencies.extend(dependency("CppRaiiSynchronizationGraph", item["scope_id"], item) for item in raii_graphs)
    dependencies = sorted({(item["kind"], item["id"]): item for item in dependencies}.values(),
                          key=lambda item: (item["kind"], item["id"]))
    return concurrent_access_document(
        "AccessProtectionOverlay", scope_id=request["scope_id"], request_hash=request["semantic_digest"],
        status=status, protections=_dedupe(protections), counts={"queries": min(queries, budgets["protection_queries"]),
                                                                  "protected": len(protections)},
        dependencies=dependencies, diagnostics=frontier[:budgets["frontier_items"]],
        frontier=frontier[:budgets["frontier_items"]], semantic_digest=None)


def build_candidate_graph(request, projection, execution, protection, pairs):
    protections = {item["pair_id"]: item for item in protection["protections"]}
    candidates, atomic_handoff, frontier = [], [], [*projection["frontier"], *execution["frontier"],
                                                    *protection["frontier"], *pairs["frontier"]]
    accesses = {item["id"]: item for item in projection["accesses"]}
    for pair in pairs["candidates"]:
        pair = deepcopy(pair)
        if pair["id"] in protections:
            pair["protection"] = "protected-within-bounded-model"
            pair["protection_id"] = protections[pair["id"]]["id"]
        candidates.append(pair)
        left, right = accesses[pair["left"]], accesses[pair["right"]]
        if left["atomic"] or right["atomic"] or left["operation"] in ADVANCED_KINDS or right["operation"] in ADVANCED_KINDS:
            advanced = left["operation"] in ADVANCED_KINDS or right["operation"] in ADVANCED_KINDS
            handoff = {"id": identity({"pair": pair["id"], "advanced": advanced}),
                       "pair_id": pair["id"], "advanced_atomic_semantics_required": advanced,
                       "orders": sorted({item for item in (left.get("ordering"), right.get("ordering"),
                                                           left.get("failure_ordering"), right.get("failure_ordering")) if item}),
                       "consumer": "A6" if advanced else "P4-or-A6"}
            atomic_handoff.append(handoff)
            if advanced:
                frontier.append(diagnostic("advanced-atomic-semantics-unsupported",
                                           "RMW/CAS/fence release sequence 需要 A6",
                                           "RMW/CAS/fence release-sequence semantics require A6",
                                           source={"pair_id": pair["id"]}))
    status = "partial" if frontier or any(item["status"] != "complete" for item in
                                           (projection, execution, protection)) else "complete"
    refs = [dependency("ConcurrentAccessProjectionFacts", projection["scope_id"], projection),
            dependency("ExecutionInstanceBindingOverlay", execution["scope_id"], execution),
            dependency("AccessProtectionOverlay", protection["scope_id"], protection)]
    counts = {**pairs["counts"], "accesses": len(accesses), "candidates": len(candidates),
              "exclusions": len(pairs["exclusions"]),
              "protected": sum(item["protection"] == "protected-within-bounded-model" for item in candidates),
              "atomic_handoff": len(atomic_handoff), "frontier": len(frontier)}
    planned = {
        "roots": execution["counts"].get("roots", 0),
        "contexts": execution["counts"].get("contexts", 0),
        "translation_units": len(request["members"]),
        "effects": projection["counts"].get("planned_effects", projection["counts"].get("effects", 0)),
        "accesses": max(len(accesses), projection["counts"].get("demanded_effects", 0)),
        "instances": execution["counts"].get("instances", 0),
        "mhp": execution["counts"].get("mhp", 0),
        "object_bindings": len(accesses),
        "buckets": pairs["counts"].get("buckets", 0),
        "pairs": len(candidates) + len(pairs["exclusions"]),
        "protection_queries": protection["counts"].get("queries", 0),
    }
    frontier_codes = {item["code"] for item in frontier}
    categories = {
        "roots": ("root", "entry", "scope"), "contexts": ("context", "scope"),
        "translation_units": ("tu", "source", "ir-only", "ast-only", "profile", "abi", "scope"),
        "effects": ("effect", "source-ir"), "accesses": ("access", "effect", "source-ir"),
        "instances": ("instance", "lifecycle", "entry"), "mhp": ("mhp", "lifecycle", "parallel"),
        "object_bindings": ("object", "alias", "provenance"), "buckets": ("bucket", "object"),
        "pairs": ("pair", "mhp", "alias", "object"), "protection_queries": ("protection", "mutex", "synchronization"),
    }
    completeness = {}
    global_partial = frontier_codes & {"request-time-budget-exhausted", "open-scope",
                                       "dependency-failed", "unknown-external-synchronization"}
    for name, value in planned.items():
        relevant = [code for code in frontier_codes
                    if any(token in code for token in categories[name])]
        relevant.extend(sorted(global_partial))
        failed = min(value, sum("failed" in code for code in relevant))
        partial = min(max(0, value - failed), 1 if relevant else 0)
        completeness[name] = {"planned": value, "completed": max(0, value - partial - failed),
                              "partial": partial, "failed": failed}
    return concurrent_access_document(
        "ConcurrentAccessCandidateGraph", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=status,
        projection=refs[0], execution_instances=refs[1], protection=refs[2],
        accesses=sorted(accesses.values(), key=lambda item: item["id"]),
        candidates=sorted(candidates, key=lambda item: item["id"]),
        exclusions=sorted(pairs["exclusions"], key=lambda item: item["id"]),
        atomic_handoff=sorted(atomic_handoff, key=lambda item: item["id"]),
        completeness=completeness, counts=counts,
        dependencies=sorted(refs, key=lambda item: (item["kind"], item["id"])),
        diagnostics=frontier[:request["budgets"]["frontier_items"]],
        frontier=frontier[:request["budgets"]["frontier_items"]], semantic_digest=None)


def build_report(request, graph, *, hits=0, misses=0):
    graph_ref = dependency("ConcurrentAccessCandidateGraph", graph["scope_id"], graph)
    language_counts = {}
    for standard in ("c11", "c17", "c++17", "c++20"):
        planned = sum(item["standard"] == standard for item in request["members"])
        language_counts[standard] = {"planned": planned,
                                     "completed": planned if graph["status"] == "complete" else 0,
                                     "failed": 0, "candidate_pairs": graph["counts"].get("candidates", 0)
                                     if planned else 0,
                                     "protected": graph["counts"].get("protected", 0) if planned else 0,
                                     "excluded": graph["counts"].get("exclusions", 0) if planned else 0,
                                     "frontier": graph["counts"].get("frontier", 0) if planned else 0}
    diagnostics = deepcopy(graph["diagnostics"])
    diagnostics.append(diagnostic(
        "candidate-analysis-only", "R2 已生成并发访问候选，但未运行 data-race 或安全判定",
        "R2 generated concurrent-access candidates but did not run data-race or safety evaluation",
        suggestion="将候选交给明确版本化的 P4/A6 或后续风险消费者",
        suggestion_en="Pass candidates to an explicitly versioned P4/A6 or later risk consumer"))
    return concurrent_access_document(
        "ConcurrentAccessCandidateReport", scope_id=request["scope_id"],
        request_hash=request["semantic_digest"], status=graph["status"],
        exit_code=2 if graph["status"] == "partial" else 0,
        safety="not_evaluated", findings=None, graph=graph_ref,
        language_counts=language_counts, completeness=deepcopy(graph["completeness"]),
        counts=deepcopy(graph["counts"]), dependencies=[graph_ref],
        diagnostics=diagnostics, frontier=deepcopy(graph["frontier"]),
        cache={"hits": hits, "misses": misses}, semantic_digest=None)


def failed_report(code, detail, detail_en=None):
    item = diagnostic(code, f"并发访问候选分析失败：{detail}",
                      f"Concurrent-access candidate analysis failed: {detail_en or detail}")
    return concurrent_access_document(
        "ConcurrentAccessCandidateReport", scope_id=None, request_hash=None,
        status="failed", exit_code=1, safety="not_evaluated", findings=None,
        graph=None, language_counts={}, completeness={}, counts={}, dependencies=[],
        diagnostics=[item], frontier=[item], cache={"hits": 0, "misses": 0},
        semantic_digest=None)
