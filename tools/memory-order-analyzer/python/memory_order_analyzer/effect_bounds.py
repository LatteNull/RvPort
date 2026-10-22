"""Bound P2 payloads before recursive schema/digest/copy operations."""

from .contracts import AnalysisError

VALUE_KINDS = {"integer", "object", "parameter", "null", "unknown", "poison", "undef", "freeze", "expression"}


def bounded_values(payload):
    """Iteratively check tree shape and return every Value, including operands.

    Shared Python containers are permitted; cycles are not JSON. Count occurrences
    rather than distinct object identities, as serialization duplicates aliases.
    The general nesting cap also protects malformed, non-Value input.
    """
    budgets = payload.get("budgets", {}) if isinstance(payload, dict) else {}
    limit = budgets.get("local_steps", 100000) if isinstance(budgets, dict) else 100000
    limit = min(100000, max(1, limit)) if type(limit) is int else 100000
    pending, active, values = [(payload, 0, 0, False, False)], set(), []
    while pending:
        item, depth, value_depth, leaving, ratio = pending.pop()
        if isinstance(item, float) and not ratio:
            raise AnalysisError("schema_invalid", "P2 numeric fields require integer JSON representation")
        if not isinstance(item, (dict, list)):
            continue
        if leaving:
            active.remove(id(item))
            continue
        if id(item) in active or depth > 256:
            raise AnalysisError("evaluation_budget", "Cyclic or excessively nested P2 payload")
        active.add(id(item))
        pending.append((item, depth, value_depth, True, ratio))
        if isinstance(item, dict):
            kind = item.get("kind")
            if isinstance(kind, str) and kind in VALUE_KINDS and not ("call" in item or "occurrence" in item):
                value_depth += 1
                values.append(item)
                if len(values) > limit or value_depth > min(64, limit):
                    raise AnalysisError("evaluation_budget", "P2 Value node/depth budget exceeded")
            children = ((child, key == "complete_ratio") for key, child in item.items())
        else:
            children = ((child, False) for child in item)
        pending.extend((child, depth + 1, value_depth, False, child_ratio) for child, child_ratio in children)
    return values
