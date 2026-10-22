"""Conservative call-body adoption layered above the immutable ScopeIndex."""

from collections import defaultdict

from .contracts import canonical


def _ref(key, function_id=None, symbol_id=None):
    return {"artifact_key": key, "function_id": function_id, "id": symbol_id}


def _compatible(call, function):
    left, right = call["interface"], function["interface"]
    return (left["status"] == right["status"] == "supported" and
            all(left[name] == right[name] for name in
                ("function_type", "return_type", "parameter_types", "calling_convention", "vararg")))


def derive_adoptions(inputs, local_facts, source_binding=None):
    """Return one stable adoption for every raw call in the explicit scope.

    A unique external/internal definition and the verified linkonce_odr/any
    subset are the only definite choices.  Weak, ordinary linkonce, indirect,
    unsupported ABI and open-boundary calls remain explicit unknown edges.
    """
    metadata = {}
    by_name = defaultdict(list)
    raw_calls = {}
    for key in sorted(inputs.scope["members"]):
        local = local_facts[key]
        for item in local["functions"]:
            metadata[key, item["source"]["id"]] = item
        for raw in inputs.modules[key]["functions"]:
            if not raw["declaration"]:
                by_name[raw["name"]].append((key, raw, metadata.get((key, raw["id"]))))
        raw_calls.update({(key, item["id"]): item for item in inputs.modules[key]["calls"]})
    local_calls = {(key, item["source"]["id"]): item for key, local in local_facts.items()
                   for item in local["calls"]}
    closed = inputs.scope["closed"] and not inputs.scope["external_boundaries"]
    result = []
    for pair, raw in sorted(raw_calls.items()):
        key, call_id = pair
        source = _ref(key, raw["function"], call_id)
        candidates = by_name.get(raw["target"], []) if raw["kind"] == "direct" else []
        selected, kind, reason, assumptions = None, "unknown", "indirect_call", []
        local_call = local_calls.get(pair)
        if raw["kind"] == "direct" and not candidates:
            reason = "missing_definition"
        eligible = [(k, f, m) for k, f, m in candidates if m and local_call and _compatible(local_call, m)]
        if raw["kind"] == "direct" and candidates and not eligible:
            reason = "unsupported_or_mismatched_abi"
        exact = [(k, f, m) for k, f, m in eligible if
                 (f["linkage"] == "internal" and k == key or
                  f["linkage"] == "external" and m["exact_definition"] and not m["interposable"])]
        source_target = None
        if source_binding is not None and raw["kind"] == "direct":
            from .source_assistance import resolve_function
            declarations = [item for item in inputs.modules[key]["functions"]
                            if item.get("name") == raw["target"]]
            resolved = [resolve_function(source_binding, key, item["id"]) for item in declarations]
            targets = {canonical(item["target"]): item["target"] for item in resolved
                       if item["status"] == "resolved"}
            source_target = next(iter(targets.values())) if len(targets) == 1 else None
            exact = [item for item in exact if source_target and
                     item[0] == source_target["artifact_key"] and item[1]["id"] == source_target["function_id"]]
        if len(exact) == 1 and (exact[0][1]["linkage"] == "internal" or closed):
            selected = exact[0]
            kind = "source-verified-definition" if source_binding is not None else "unique-definition"
            reason = "source_ir_exact_definition" if source_binding is not None else "exact_unique_definition"
        elif eligible:
            odr = [(k, f, m) for k, f, m in eligible if f["linkage"] == "linkonce_odr" and
                   m["selection"] == "any" and m["dso_local"] and not m["interposable"] and
                   m["body_fingerprint"]]
            fingerprints = {m["body_fingerprint"] for _, _, m in odr}
            # The called TU must expose one representative; all visible copies
            # must normalize identically.  This is an ODR assumption, not linker selection.
            same_tu = [item for item in odr if item[0] == key]
            if closed and same_tu and len(odr) == len(eligible) and len(fingerprints) == 1:
                selected = same_tu[0]
                kind, reason = "odr-body-under-contract", "verified_linkonce_odr_any"
                assumptions = ["closed-scope", "llvm-odr-contract", "normalized-body-fingerprint"]
            elif candidates:
                reason = "ambiguous_interposable_or_odr_conflict"
        target = _ref(selected[0], None, selected[1]["id"]) if selected else None
        result.append({"call": source, "target": target, "kind": kind,
                       "reason": reason, "assumptions": assumptions})
    return result


def adoption_digest(adoptions):
    """Canonical text is useful in cache keys without mutating ScopeIndex."""
    return canonical(sorted(adoptions, key=lambda item: canonical(item["call"])))
