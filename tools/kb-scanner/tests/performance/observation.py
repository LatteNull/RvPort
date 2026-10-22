"""Transparent stage observation using existing pipeline injection boundaries."""
from dataclasses import replace
from time import perf_counter


def counts(value):
    return {name: len(getattr(value, name)) for name in (
        "files", "entities", "evidence", "facts", "entries", "relations",
        "proof_paths", "observations", "classifications", "assessments",
    ) if hasattr(value, name)}


class ObservedStage:
    def __init__(self, name, delegate, emit, clock=perf_counter):
        self.name, self.delegate, self.emit, self.clock = name, delegate, emit, clock

    def __getattr__(self, method):
        original = getattr(self.delegate, method)

        def call(*args, **kwargs):
            started = self.clock()
            self.emit({"stage": self.name, "event": "start", "input": [counts(arg) for arg in args],
                       "keywordInput": {key: counts(value) for key, value in kwargs.items()}})
            try:
                result = original(*args, **kwargs)
            except Exception as exc:
                self.emit({"stage": self.name, "event": "error", "error": type(exc).__name__,
                           "elapsedSeconds": self.clock() - started})
                raise
            self.emit({"stage": self.name, "event": "end", "status": result.status.value,
                       "elapsedSeconds": self.clock() - started,
                       "output": counts(result.value), "diagnostics": len(result.diagnostics)})
            return result
        return call


def observe(profile, emit):
    return replace(profile, **{
        name: ObservedStage(name, getattr(profile, name), emit)
        for name in profile.__dataclass_fields__
    })
