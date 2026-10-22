"""Explicit, read-only bridge from AST evidence into P2-P4 composition.

The bridge only supplies verified identities.  It never creates execution-order,
reads-from, synchronizes-with, happens-before, or safety evidence.
"""

from pathlib import Path

from .contracts import AnalysisError, identity
from .source_contracts import read_source_document


def load_source_assistance(directory, *, scope_id=None):
    root = Path(directory).resolve()
    report = read_source_document(root / "report.json", "AstAssistedAnalysisReport")
    binding = read_source_document(root / "source-ir-binding.json", "SourceIRBinding")
    overlay = read_source_document(root / "canonical-object-overlay.json", "CanonicalObjectOverlay")
    source_facts = [read_source_document(path, "SourceSemanticFacts")
                    for path in sorted((root / "source-facts").glob("*.json"))]
    values = {"report": report, "binding": binding, "overlay": overlay,
              "source_facts": source_facts}
    scopes = {item["scope_id"] for item in (report, binding, overlay)}
    if len(scopes) != 1 or scope_id is not None and scopes != {scope_id}:
        raise AnalysisError("scope_conflict", "Source assistance does not match the requested analysis scope")
    declared = {(item["kind"], item["id"]): item["digest"] for item in report["outputs"]}
    expected = {
        ("SourceIRBinding", binding["scope_id"]): identity(binding),
        ("CanonicalObjectOverlay", overlay["scope_id"]): identity(overlay),
    }
    if not all(declared.get(key) == digest for key, digest in expected.items()):
        raise AnalysisError("invalid_reference", "Source assistance report has stale binding or overlay outputs")
    fact_dependencies = {(item["kind"], item["id"]): item["digest"]
                         for item in binding["dependencies"]
                         if item["kind"] == "SourceSemanticFacts"}
    actual_facts = {("SourceSemanticFacts", item["physical_tu_id"]): identity(item)
                    for item in source_facts}
    if fact_dependencies != actual_facts:
        raise AnalysisError("invalid_reference", "Source assistance has missing or stale source facts")
    return values


def resolve_function(binding, artifact_key, symbol_id):
    """Resolve an IR function to one definition using one program-entity group."""
    matching = [item for item in binding["entity_bindings"]
                if any(target.get("artifact_key") == artifact_key and target.get("id") == symbol_id
                       and target.get("kind") == "function" for target in item["targets"])]
    entities = {item["program_entity_id"] for item in matching}
    if len(entities) != 1:
        return {"status": "unresolved" if not entities else "ambiguous", "target": None}
    candidates = {(target["artifact_key"], target["id"]): target
                  for item in binding["entity_bindings"] if item["program_entity_id"] in entities
                  for target in item["targets"]
                  if target.get("kind") == "function" and not target.get("declaration", False)}
    exact = [target for target in candidates.values()
             if any(item["program_entity_id"] in entities and item["resolution"] == "exact" and
                    target in item["targets"] for item in binding["entity_bindings"])]
    exact = {(item["artifact_key"], item["id"]): item for item in exact}
    if len(exact) == 1:
        target = next(iter(exact.values()))
        return {"status": "resolved", "target": {"artifact_key": target["artifact_key"],
                                                     "function_id": target["id"]},
                "program_entity_id": next(iter(entities))}
    return {"status": "unresolved" if not exact else "ambiguous", "target": None,
            "candidates": sorted({key for key in exact})}


def resolve_object(overlay, source):
    if not isinstance(source, dict):
        return {"status": "unresolved", "program_object_id": None}
    artifact = source.get("artifact_key")
    identifier = source.get("id") or source.get("symbol_id")
    matches = [item for item in overlay["mappings"]
               if any(target.get("artifact_key") == artifact and target.get("id") == identifier
                      for target in item["artifact_objects"])]
    if len(matches) == 1 and matches[0]["resolution"] == "exact":
        return {"status": "resolved", "program_object_id": matches[0]["program_object_id"],
                "mapping": matches[0]}
    return {"status": "unresolved" if not matches else "ambiguous", "program_object_id": None,
            "candidates": sorted(item["program_object_id"] for item in matches)}


