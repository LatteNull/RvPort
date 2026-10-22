"""RPM line structure with branch-local macro environments, no project execution."""
from __future__ import annotations
from dataclasses import dataclass
import re

from .conditions import conjunction, negate, evaluate
from .dependencies import parse_dependency, parse_constraint
from .macros import MacroEnv, Definition, Value
from .records import Records


@dataclass
class Frame:
    base: MacroEnv
    alternatives: list[MacroEnv]
    outer: bool | None
    remaining: bool | None
    active: bool | None
    parents: tuple[str, ...]
    keys: list[str]
    start: int
    layout: tuple[str, str, str]
    layouts: list[tuple[str, str, str]]
    seen_else: bool = False


def parse(source: str, path: str, target: str, *, max_depth: int = 64):
    from .shell import parse_scripts
    records = Records(path)
    env = MacroEnv(target)
    stack: list[Frame] = []
    active: bool | None = True
    parents: tuple[str, ...] = ()
    section, package = "preamble", "main"
    section_key = ""
    scripts = []
    structural_damage = False
    for line, raw in enumerate(source.splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("%dnl"):
            continue
        ctx = {"active": active, "parents": parents, "package": package, "section": section}
        if active is not False and re.search(r'%\{\s*(?:lua|load|expand|eval):|^%include\b', text):
            env.invalidate('rpm-executable-expansion')
            key = records.unknown(raw,line,'rpm-executable-expansion',**ctx)
            active, parents = None, (*parents,key)
            ctx = {**ctx,'active':active,'parents':parents}
        if text.startswith("#"):
            if "%" in text:
                value = records.expand(env, raw, line, 1, **ctx)
                if value.text is None:
                    records.unknown(raw, line, "rpm-comment-expansion-unknown", **ctx)
                    env.invalidate("rpm-comment-expansion-unknown")
            continue
        condition = re.match(r"^%(ifarch|ifnarch|if|elifarch|elifnarch|elif|else|endif)\b(.*)$", text, re.I)
        if condition:
            command, expression = condition.group(1).lower(), condition.group(2).strip()
            if command in {"else", "endif"} or command.startswith("elif"):
                if not stack:
                    records.unknown(raw,line,f"unmatched %{command}", **ctx)
                    active, structural_damage = None, True
                    continue
                frame = stack[-1]
                if frame.active is not False:
                    frame.alternatives.append(env.copy())
                    frame.layouts.append((section,package,section_key))
                env = frame.base.copy()
                section,package,section_key = frame.layout
                if command == "endif":
                    if frame.remaining is not False and not frame.seen_else:
                        frame.alternatives.append(frame.base)
                        frame.layouts.append(frame.layout)
                    env.merge(frame.alternatives)
                    if frame.layouts:
                        section,package,section_key = frame.layouts[0] if all(x==frame.layouts[0] for x in frame.layouts) else ('unknown','unknown','')
                    stack.pop()
                    active, parents = frame.outer, frame.parents
                    continue
                if frame.seen_else:
                    records.damage(frame.start,"rpm-duplicate-else")
                    records.unknown(raw,line,"rpm-duplicate-else",**ctx)
                    frame.remaining = None
                    structural_damage = True
                active, parents = frame.outer, frame.parents
            else:
                if len(stack) >= max_depth:
                    records.unknown(raw,line,"rpm-condition-budget",**ctx)
                    structural_damage = True
                    break
                frame = Frame(env.copy(), [], active, True, None, parents, [], len(records.items),
                              (section,package,section_key), [])
                stack.append(frame)
            ctx = {**ctx, "active": active, "parents": parents, "section":section, "package":package}
            if command == "else":
                truth = True
                refs = ()
                reason = ""
                frame.seen_else = True
            else:
                value = records.expand(env, expression,line,raw.find(expression)+1,**ctx)
                refs, reason = value.refs, value.reason
                if command.endswith("arch"):
                    truth = None if value.text is None else env.target in value.text.split() or "riscv" in value.text.split()
                    if command.endswith("narch"):
                        truth = negate(truth)
                else:
                    truth = evaluate(value.text)
                if truth is None:
                    reason = reason or "rpm-condition-unsupported"
            branch_truth = conjunction(frame.remaining,truth)
            active = conjunction(frame.outer,branch_truth)
            key = records.emit("build_branch", text, line, raw.find(text)+1,
                               **{**ctx,"active": active, "parents": (*frame.parents,*frame.keys,*refs)},
                               conditionGroup=f"{path}:rpm-group:{frame.start}",
                               branchOrdinal=len(frame.keys), conditionTruth=truth,
                               branchRemaining=frame.remaining, reason=reason)
            frame.keys.append(key)
            frame.active = active
            frame.remaining = conjunction(frame.remaining,negate(truth))
            parents = (*frame.parents,key)
            continue
        definition = re.match(r"^%(global|define|undefine)\s+([\w]+)(.*)$",text)
        if definition:
            command, name, tail = definition.groups()
            key = records.emit("build_assignment",text,line,raw.find(text)+1,**ctx,macroDefinition=name)
            if active is not False:
                if command == "undefine":
                    # RPM definitions are a stack; don't guess whether a shadowed definition resurfaces.
                    env.values[name] = Definition(Value(refs=(key,),reason="rpm-undefine-stack-unknown"),None)
                elif tail.startswith("(") or raw.rstrip().endswith("\\"):
                    env.values[name] = Definition(Value(refs=(key,),reason="rpm-parametric-or-multiline-macro"),True)
                    records.unknown(raw,line,"rpm-parametric-or-multiline-macro",**ctx)
                else:
                    body = tail.strip()
                    value = records.expand(env,body,line,raw.find(body)+1,**ctx)
                    env.define(name,body,key,lazy=command == "define")
                    # Definition depends on its literal reference records, not just prior definitions.
                    item = records.items[next(i for i,x in enumerate(records.items) if x.metadata['rpm']['key']==key)]
                    from dataclasses import replace
                    index = records.items.index(item)
                    records.items[index] = replace(item,metadata={**item.metadata,"rpm":{**item.metadata['rpm'],"parents":(*parents,*value.refs)}})
            continue
        section_match = re.match(r"^%(prep|build|install|check|files|package|description|pre|post|preun|postun|changelog|generate_buildrequires)\b(.*)",text,re.I)
        if section_match:
            section = section_match.group(1).lower()
            suffix = section_match.group(2).strip()
            if section in {"package","files","description"}:
                package = suffix or "main"
            section_key = records.emit("build_package_section",text,line,raw.find(text)+1,**{**ctx,"section":section,"package":package})
            continue
        ctx["parents"] = (*parents,*((section_key,) if section_key else ()))
        if section == 'unknown':
            ctx['active'] = None
        if section in {"preamble","package","unknown"}:
            if parse_dependency(raw,line,env,records,**ctx) or parse_constraint(raw,line,env,records,**ctx):
                continue
            if re.match(r"^BuildArch\s*:",text,re.I):
                env.invalidate("rpm-buildarch-profile-unknown")
                records.unknown(raw,line,"rpm-buildarch-profile-unknown",**ctx)
                continue
        if section in {"prep","build","install","check"}:
            scripts.append((line,raw,env.copy(),ctx))
        elif re.search(r"%\(|%\{\s*(?:lua|load|expand):|^%include\b",text):
            records.unknown(raw,line,"rpm-executable-expansion",**ctx)
            env.invalidate("rpm-executable-expansion")
        elif text.startswith('%'):
            key = records.unknown(raw,line,'rpm-directive-unsupported',**ctx)
            active, parents = None, (*parents,key)
    if stack:
        records.damage(stack[0].start,"rpm-unterminated-condition")
        records.diagnostics.append(f"{path}: unterminated RPM condition")
        structural_damage = True
    parse_scripts(source,scripts,records)
    if structural_damage:
        records.damage(0,"rpm-structure-incomplete")
    return tuple(records.items),tuple(records.diagnostics)
