"""Evidence-level source-to-IR binding without memory-model inference."""

from pathlib import Path

from .contracts import AnalysisError, canonical, identity
from .source_contracts import counts, dependency, diagnostic, source_document, validate_source_document


def _symbols(module):
    for category in ("functions", "globals"):
        for symbol in module.get(category, []):
            yield category[:-1], symbol


def _compatible_linkage(source, llvm):
    if source in {"none", "internal"}:
        return llvm in {"internal", "private"}
    if source in {"external", "unique_external"}:
        return llvm in {"external", "common", "weak", "extern_weak", "linkonce", "available_externally"}
    return False


def _parameter_count(canonical_type):
    if "(" not in canonical_type or ")" not in canonical_type:
        return None
    arguments = canonical_type.rsplit("(", 1)[1].split(")", 1)[0].strip()
    if not arguments or arguments == "void":
        return 0
    return len([item for item in arguments.split(",") if item.strip() and item.strip() != "..."])


def _typed_evidence(node, typed, entity, fact):
    evidence = ["profile-tu", "mangled-name", "definition-role", "linkage", "visibility", "tls"]
    opposed = []
    if typed["definition"] != node["definition"]:
        opposed.append("definition-role-mismatch")
    if not _compatible_linkage(node["linkage"], typed["linkage"]):
        opposed.append("linkage-mismatch")
    if node["visibility"] != "unknown" and typed["visibility"] != node["visibility"]:
        opposed.append("visibility-mismatch")
    if typed["tls"] != node["tls"]:
        opposed.append("tls-mismatch")
    compatibility = entity["key"].get("compatibility", {})
    if typed.get("target") not in {None, "unknown", compatibility.get("target")}:
        opposed.append("target-mismatch")
    if typed.get("profile_id") != fact["profile_id"] or typed.get("physical_tu_id") != fact["physical_tu_id"]:
        opposed.append("profile-tu-mismatch")
    source_abi, llvm_abi = node.get("abi", {}), typed.get("abi", {})
    if node["kind"] == "function":
        expected = _parameter_count(node["canonical_type"])
        if expected is None or llvm_abi.get("parameters") != expected:
            opposed.append("function-type-abi-mismatch")
        else:
            evidence.append("canonical-type-abi")
    elif source_abi.get("complete") and llvm_abi.get("complete"):
        if (source_abi.get("size_bits"), source_abi.get("align_bits")) != (llvm_abi.get("size_bits"), llvm_abi.get("align_bits")):
            opposed.append("object-type-abi-mismatch")
        else:
            evidence.append("canonical-type-abi")
    else:
        opposed.append("missing-type-abi")
    return evidence, opposed


def _symbol_candidates(node, entity, fact, modules, allowed_artifacts, ir_facts):
    names = {value for value in (node.get("mangled_name"), node.get("name"), node.get("qualified_name")) if value}
    candidates = []
    expected_kind = "function" if node["kind"] == "function" else "global"
    for artifact, module in sorted(modules.items()):
        if artifact not in allowed_artifacts:
            continue
        for kind, symbol in _symbols(module):
            if kind != expected_kind or symbol.get("name") not in names:
                continue
            typed = next((item for item in ir_facts.get(artifact, {}).get("symbols", [])
                          if item["id"] == symbol["id"] and item["kind"] == kind), None)
            if typed is None:
                evidence, opposed = ["symbol-name", "module-association"], ["missing-llvm-binding-facts"]
            else:
                typed = {**typed, "target": ir_facts[artifact]["target"],
                         "profile_id": ir_facts[artifact]["profile_id"],
                         "physical_tu_id": ir_facts[artifact]["physical_tu_id"]}
                evidence, opposed = _typed_evidence(node, typed, entity, fact)
            candidates.append({"artifact_key": artifact, "id": symbol["id"], "name": symbol.get("name", ""),
                               "kind": kind, "linkage": symbol.get("linkage", "unknown"),
                               "declaration": symbol.get("declaration", False), "comdat": symbol.get("comdat", False),
                               "evidence": evidence, "opposed": opposed})
    return sorted(candidates, key=canonical)


def _source_location(value):
    if not isinstance(value, dict):
        return None
    for key in ("spelling", "expansion", "location"):
        item = value.get(key)
        if isinstance(item, dict) and isinstance(item.get("line"), int):
            return item
    return value if isinstance(value.get("line"), int) else None


def _location_path(location):
    """Return a stable absolute path when LLVM split file and directory fields."""
    if not isinstance(location, dict) or not location.get("file"):
        return None
    path = Path(location["file"])
    if not path.is_absolute() and location.get("directory"):
        path = Path(location["directory"]) / path
    return str(path.resolve()) if path.is_absolute() else path.as_posix()


