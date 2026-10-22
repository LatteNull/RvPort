"""Canonical object overlay derived from source resolution and IR binding."""

from .contracts import AnalysisError, identity
from .source_contracts import counts, dependency, diagnostic, source_document, validate_source_document


def _distinct_targets(bindings):
    """Return physical LLVM objects once, independent of declaration fan-in."""
    distinct = {}
    for binding in bindings:
        for target in binding["targets"]:
            if target["kind"] != "global":
                continue
            key = (target["artifact_key"], target["id"], target["kind"])
            distinct.setdefault(key, target)
    return sorted(distinct.values(), key=lambda item: (item["artifact_key"], item["id"], item["kind"]))


def _set_level_exact(entity, bindings, objects):
    """Prove a canonical object from the target set, not each declaration edge.

    A header declaration compiled in the definition TU can legitimately bind to
    that TU's definition and report only a definition-role mismatch.  That local
    role difference is harmless when every edge converges on one distinct LLVM
    definition and no other opposition remains.
    """
    definitions = [item for item in objects if not item.get("declaration", False)]
    allowed_opposition = {"definition-role-mismatch"}
    def compatible(binding):
        if binding["targets"]:
            return (set(binding["opposed"]) <= allowed_opposition and
                    binding["resolution"] in {"exact", "candidate"})
        # A declaration-only TU need not emit an LLVM global when it never
        # odr-uses/references that declaration.  It is neutral only after the
        # program entity has a unique definition elsewhere in the scope.
        return (binding["source_id"] not in entity["definitions"] and
                binding["resolution"] == "unresolved" and
                binding["opposed"] == ["missing-ir-symbol"])

    return (entity["resolution"] == "resolved" and bool(objects) and
            len(definitions) == 1 and bool(bindings) and
            all(compatible(item) for item in bindings))


def build_overlay(scope_id, index, binding, *, item_budget=None):
    validate_source_document(index, "ProgramEntityIndex")
    validate_source_document(binding, "SourceIRBinding")
    if scope_id != index["scope_id"] or scope_id != binding["scope_id"]:
        raise AnalysisError("scope_conflict", "Overlay inputs use different explicit scopes")
    by_entity = {}
    for item in binding["entity_bindings"]:
        by_entity.setdefault(item["program_entity_id"], []).append(item)
    entities = [item for item in index["entities"] if item["object_id"]]
    limit = len(entities) if item_budget is None else item_budget
    mappings, frontier = [], []
    for ordinal, entity in enumerate(entities):
        if ordinal >= limit:
            frontier.append(diagnostic("overlay-budget-exhausted", "对象覆盖预算已耗尽", "Object-overlay budget exhausted"))
            break
        bindings = by_entity.get(entity["id"], [])
        objects = _distinct_targets(bindings)
        exact = _set_level_exact(entity, bindings, objects)
        resolution = "exact" if exact else entity["resolution"] if entity["resolution"] in {"ambiguous", "unresolved", "conflict"} else "candidate"
        mappings.append({"program_object_id": entity["object_id"], "program_entity_id": entity["id"],
                         "resolution": resolution, "artifact_objects": objects,
                         "source_nodes": entity["declarations"],
                         "binding_ids": sorted(item["id"] for item in bindings),
                         "evidence": sorted({*entity["evidence"], *(e for item in bindings for e in item["evidence"])})})
    mappings.sort(key=lambda item: item["program_object_id"])
    status = "complete" if len(mappings) == len(entities) and not frontier and all(item["resolution"] == "exact" for item in mappings) else "partial"
    dependencies = sorted([dependency("ProgramEntityIndex", index["scope_id"], index),
                           dependency("SourceIRBinding", binding["scope_id"], binding)],
                          key=lambda item: (item["kind"], item["id"]))
    return source_document("CanonicalObjectOverlay", scope_id=scope_id, status=status,
                           dependencies=dependencies, mappings=mappings,
                           counts={"objects": counts(len(entities), len(entities), len(mappings), failed=len(entities) - len(mappings))},
                           diagnostics=[], frontier=frontier, semantic_digest=None)


def resolve_artifact_object(overlay, artifact_key, object_id):
    """Return a unique canonical object or an explicit non-resolution state."""
    validate_source_document(overlay, "CanonicalObjectOverlay")
    matches = [item for item in overlay["mappings"] if any(target["artifact_key"] == artifact_key and target["id"] == object_id for target in item["artifact_objects"])]
    if len(matches) == 1 and matches[0]["resolution"] in {"exact", "resolved"}:
        return {"status": "resolved", "program_object_id": matches[0]["program_object_id"], "mapping": matches[0]}
    return {"status": "unresolved" if not matches else "ambiguous", "program_object_id": None,
            "candidates": sorted(item["program_object_id"] for item in matches)}