def resolve_event_object(binding, overlay, source):
    """Resolve an IR memory event through an AST expression-to-entity edge.

    Expression bindings remain candidate source-location evidence; they become
    usable as an object identity only when every matching relation converges on
    one exact canonical overlay mapping.
    """
    if not isinstance(source, dict):
        return {"status": "unresolved", "program_object_id": None}
    artifact, identifier = source.get("artifact_key"), source.get("id")
    entity_ids = {item["program_entity_id"] for item in binding["expression_bindings"]
                  if item["program_entity_id"] is not None and any(
                      target.get("artifact_key") == artifact and target.get("id") == identifier
                      for target in item["targets"])}
    mappings = [item for item in overlay["mappings"]
                if item["program_entity_id"] in entity_ids and item["resolution"] == "exact"]
    object_ids = {item["program_object_id"] for item in mappings}
    if len(object_ids) == 1:
        return {"status": "resolved", "program_object_id": next(iter(object_ids)),
                "program_entity_ids": sorted(entity_ids)}
    return {"status": "unresolved" if not object_ids else "ambiguous",
            "program_object_id": None, "candidates": sorted(object_ids)}


def canonical_object_key(overlay, address):
    """Return an exact program object ID or None; no name-based fallback."""
    if not isinstance(address, dict):
        return None
    source = address.get("source") if address.get("kind") == "object" else None
    result = resolve_object(overlay, source)
    return result["program_object_id"] if result["status"] == "resolved" else None


def relevant_dependency_slice(protocol, graph, bundle):
    """Describe the exact AST dependencies relevant to one P4 candidate."""
    event_ids = {protocol.get(name) for name in
                 ("flag_write", "flag_read", "payload_write", "payload_read")}
    effects = [item for item in graph.get("effects", []) if item.get("id") in event_ids]
    artifacts = sorted({item.get("source", {}).get("artifact_key") for item in effects
                        if isinstance(item.get("source"), dict) and item["source"].get("artifact_key")})
    mappings = sorted({item["program_object_id"] for item in bundle["overlay"]["mappings"]
                       if item["program_object_id"] in {protocol.get("flag_object"),
                                                        protocol.get("payload_object")}})
    missing = []
    if len(effects) != len({item for item in event_ids if item is not None}):
        missing.append("thread-effect")
    if protocol.get("flag_object") not in mappings:
        missing.append("flag-object-binding")
    if protocol.get("payload_object") not in mappings:
        missing.append("payload-object-binding")
    return {"artifacts": artifacts, "program_objects": mappings,
            "source_report_digest": identity(bundle["report"]),
            "status": "complete" if not missing else "partial", "missing": sorted(missing)}


def ast_sequence_edges(bundle, modules, effects):
    """Project exact adjacent CompoundStmt order onto already-bound IR effects."""
    event_locations = {}
    for artifact, module in modules.items():
        for event in module.get("events", []):
            event_locations[(artifact, event["id"])] = event.get("source", {}).get("inline_chain", [])

    def path(location):
        if not isinstance(location, dict) or not location.get("file"):
            return None
        value = Path(location["file"])
        if not value.is_absolute() and location.get("directory"):
            value = Path(location["directory"]) / value
        return str(value.resolve()) if value.is_absolute() else value.as_posix()

    def contains(source, location):
        begin = source.get("expansion") or source.get("spelling") or {}
        end = source.get("expansion_end") or source.get("spelling_end") or begin
        if path(begin) != path(location):
            return False
        point = (location.get("line"), location.get("column"))
        first = (begin.get("line"), begin.get("column"))
        last = (end.get("line"), end.get("column"))
        return all(isinstance(value, int) for value in (*point, *first, *last)) and first <= point <= last

    effect_list = list(effects.values()) if isinstance(effects, dict) else list(effects)
    by_node = {}
    relations = []
    for facts in bundle.get("source_facts", []):
        by_node.update({item["id"]: item for item in facts["nodes"]})
        relations.extend(item for item in facts["relations"]
                         if item["kind"] == "sequenced-before" and item["status"] == "exact")
    result = set()
    for relation in relations:
        before_node, after_node = by_node.get(relation["from"]), by_node.get(relation["to"])
        if before_node is None or after_node is None:
            continue
        before = [effect for effect in effect_list if any(
            contains(before_node["source"], location)
            for location in event_locations.get(
                (effect["source"]["artifact_key"], effect["source"]["id"]), []))]
        after = [effect for effect in effect_list if any(
            contains(after_node["source"], location)
            for location in event_locations.get(
                (effect["source"]["artifact_key"], effect["source"]["id"]), []))]
        for left in before:
            for right in after:
                if left["thread_instance_id"] == right["thread_instance_id"] and left["id"] != right["id"]:
                    result.add((left["id"], right["id"]))
    return sorted(result)
