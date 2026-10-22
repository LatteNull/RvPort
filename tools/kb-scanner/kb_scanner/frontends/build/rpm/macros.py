"""Explicit RPM macro environment. Never imports rpm or executes expansion."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from ..safety import normalize_target_arch, symbolic_uname

PROFILE = "rpm-4.20.0-upstream-target-v1"
ARCH_MACROS = frozenset({"_arch", "_target_cpu", "_isa", "__isa_name", "__isa_bits", "__isa"})


@dataclass(frozen=True)
class Value:
    text: str | None = None
    refs: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    reason: str = ""

    def with_refs(self, *refs: str) -> Value:
        return replace(self, refs=tuple(dict.fromkeys((*self.refs, *refs))))


@dataclass(frozen=True)
class Definition:
    value: Value
    defined: bool | None = True
    lazy: bool = False


class MacroEnv:
    def __init__(self, target: str, *, max_depth: int = 32, max_chars: int = 65536):
        if min(max_depth, max_chars) < 1:
            raise ValueError("RPM macro budgets must be positive")
        self.target = normalize_target_arch(target)
        self.max_depth, self.max_chars = max_depth, max_chars
        self.values = {
            "_arch": Definition(Value(self.target)),
            "_target_cpu": Definition(Value(self.target)),
            "nil": Definition(Value("")),
        }
        if self.target == "riscv64":
            self.values.update({name: Definition(Value(value)) for name, value in {
                "__isa_name": "riscv", "__isa_bits": "64", "__isa": "riscv-64", "_isa": "(riscv-64)",
            }.items()})
        else:
            self.values.update({name: Definition(Value(reason="rpm-profile-isa-unavailable"), None)
                                for name in ARCH_MACROS - {"_arch", "_target_cpu"}})

    def copy(self) -> MacroEnv:
        result = MacroEnv(self.target, max_depth=self.max_depth, max_chars=self.max_chars)
        result.values = dict(self.values)
        return result

    def define(self, name: str, body: str, key: str, *, lazy: bool = False) -> Value:
        value = Value(body) if lazy else self.expand(body)
        value = value.with_refs(key)
        self.values[name] = Definition(value, True, lazy)
        # __isa depends on its components; don't leave profile constants after overrides.
        if name in {"__isa_name", "__isa_bits", "__isa"}:
            self.values["_isa"] = Definition(Value("(%{__isa})"), True, True)
            if name != "__isa":
                self.values["__isa"] = Definition(Value("%{__isa_name}-%{__isa_bits}"), True, True)
        return value

    def invalidate(self, reason: str) -> None:
        self.values = {name: Definition(Value(refs=value.value.refs, reason=reason), None)
                       for name, value in self.values.items()}

    def merge(self, alternatives: list[MacroEnv]) -> None:
        if not alternatives:
            return
        merged = {}
        for name in sorted(set().union(*(env.values for env in alternatives))):
            defs = [env.values.get(name, Definition(Value(reason="rpm-macro-external"), None)) for env in alternatives]
            first = defs[0]
            refs = tuple(dict.fromkeys(ref for d in defs for ref in d.value.refs))
            same = all((d.value.text, d.defined, d.lazy, d.value.reason) ==
                       (first.value.text, first.defined, first.lazy, first.value.reason) for d in defs)
            merged[name] = replace(first, value=replace(first.value, refs=refs)) if same else Definition(
                Value(refs=refs, reason="rpm-macro-branch-conflict"),
                True if all(d.defined is True for d in defs) else None,
            )
        self.values = merged

    def expand(self, text: str, depth: int = 0, trail: tuple[str, ...] = (), _work=None) -> Value:
        work = [4096] if _work is None else _work
        work[0] -= 1
        if work[0] < 0 or depth >= self.max_depth or len(text) > self.max_chars:
            return Value(reason="rpm-macro-budget")
        pieces: list[str] = []
        refs: list[str] = []
        names: list[str] = []
        reasons: list[str] = []
        index = 0
        output_size = 0
        while index < len(text):
            if text.startswith("%%", index):
                pieces.append("%")
                index += 2
                continue
            if text.startswith(("%{", "%("), index):
                opening = text[index + 1]
                closing = "}" if opening == "{" else ")"
                end, nesting = index + 2, 1
                while end < len(text) and nesting:
                    if text[end] == opening:
                        nesting += 1
                    elif text[end] == closing:
                        nesting -= 1
                    end += 1
                if nesting:
                    return Value(refs=tuple(refs), names=tuple(names), reason="rpm-macro-unclosed")
                body = text[index + 2:end - 1]
                if opening == "(":
                    probe = symbolic_uname(body, self.target)
                    value = Value(probe.value, names=("uname -m",), reason="" if probe.recognized else "rpm-shell-expansion")
                else:
                    value = self._reference(body, depth, trail, work)
                refs.extend(value.refs)
                names.extend(value.names)
                if value.text is None:
                    reasons.append(value.reason or "rpm-macro-unknown")
                else:
                    pieces.append(value.text)
                    output_size += len(value.text)
                index = end
            elif text[index] == "%" and index + 1 < len(text) and (text[index + 1].isalpha() or text[index + 1] in "_["):
                # Bare/expressive macros are outside the braced bounded grammar.
                return Value(refs=tuple(refs), names=tuple(names), reason="rpm-macro-shape-unsupported")
            else:
                pieces.append(text[index])
                output_size += 1
                index += 1
            if output_size > self.max_chars:
                return Value(refs=tuple(refs), names=tuple(names), reason="rpm-macro-budget")
        return Value(None if reasons else "".join(pieces), tuple(dict.fromkeys(refs)),
                     tuple(dict.fromkeys(names)), ";".join(dict.fromkeys(reasons)))

    def _reference(self, body: str, depth: int, trail: tuple[str, ...], work=None) -> Value:
        match = re.fullmatch(r"(!?\??)([A-Za-z_][A-Za-z0-9_]*)(?::([\s\S]*))?", body)
        if not match:
            return Value(reason="rpm-macro-shape-unsupported")
        prefix, name, alternate = match.groups()
        if prefix not in {"", "?", "!?"} or (alternate is not None and not prefix):
            return Value(names=(name,), reason="rpm-macro-shape-unsupported")
        definition = self.values.get(name, Definition(Value(reason="rpm-macro-external"), None))
        if prefix:
            if definition.defined is None:
                return Value(refs=definition.value.refs, names=(name,), reason="rpm-macro-definedness-unknown")
            include = definition.defined if prefix == "?" else not definition.defined
            if not include:
                return Value("", definition.value.refs, (name,))
            if alternate is not None:
                value = self.expand(alternate, depth + 1, trail, work)
                return replace(value.with_refs(*definition.value.refs), names=tuple(dict.fromkeys((name, *value.names))))
        if name in trail:
            return Value(refs=definition.value.refs, names=(name,), reason="rpm-macro-cycle")
        value = definition.value
        if definition.defined is False:
            return Value(refs=value.refs, names=(name,), reason="rpm-macro-undefined")
        if definition.lazy and value.text is not None:
            value = self.expand(value.text, depth + 1, (*trail, name), work).with_refs(*value.refs)
        return replace(value, names=tuple(dict.fromkeys((name, *value.names))))