def _same_location(left, right):
    if left.get("line") != right.get("line"):
        return False
    left_path, right_path = _location_path(left), _location_path(right)
    if left_path and right_path and left_path != right_path:
        return False
    left_column, right_column = left.get("column"), right.get("column")
    if isinstance(left_column, int) and isinstance(right_column, int):
        # Debug locations commonly point at a macro/call expression while the
        # AST relation points at the referenced object inside that expression.
        # A bounded column window preserves that legitimate association while
        # preventing every memory event on a one-line function from aliasing.
        return abs(left_column - right_column) <= 32
    return True


def _event_candidates(relation, modules, allowed_artifacts):
    wanted = _source_location(relation.get("source"))
    if wanted is None:
        return []
    result = []
    for artifact, module in sorted(modules.items()):
        if artifact not in allowed_artifacts:
            continue
        for event in module.get("events", []):
            locations = event.get("source", {}).get("inline_chain", [])
            if any(_same_location(item, wanted) for item in locations):
                result.append({"artifact_key": artifact, "id": event["id"], "kind": event.get("kind"),
                               "ordering": event.get("ordering"), "function": event.get("function")})
    return sorted(result, key=canonical)


def _fact_artifacts(fact, modules, ir_facts):
    """Associate a physical TU only with IR modules that expose matching source files."""
    typed = {artifact for artifact, value in ir_facts.items()
             if value["profile_id"] == fact["profile_id"] and
             value["physical_tu_id"] == fact["physical_tu_id"]}
    if ir_facts:
        return typed
    source_files = {_location_path(location) for node in fact["nodes"]
                    for location in node.get("source", {}).values()
                    if isinstance(location, dict) and location.get("file")}
    matched = set()
    for artifact, module in modules.items():
        files = {_location_path(location) for event in module.get("events", [])
                 for location in event.get("source", {}).get("inline_chain", [])
                 if location.get("file")}
        if source_files & files:
            matched.add(artifact)
    return matched


