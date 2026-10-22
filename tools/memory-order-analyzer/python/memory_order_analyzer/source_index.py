"""Conservative cross-translation-unit source entity resolution."""

from collections import defaultdict

from .contracts import AnalysisError, identity
from .source_contracts import counts, dependency, diagnostic, source_document, validate_source_document


INTERNAL = {"internal", "none"}
MODELED_EXTERNAL_ENTITIES = {
    "pthread_create", "pthread_join", "pthread_mutex_lock", "pthread_mutex_unlock",
    "memory_order_relaxed", "memory_order_consume", "memory_order_acquire",
    "memory_order_release", "memory_order_acq_rel", "memory_order_seq_cst",
}


def compatibility_key(profile):
    return {"language": profile["language"], "standard": profile["standard"],
            "target": profile["target"], "abi": profile["abi"],
            "clang": profile["replay"]["clang_version"]}


def _entity_key(node, fact, profile, *, include_type=True, include_compatibility=True):
    local = node["linkage"] in INTERNAL or "anonymous-namespace" in node["attributes"]
    symbol = node["usr"] or node["mangled_name"] or node["qualified_name"] or node["name"]
    key = {"symbol": symbol, "kind": node["kind"],
           "language_linkage": node["language_linkage"]}
    if include_compatibility:
        key["compatibility"] = compatibility_key(profile)
    if include_type:
        key["type"] = node["canonical_type"]
    if local:
        key["physical_tu_id"] = fact["physical_tu_id"]
    return key


def _definition_digest(node):
    return next((item.split(":", 1)[1] for item in node["attributes"]
                 if item.startswith("definition-sha256:")), None)


def _modeled_external_boundary(entries):
    """Recognize only system entities whose semantics are explicitly modeled."""
    names = {node.get("name") or node.get("qualified_name") for _, node in entries}
    return len(names) == 1 and next(iter(names)) in MODELED_EXTERNAL_ENTITIES and not any(
        node["definition"] for _, node in entries)


def _resolution(entries, profiles):
    nodes = [node for _, node in entries]
    definitions = [node for node in nodes if node["definition"]]
    compatibilities = {identity(compatibility_key(profiles[member])) for member, _ in entries}
    if len(compatibilities) > 1:
        return "conflict", "incompatible-profiles"
    types = {node["canonical_type"] for node in nodes}
    if len(types) > 1:
        return "conflict", "incompatible-types"
    abi = {identity(node["abi"]) for node in nodes if node["abi"]}
    if len(abi) > 1:
        return "conflict", "incompatible-abi"
    if len({node["tls"] for node in nodes}) > 1:
        return "conflict", "incompatible-tls"
    visible = {node["visibility"] for node in nodes if node["visibility"] != "unknown"}
    if len(visible) > 1:
        return "conflict", "incompatible-visibility"
    if not definitions:
        return "unresolved", "missing-definition"
    if len(definitions) == 1:
        return "resolved", None
    kinds = {node["definition_kind"] for node in definitions}
    if kinds <= {"tentative"}:
        return "resolved", "c-tentative-definition-set"
    if kinds <= {"tentative", "strong"} and sum(node["definition_kind"] == "strong" for node in definitions) == 1:
        return "resolved", "strong-definition-overrides-tentative"
    digests = {_definition_digest(node) for node in definitions}
    if kinds <= {"inline", "template"} and None not in digests and len(digests) == 1:
        return "resolved", "equivalent-definition-set"
    if kinds <= {"inline", "template"}:
        return "conflict", "odr-definition-mismatch"
    if kinds <= {"weak", "comdat", "inline", "template"}:
        return "ambiguous", "link-selection-unknown"
    return "conflict", "multiple-strong-definitions"


