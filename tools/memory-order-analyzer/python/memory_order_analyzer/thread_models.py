"""Versioned, deliberately narrow POSIX pthread semantic adoption."""

from copy import deepcopy

from .contracts import identity
from .thread_contracts import diagnostic


MODEL_ID = "posix-pthread-v1"
MODELS = {
    "pthread_create": {"parameters": 4, "roles": {"handle": 0, "callback": 2, "argument": 3}, "event": "create"},
    "pthread_join": {"parameters": 2, "roles": {"handle": 0, "result": 1}, "event": "join"},
    "pthread_mutex_lock": {"parameters": 1, "roles": {"mutex": 0}, "event": "mutex-lock"},
    "pthread_mutex_unlock": {"parameters": 1, "roles": {"mutex": 0}, "event": "mutex-unlock"},
}

UNSUPPORTED = {
    "pthread_detach", "pthread_cancel", "pthread_mutex_trylock", "pthread_mutex_timedlock",
    "pthread_cond_wait", "pthread_cond_signal", "pthread_cond_broadcast",
    "pthread_rwlock_rdlock", "pthread_rwlock_wrlock", "pthread_rwlock_unlock",
}


def _metadata_agrees(entries):
    if not entries:
        return True
    return any(len(entry) >= 2 and entry[0] == 2 and entry[1] == 3 for entry in entries)


def _supported_mutex_fingerprint(value):
    prefix = "zero-static:"
    return (isinstance(value, str) and value.startswith(prefix) and
            len(value) == len(prefix) + 64 and
            not set(value[len(prefix):]) - set("0123456789abcdef"))


def adopt_call(call):
    """Return a machine-only adoption; diagnostics are emitted separately."""
    symbol = call["symbol"]
    if symbol not in MODELS:
        return {"id": identity({"call": call["source"], "model": MODEL_ID}),
                "call": deepcopy(call["source"]), "symbol": symbol, "kind": "unknown",
                "event": None, "roles": {}, "reason": "api-not-modeled"}
    model = MODELS[symbol]
    reason = None
    if not call["direct"] or call["status"] != "candidate" or len(call["arguments"]) != model["parameters"]:
        reason = "pthread-call-ineligible"
    elif symbol == "pthread_create" and not _metadata_agrees(call["callback_metadata"]):
        reason = "callback-metadata-conflict"
    elif symbol == "pthread_create" and len(call["callback_targets"]) != 1:
        reason = "callback-target-unknown"
    elif symbol.startswith("pthread_mutex_") and not _supported_mutex_fingerprint(call["mutex_initializer"]):
        reason = "mutex-kind-unknown"
    return {"id": identity({"call": call["source"], "model": MODEL_ID}),
            "call": deepcopy(call["source"]), "symbol": symbol,
            "kind": "adopted" if reason is None else "unknown", "event": model["event"],
            "roles": deepcopy(model["roles"]), "reason": reason}


def adopt_all(local_facts):
    adoptions, diagnostics = [], []
    for artifact in sorted(local_facts):
        for call in local_facts[artifact]["calls"]:
            adoption = adopt_call(call)
            if call["symbol"] in MODELS or call["symbol"] in UNSUPPORTED or (
                    isinstance(call["symbol"], str) and call["symbol"].startswith("pthread_")):
                adoptions.append(adoption)
            if adoption["kind"] == "unknown" and call["symbol"] in MODELS:
                diagnostics.append(diagnostic(
                    adoption["reason"], "pthread 调用无法由首版模型确定采用",
                    "The pthread call cannot be adopted by the initial model",
                    source=call["source"],
                    suggestion="检查直接调用、ABI、回调目标或 mutex 初始化证据",
                    suggestion_en="Check the direct call, ABI, callback target, or mutex initializer evidence",
                ))
            elif call["symbol"] in UNSUPPORTED:
                diagnostics.append(diagnostic(
                    "pthread-api-unsupported", "该 pthread API 不在首版支持范围",
                    "This pthread API is outside the initial supported scope",
                    source=call["source"],
                    suggestion="保留为 unknown，后续通过独立 change 扩展模型",
                    suggestion_en="Keep it unknown and extend the model in a separate change",
                ))
    return sorted(adoptions, key=lambda item: item["id"]), diagnostics