def build_source_ir_binding(request, index, facts_by_id, modules, ir_facts=None):
    ir_facts = ir_facts or {}
    validate_source_document(request, "SourceIRBindingRequest")
    validate_source_document(index, "ProgramEntityIndex")
    if request["scope_id"] != index["scope_id"]:
        raise AnalysisError("scope_conflict", "Source binding request and entity index use different scopes")
    expected_index = request["entity_index"]
    if (expected_index["kind"] != "ProgramEntityIndex" or
            expected_index["id"] != index["scope_id"] or
            expected_index["digest"] != identity(index)):
        raise AnalysisError("invalid_reference", "Entity index dependency digest changed")
    declared_facts = {(item["kind"], item["id"]): item["digest"] for item in request["source_facts"]}
    expected_facts = {("SourceSemanticFacts", key): identity(value) for key, value in facts_by_id.items()}
    declared_modules = {(item["kind"], item["id"]): item["digest"] for item in request["module_facts"]}
    expected_modules = {("ModuleFacts", key): identity(value) for key, value in modules.items()}
    if declared_facts != expected_facts or declared_modules != expected_modules:
        raise AnalysisError("invalid_reference", "Binding dependencies are missing, stale, or outside scope")
    declared_ir = {(item["kind"], item["id"]): item["digest"] for item in request.get("ir_facts", [])}
    expected_ir = {("LLVMSourceBindingFacts", key): identity(value) for key, value in ir_facts.items()}
    if declared_ir != expected_ir or not set(ir_facts) <= set(modules):
        raise AnalysisError("invalid_reference", "LLVM binding dependencies are missing, stale, or outside scope")
    fact_by_node = {}
    node_by_id = {}
    relation_entries = []
    for key, fact in facts_by_id.items():
        validate_source_document(fact, "SourceSemanticFacts")
        for node in fact["nodes"]:
            node_by_id[node["id"]] = node
            fact_by_node[node["id"]] = key
        relation_entries.extend((key, relation) for relation in fact["relations"])
    artifacts_by_fact = {key: _fact_artifacts(fact, modules, ir_facts) for key, fact in facts_by_id.items()}
    entity_for_node = {node: entity for entity in index["entities"] for node in entity["declarations"]}
    limit = request["budgets"]["binding_candidates"]
    used = 0
    entity_bindings, expression_bindings, frontier = [], [], []
    for source_id in sorted(entity_for_node):
        entity, node = entity_for_node[source_id], node_by_id[source_id]
        allowed = artifacts_by_fact[fact_by_node[source_id]]
        fact = facts_by_id[fact_by_node[source_id]]
        candidates = _symbol_candidates(node, entity, fact, modules, allowed, ir_facts)
        if used + len(candidates) > limit:
            frontier.append(diagnostic("binding-budget-exhausted", "绑定候选预算已耗尽", "Binding-candidate budget exhausted"))
            break
        used += len(candidates)
        opposed = sorted({reason for candidate in candidates for reason in candidate.pop("opposed")})
        evidence = sorted({reason for candidate in candidates for reason in candidate.pop("evidence")})
        resolution = "exact" if entity["resolution"] == "resolved" and len(candidates) == 1 and not opposed else "unresolved" if not candidates else "ambiguous" if len(candidates) > 1 or entity["resolution"] in {"ambiguous", "conflict"} else "candidate"
        if not candidates:
            opposed = ["missing-ir-symbol"]
        binding_id = identity({"layer": "entity-binding-v1", "source": source_id, "targets": candidates})
        entity_bindings.append({"id": binding_id, "source_id": source_id, "program_entity_id": entity["id"],
                                "resolution": resolution, "targets": candidates,
                                "cardinality": "zero" if not candidates else "one-to-one" if len(candidates) == 1 else "one-to-many",
                                "evidence": evidence, "opposed": opposed,
                                "reason": None if resolution == "exact" else "non-unique-or-incomplete-evidence"})
    for _, relation in sorted(relation_entries, key=lambda item: item[1]["id"]):
        if relation["kind"] not in {
                "atomic", "read", "write", "call", "control", "return", "compare",
                "atomic-c-load", "atomic-c-store", "atomic-c-rmw", "atomic-c-cas",
                "atomic-c-thread-fence", "atomic-c-signal-fence",
                "atomic-cpp-load", "atomic-cpp-store", "atomic-cpp-rmw", "atomic-cpp-cas",
                "atomic-cpp-thread-fence", "atomic-cpp-signal-fence"}:
            continue
        fact_key = next(key for key, candidate in relation_entries if candidate is relation)
        candidates = _event_candidates(relation, modules, artifacts_by_fact[fact_key])
        if used + len(candidates) > limit:
            frontier.append(diagnostic("binding-budget-exhausted", "绑定候选预算已耗尽", "Binding-candidate budget exhausted"))
            break
        used += len(candidates)
        resolution = "candidate" if candidates else "unresolved"
        binding_id = identity({"layer": "expression-binding-v1", "source": relation["id"], "targets": candidates})
        related_entity = entity_for_node.get(relation.get("to"))
        expression_bindings.append({"id": binding_id, "source_id": relation["id"],
                                    "program_entity_id": (related_entity["id"]
                                                          if related_entity is not None else None),
                                    "resolution": resolution, "targets": candidates,
                                    "cardinality": "zero" if not candidates else "one-to-one" if len(candidates) == 1 else "one-to-many",
                                    "evidence": ["source-range", "opcode-context"] if candidates else [],
                                    "opposed": [] if candidates else ["missing-debug-location"],
                                    "reason": "expression-mapping-is-never-memory-model-proof"})
    entity_bindings.sort(key=lambda item: item["id"]); expression_bindings.sort(key=lambda item: item["id"])
    dependencies = [dependency("ProgramEntityIndex", index["scope_id"], index)]
    dependencies += [dependency("SourceSemanticFacts", key, facts_by_id[key]) for key in sorted(facts_by_id)]
    dependencies += [dependency("ModuleFacts", key, modules[key]) for key in sorted(modules)]
    dependencies += [dependency("LLVMSourceBindingFacts", key, ir_facts[key]) for key in sorted(ir_facts)]
    dependencies.sort(key=lambda item: (item["kind"], item["id"]))
    binding_relations = {
        "atomic", "read", "write", "call", "control", "return", "compare",
        "atomic-c-load", "atomic-c-store", "atomic-c-rmw", "atomic-c-cas",
        "atomic-c-thread-fence", "atomic-c-signal-fence",
        "atomic-cpp-load", "atomic-cpp-store", "atomic-cpp-rmw", "atomic-cpp-cas",
        "atomic-cpp-thread-fence", "atomic-cpp-signal-fence",
    }
    planned = len(entity_for_node) + sum(1 for _, relation in relation_entries
                                         if relation["kind"] in binding_relations)
    emitted = len(entity_bindings) + len(expression_bindings)
    status = "complete" if emitted == planned and not frontier and all(item["resolution"] in {"exact", "candidate"} for item in [*entity_bindings, *expression_bindings]) else "partial"
    return source_document("SourceIRBinding", scope_id=request["scope_id"], status=status,
                           dependencies=dependencies, entity_bindings=entity_bindings,
                           expression_bindings=expression_bindings,
                           counts={"bindings": counts(planned, planned, emitted, failed=planned - emitted)},
                           diagnostics=[], frontier=frontier, semantic_digest=None)