def build_entity_index(request, facts_by_id, profiles_by_id):
    validate_source_document(request, "ProgramEntityIndexRequest")
    requested = set(request["members"])
    if set(facts_by_id) != requested or set(profiles_by_id) != requested:
        raise AnalysisError("invalid_reference", "Entity index inputs must exactly match explicit scope members")
    declared = {(item["kind"], item["id"]): item["digest"] for item in request["dependencies"]}
    expected = {("SourceSemanticFacts", key): identity(value) for key, value in facts_by_id.items()}
    if declared != expected:
        raise AnalysisError("invalid_reference", "Entity index dependencies are missing, stale, or outside scope")
    for member in requested:
        fact = validate_source_document(facts_by_id[member], "SourceSemanticFacts")
        profile = validate_source_document(profiles_by_id[member], "CompilationProfileIdentity")
        if fact["physical_tu_id"] != member or fact["profile_id"] != profile["profile_id"]:
            raise AnalysisError("profile_conflict", "Source facts do not match their scoped compilation profile")
    grouped = defaultdict(list)
    for member in sorted(requested):
        for node in facts_by_id[member]["nodes"]:
            if node["kind"] not in {"function", "variable", "field"}:
                continue
            grouped[identity(_entity_key(node, facts_by_id[member], profiles_by_id[member],
                                         include_type=False, include_compatibility=False))].append((member, node))
    budget = request["budgets"]["entity_groups"]
    external_boundaries = []
    analyzable = []
    for group_id, entries in sorted(grouped.items()):
        if _modeled_external_boundary(entries):
            external_boundaries.append((group_id, entries))
        else:
            analyzable.append((group_id, entries))
    entities, frontier, diagnostics = [], [], []
    for _, entries in external_boundaries:
        nodes = [node for _, node in entries]
        diagnostics.append(diagnostic(
            "modeled-external-entity", "已识别建模系统外部实体边界",
            "Recognized a modeled system external entity boundary",
            source={"name": nodes[0].get("name"),
                    "source_nodes": sorted(node["id"] for node in nodes)}))
    for ordinal, (_, entries) in enumerate(analyzable):
        if ordinal >= budget:
            frontier.append(diagnostic("entity-budget-exhausted", "实体分组预算已耗尽", "Entity-group budget exhausted",
                                       suggestion="提高 entity_groups 预算后重试", suggestion_en="Increase entity_groups and retry"))
            break
        nodes = [node for _, node in entries]
        resolution, reason = _resolution(entries, profiles_by_id)
        declarations = sorted(node["id"] for node in nodes)
        definitions = sorted(node["id"] for node in nodes if node["definition"])
        key = _entity_key(nodes[0], facts_by_id[entries[0][0]], profiles_by_id[entries[0][0]])
        key["canonical_types"] = sorted({node["canonical_type"] for node in nodes})
        entity_id = identity({"layer": "program-entity-v1", "key": key, "declarations": declarations})
        object_id = identity({"layer": "program-object-v1", "entity": entity_id}) if nodes[0]["kind"] in {"variable", "field"} else None
        candidates = definitions if resolution in {"ambiguous", "conflict"} else []
        entities.append({"id": entity_id, "object_id": object_id, "kind": nodes[0]["kind"],
                         "resolution": resolution, "key": key, "declarations": declarations,
                         "definitions": definitions, "candidates": candidates,
                         "evidence": sorted({"usr" if node["usr"] else "mangled-name" if node["mangled_name"] else "qualified-name" for node in nodes}),
                         "reason": reason})
        if resolution in {"ambiguous", "conflict", "unresolved"}:
            frontier.append(diagnostic(f"entity-{resolution}", f"程序实体解析为 {resolution}",
                                       f"Program entity resolved as {resolution}", source={"entity_id": entity_id}))
    entities.sort(key=lambda item: item["id"])
    dependencies = sorted((dependency("SourceSemanticFacts", key, facts_by_id[key]) for key in requested),
                          key=lambda item: (item["kind"], item["id"]))
    complete = len(entities) == len(analyzable) and not frontier and all(facts_by_id[key]["status"] == "complete" for key in requested)
    document = source_document("ProgramEntityIndex", scope_id=request["scope_id"],
                               status="complete" if complete else "partial", dependencies=dependencies,
                               entities=entities,
                               counts={"groups": counts(len(analyzable), len(analyzable), len(entities),
                                                         failed=len(analyzable) - len(entities)),
                                       "external_boundaries": counts(len(external_boundaries))},
                               diagnostics=diagnostics, frontier=frontier, semantic_digest=None)
    return document
