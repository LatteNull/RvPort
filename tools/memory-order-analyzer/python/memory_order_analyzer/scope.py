"""Explicit scope binding, never whole-program inference from a directory."""

from collections import defaultdict

from .contracts import AnalysisError, document, identity, validate, validate_references
from .protocol import expected_protocol

CAPABILITIES = {"direct_symbols": True, "points_to": False, "effect_propagation": False,
                "callsite_specialization": False, "threads": False, "memory_model": False}


def preflight(scope, artifacts, facts):
    validate(scope, "ScopeManifest")
    validate_references(scope["members"], artifacts)
    validate_references(scope["members"], facts)
    targets, layouts, sources, seen, inputs = set(), set(), {}, set(), {}
    abi_values = defaultdict(set)
    for key in scope["members"]:
        artifact, module = artifacts[key], facts[key]
        validate(artifact, "BCArtifact")
        validate(module, "ModuleFacts")
        if artifact["artifact_key"] != key or module["artifact_key"] != key or artifact["sha256"] != module["module_hash"]:
            raise AnalysisError("invalid_reference", "Member keys/hashes disagree")
        lineage = {key, *artifact["lineage"]}
        if seen & lineage:
            raise AnalysisError("lineage_overlap", f"Repeated object/linked ancestry: {sorted(seen & lineage)}")
        seen.update(lineage)
        for path, digest in artifact["inputs"].items():
            if path in inputs and inputs[path] != digest:
                raise AnalysisError("configuration_conflict", f"Different input revisions in one scope: {path}")
            inputs[path] = digest
        targets.add(module["target"])
        layouts.add(module["layout"])
        source = artifact["toolchain"].get("source")
        if source:
            variant = (artifact["context_id"], artifact["profile"])
            if source in sources and sources[source] != variant:
                raise AnalysisError("configuration_conflict", f"Mutually exclusive source variants: {source}")
            sources[source] = variant
        for option, value in artifact["toolchain"].get("abi", {}).items():
            abi_values[option].add(value)
    if len(targets) != 1 or len(layouts) != 1 or "" in targets or "" in layouts:
        raise AnalysisError("target_conflict", "Members require identical known target triples and data layouts")
    if any(len(values) > 1 for values in abi_values.values()):
        raise AnalysisError("abi_conflict", "Conflicting key ABI options")
    return identity({"scope": scope, "members": sorted((key, artifacts[key]["sha256"]) for key in scope["members"]), "index_version": 2, "protocol": expected_protocol()})


def index_scope(scope, artifacts, facts):
    scope_id = preflight(scope, artifacts, facts)
    definitions, locals_by_member, bindings, unknown, diagnostics = defaultdict(list), {}, [], [], []
    for key in sorted(scope["members"]):
        local = {}
        for symbol in [*facts[key]["functions"], *facts[key]["globals"]]:
            if symbol["declaration"]:
                continue
            candidate = {"artifact_key": key, "symbol_id": symbol["id"], "linkage": symbol["linkage"], "comdat": symbol["comdat"]}
            if symbol["linkage"] == "internal":
                local[symbol["name"]] = candidate
            else:
                definitions[symbol["name"]].append(candidate)
        locals_by_member[key] = local
    for name, candidates in sorted(definitions.items()):
        strong = [c for c in candidates if c["linkage"] == "external" and not c["comdat"]]
        if len(strong) > 1:
            diagnostics.append({"code": "duplicate_strong_definition", "symbol": name, "candidates": strong})
    for key in sorted(scope["members"]):
        references = [{"id": call["id"], "symbol": call["target"], "kind": "call"} for call in facts[key]["calls"]]
        for event in facts[key]["events"]:
            for slot in ("address", "source_address"):
                address = event.get(slot, {})
                while address.get("kind") == "constant_gep":
                    address = address["base"]
                if address.get("kind") == "global":
                    references.append({"id": event["id"] + ":" + slot, "symbol": address["symbol"], "kind": "global"})
                elif address.get("kind") == "unknown":
                    unknown.append({"reference": event["id"], "reason": "unknown_pointer", "candidates": []})
        for reference in references:
            name = reference["symbol"]
            candidates = [locals_by_member[key][name]] if name in locals_by_member[key] else definitions.get(name, [])
            reason = "indirect" if name is None else "missing_definition"
            if candidates:
                reason = "ambiguous_or_interposable"
                one = candidates[0]
                definite = len(candidates) == 1 and one["linkage"] in ("external", "internal") and not one["comdat"]
                boundary = bool(scope["external_boundaries"]) or not scope["closed"]
                if definite and (one["linkage"] == "internal" or not boundary):
                    bindings.append({"reference": reference, "definition": one, "scope_id": scope_id, "evidence": scope["evidence"]})
                    continue
                if boundary:
                    reason = "external_boundary"
            unknown.append({"reference": reference, "reason": reason, "candidates": candidates})
    return document("ScopeIndex", scope_id=scope_id, members=sorted(scope["members"]), bindings=bindings,
                    unknown=unknown, diagnostics=diagnostics, capabilities=CAPABILITIES)
