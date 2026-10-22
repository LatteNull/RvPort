"""字面属性解码；不展开宏、不执行编译器、不猜测目标 ISA。"""
import re
from dataclasses import dataclass

_NAME = re.compile(r"(?<![\w:])(?:(\w+)\s*::\s*)?(__)?(target_clones|target_version|target|cpu_dispatch|cpu_specific)(?:__)?\s*\(")
_TOKEN = re.compile(r'\s*("(?:[^"\\]|\\["\\])*"|,)')
SOURCE = "https://releases.llvm.org/18.1.8/tools/clang/docs/AttributeReference.html"


def decode(value, max_chars=65536, max_options=128):
    if min(max_chars, max_options) < 0:
        raise ValueError("attribute budgets must be nonnegative")
    result = {"mechanism": "unknown", "options": (), "status": "unknown",
              "reason": "multiversion-attribute-unsupported", "optionCount": 0}
    if not isinstance(value, str):
        return result
    if len(value) > max_chars:
        return {**result, "reason": "multiversion-budget-exceeded"}
    matches = list(_NAME.finditer(value))
    if len(matches) != 1:
        return result
    match = matches[0]
    mechanism = match.group(3)
    result["mechanism"] = mechanism
    if match.group(1) not in {None, "gnu"} or mechanism not in {"target", "target_clones"}:
        return result
    position, segments, current, expect_literal = match.end(), [], "", True
    while position < len(value):
        if value[position:].lstrip().startswith(")"):
            if expect_literal:
                return result
            segments.append(current)
            break
        token = _TOKEN.match(value, position)
        if token is None:
            return {**result, "reason": "multiversion-nonliteral-attribute"}
        position = token.end()
        text = token.group(1)
        if text == ",":
            if expect_literal:
                return result
            segments.append(current)
            current, expect_literal = "", True
        else:
            current += re.sub(r'\\(["\\])', r'\1', text[1:-1])
            expect_literal = False
    else:
        return result
    options = tuple(part.strip() for segment in segments for part in segment.split(","))
    result["optionCount"] = len(options)
    if len(options) > max_options:
        return {**result, "reason": "multiversion-budget-exceeded"}
    if not all(options) or (mechanism == "target" and "default" in options and len(options) != 1):
        return result
    # target's comma list is a feature set for one version; clones is a version list.
    versions = tuple(sorted(set(options))) if mechanism == "target_clones" else (",".join(sorted(set(options))),)
    return {**result, "options": versions, "status": "complete", "reason": "multiversion-literal-attribute"}


@dataclass(frozen=True)
class CompilerProfile:
    family: str = ""
    version: str = ""
    language: str = ""
    source_target: str = ""
    provenance: str = ""


def semantic_rule(profile, mechanism):
    unknown = {"status": "unknown", "requiresDefault": False, "ruleId": None,
               "source": SOURCE, "targetApplicability": "unknown"}
    if profile is None:
        return unknown
    applies = (profile.family == "clang" and re.fullmatch(r"18\.1(?:\.\d+)?", profile.version)
               and profile.language in {"c", "cpp"} and profile.source_target in {"x86", "x86_64"}
               and bool(profile.provenance))
    if not applies or mechanism not in {"target", "target_clones"} or (mechanism == "target" and profile.language != "cpp"):
        return unknown
    return {**unknown, "status": "applicable", "requiresDefault": True,
            "ruleId": f"clang-18.1-x86-{mechanism}", "provenance": profile.provenance}
