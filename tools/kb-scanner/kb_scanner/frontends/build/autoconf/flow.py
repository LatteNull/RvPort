"""Bounded symbolic shell execution over owned syntax, without OS execution."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import PurePosixPath
import re

from ....core import stable_id
from ..vocabulary import BuildRecord
from .syntax import Node, Source
from .values import UNKNOWN, Value, pattern_match, triplet, value


@dataclass(slots=True)
class State:
    env: dict[str, Value] = field(default_factory=dict)
    output: str | None = ""
    status: int | None = 0
    stopped: bool = False
    reason: str = ""
    parent: str = ""
    last: Node | None = None

    def fork(self):
        return replace(self, env=dict(self.env))


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    output: str | None
    exit_code: int | None
    reason: str
    parents: tuple[str, ...]
    stdout: str | None = None


_PUNCTUATION = {";", ";;", "then", "fi", "else", "elif", "if", "case", "in", "esac", ")", "("}
_RAW_KINDS = {"variable_assignment": "build_assignment", "case_item": "build_branch",
              "case_statement": "build_condition", "if_statement": "build_condition",
              "command": "build_configuration", "test_command": "build_condition"}


class Evaluator:
    def __init__(self, sources: dict[str, Source], target: str, unit: str, *, max_steps=100000,
                 max_paths=128, max_depth=64, max_calls=8):
        if min(max_steps, max_paths, max_depth, max_calls) < 1:
            raise ValueError("Autoconf flow budgets must be positive")
        self.sources, self.target, self.unit = sources, target, unit
        self.max_steps, self.max_paths, self.max_depth, self.max_calls = max_steps, max_paths, max_depth, max_calls
        self.steps = 0
        self.serial = 0
        self.records: dict[str, list[BuildRecord]] = {}
        self.digests = {path: sha256(src.data).hexdigest() for path, src in sources.items()}

    def event(self, source, node, state, kind="build_configuration", **details):
        self.serial += 1
        key = stable_id("autoconf-event", self.unit, source.path, self.digests[source.path], self.target, self.serial)
        data = {"key": key, "unit": str(PurePosixPath(self.unit).parent), "entry": self.unit,
                "digest": self.digests[source.path],
                "target": self.target, "parents": (state.parent,) if state.parent else (),
                "byteStart": node.start, "byteEnd": node.end, **details}
        line, start, end = source.position(node)
        record = BuildRecord(kind, source.text(node).strip()[:512] or source.path, line, start, end,
                             {"autoconf": data, "selectionStatus": "unknown" if state.reason else "selected",
                              "reason": state.reason, "configuration": "default"})
        self.records.setdefault(source.path, []).append(record)
        state.parent, state.last = key, node
        return key

    def retain(self, source):
        """Keep facts from inactive branches too, outside the evaluated proof graph."""
        todo = [source.root]
        while todo:
            node = todo.pop()
            if node.kind in _RAW_KINDS:
                self.event(source, node, State(), _RAW_KINDS[node.kind], raw=True)
            todo.extend(child for _, child in reversed(node.children))

    def run(self, path, args=(), *, bound=False, parent="", calls=(), terminal=True):
        source = self.sources[path]
        state = State(env={str(i + 1): arg for i, arg in enumerate(args)}, parent=parent)
        state.reason = source.issue
        if not parent:
            self.event(source, source.root, state, "build_configuration", entry=True, bound=bound)
        if path in calls or len(calls) >= self.max_calls:
            state.reason = "autoconf-call-budget-or-cycle"
            states = [state]
        else:
            states = self.sequence(source, source.root.children, [state], 0, (*calls, path))
        raw_outputs = {item.output for item in states}
        outputs = {item.rstrip("\n") if item is not None else None for item in raw_outputs}
        codes = {item.status for item in states}
        reasons = {item.reason for item in states if item.reason}
        helper = PurePosixPath(path).name in {"config.guess", "config.sub"}
        output = next(iter(outputs)) if len(outputs) == 1 else None
        code = next(iter(codes)) if len(codes) == 1 else None
        if not reasons and all(item.status is not None and item.status != 0 for item in states):
            status, reason = "rejected", "autoconf-explicit-rejection"
        elif not reasons and code == 0 and (not helper or triplet(output, self.target)):
            status, reason = "accepted", "autoconf-bounded-acceptance"
        else:
            status, reason = "unknown", sorted(reasons)[0] if reasons else "autoconf-result-not-proven"
        parents = []
        for item in states:
            parents.append(self.event(source, item.last or source.root, item, "build_configuration",
                                      outcome=status if terminal else "", resultStatus=status, reason=reason, bound=bound,
                                      output=output, exitCode=code, scope="current-file-bytes"))
        return Outcome(status, output, code, reason, tuple(parents), next(iter(raw_outputs)) if len(raw_outputs) == 1 else None)

    def sequence(self, source, children, states, depth, calls):
        for _, node in children:
            if node.kind in _PUNCTUATION or node.kind == "comment":
                continue
            following = []
            for state in states:
                if state.stopped:
                    following.append(state)
                    continue
                self.steps += 1
                if self.steps > self.max_steps or depth > self.max_depth:
                    state.reason, state.stopped = "autoconf-flow-budget", True
                    following.append(state)
                    continue
                produced = self.statement(source, node, state, depth, calls)
                for item in produced:
                    # An unsupported side effect invalidates continuation. Raw syntax
                    # was retained separately, so stopping cannot erase source facts.
                    if item.reason:
                        item.stopped = True
                following.extend(produced)
                if len(following) > self.max_paths:
                    state.reason, state.stopped = "autoconf-path-budget", True
                    return [state]
            states = following
        return states

    def evaluate(self, source, node, state, calls):
        def substitution(child):
            commands = [item for _, item in child.children if item.kind == "command"]
            if len(commands) != 1 or any(item.kind not in {"command", "$(", ")", "`"} for _, item in child.children):
                state.reason = state.reason or "autoconf-command-substitution-unsupported"
                return UNKNOWN
            command = commands[0]
            text = " ".join(source.text(command).split())
            if text == "uname -m":
                self.event(source, command, state, "build_arch_probe", resolvedValue=self.target)
                return Value(self.target)
            if text.startswith("uname "):
                self.event(source, command, state, "build_arch_probe", valueKnown=False)
                return Value(None, "autoconf-target-environment-unknown")
            result = self.helper(source, command, state, calls)
            if result is None:
                state.reason = state.reason or "autoconf-command-substitution-unsupported"
                return UNKNOWN
            state.status = result.exit_code
            return Value(result.output, result.reason)
        return value(source, node, state.env, substitution)

    def statement(self, source, node, state, depth, calls):
        self.event(source, node, state, _RAW_KINDS.get(node.kind, "build_unsupported"))
        if node.kind == "variable_assignment":
            name = node.field("name")
            if name is None or "+=" in source.text(node):
                state.reason = "autoconf-assignment-unsupported"
            else:
                state.status = 0
                state.env[source.text(name)] = self.evaluate(source, node.field("value"), state, calls)
        elif node.kind == "case_statement":
            return self.case(source, node, state, depth, calls)
        elif node.kind == "if_statement":
            return self.conditional(source, node, state, depth, calls)
        elif node.kind == "command":
            self.command(source, node, state, calls)
        else:
            state.reason, state.status = "autoconf-unsupported-" + node.kind, None
        return [state]

    def argument(self, source, node, state, calls):
        result = self.evaluate(source, node, state, calls)
        if node.kind not in {"string", "raw_string"} and result.text is not None:
            if re.search(r"[\s*?\[]", result.text) or not result.text:
                state.reason = "autoconf-field-splitting-or-glob-unknown"
                return UNKNOWN
        return result

    def case(self, source, node, state, depth, calls):
        selector = self.evaluate(source, node.field("value"), state, calls)
        pending, completed = [state], []
        for _, arm in node.children:
            if arm.kind != "case_item":
                continue
            if any(child.kind in {";&", ";;&"} for _, child in arm.children):
                state.reason = "autoconf-case-fallthrough-unsupported"
                return [state]
            tests = []
            for pattern in arm.fields("value"):
                candidate = value(source, pattern, state.env)
                if pattern.kind in {"string", "raw_string"}:
                    match = None if selector.text is None or candidate.text is None else selector.text == candidate.text
                else:
                    match = pattern_match(selector.text, candidate.text)
                tests.append(match)
            decision = True if True in tests else None if None in tests else False
            next_pending = []
            for current in pending:
                if decision is not False:
                    chosen = current.fork()
                    self.event(source, arm, chosen, "build_branch", decision="selected" if decision else "possible")
                    body = tuple((key, child) for key, child in arm.children if key != "value")
                    completed.extend(self.sequence(source, body, [chosen], depth + 1, calls))
                if decision is not True:
                    next_pending.append(current)
            pending = next_pending
            if len(completed) + len(pending) > self.max_paths:
                state.reason, state.stopped = "autoconf-path-budget", True
                return [state]
        return completed + pending

    def condition(self, source, node, state, calls):
        if node.kind == "command":
            name = value(source, node.field("name"), state.env).text
            args = [self.argument(source, item, state, calls).text for item in node.fields("argument")]
            if name in {"true", ":", "false"} and not args:
                return name != "false"
            if name != "test":
                state.reason = "autoconf-condition-unsupported"
                return None
        elif node.kind == "test_command":
            inner = [child for _, child in node.children if child.kind in {"binary_expression", "unary_expression"}]
            if len(inner) != 1:
                state.reason = "autoconf-test-unsupported"
                return None
            expression = inner[0]
            args = [self.evaluate(source, child, state, calls).text if key != "operator" else source.text(child)
                    for key, child in expression.children]
        else:
            state.reason = "autoconf-condition-unsupported"
            return None
        if None in args:
            return None
        if len(args) == 3 and args[1] in {"=", "!=", "=="}:
            return (args[0] == args[2]) == (args[1] != "!=")
        if len(args) == 2 and args[0] in {"-z", "-n"}:
            return bool(args[1]) == (args[0] == "-n")
        state.reason = "autoconf-test-unsupported"
        return None

    def conditional(self, source, node, state, depth, calls):
        conditions = [child for key, child in node.children if key == "condition" and child.kind != ";"]
        if len(conditions) != 1:
            state.reason = "autoconf-condition-list-unsupported"
            return [state]
        decision = self.condition(source, conditions[0], state, calls)
        body = tuple((key, child) for key, child in node.children
                     if key != "condition" and child.kind not in {"elif_clause", "else_clause"})
        completed = self.sequence(source, body, [state.fork()], depth + 1, calls) if decision is not False else []
        pending = [] if decision is True else [state.fork()]
        for _, clause in node.children:
            if clause.kind == "else_clause":
                completed.extend(self.sequence(source, clause.children, pending, depth + 1, calls))
                pending = []
            elif clause.kind == "elif_clause":
                parts = tuple((key, child) for key, child in clause.children if child.kind not in _PUNCTUATION)
                if parts:
                    synthetic = replace(clause, kind="if_statement", children=(("condition", parts[0][1]), *parts[1:]))
                    following = []
                    for item in pending:
                        test = self.condition(source, parts[0][1], item, calls)
                        if test is not False:
                            completed.extend(self.sequence(source, synthetic.children[1:], [item.fork()], depth + 1, calls))
                        if test is not True:
                            following.append(item)
                    pending = following
        return completed + pending

    def helper(self, source, node, state, calls):
        name = value(source, node.field("name"), state.env).text
        args = list(node.fields("argument"))
        if name in {"sh", "/bin/sh"} and args:
            name = value(source, args.pop(0), state.env).text
        if name is None or PurePosixPath(name).name not in {"config.guess", "config.sub"}:
            return None
        # Bare names are PATH lookups, not evidence that the adjacent file is used.
        if "/" not in name or PurePosixPath(name).is_absolute():
            state.reason = "autoconf-helper-path-unbound"
            return None
        components = list(PurePosixPath(self.unit).parent.parts)
        for part in PurePosixPath(name).parts:
            if part == "..":
                if not components:
                    state.reason = "autoconf-helper-outside-workspace"
                    return None
                components.pop()
            elif part != ".":
                components.append(part)
        path = "/".join(components)
        if path not in self.sources:
            state.reason = "autoconf-helper-unavailable"
            return None
        arguments = tuple(self.argument(source, arg, state, calls) for arg in args)
        self.event(source, node, state, "build_include", helper=path)
        result = self.run(path, arguments, bound=True, parent=state.parent, calls=calls, terminal=False)
        if len(result.parents) == 1:
            state.parent = result.parents[0]
        else:
            self.event(source, node, state, "build_configuration", parents=result.parents, helperResult=True)
        if result.status == "unknown":
            state.reason = result.reason
        return result

    def command(self, source, node, state, calls):
        if any(key not in {"name", "argument"} for key, _ in node.children):
            state.reason, state.status = "autoconf-command-prefix-unsupported", None
            return
        name = value(source, node.field("name"), state.env).text
        args = [] if name not in {"exit", "true", ":", "false", "echo", "printf"} else [
            self.argument(source, child, state, calls).text for child in node.fields("argument")]
        if name == "exit":
            state.stopped = True
            state.status = state.status if not args else int(args[0]) % 256 if len(args) == 1 and args[0] is not None and args[0].isdigit() else None
        elif name in {"true", ":", "false"} and not args:
            state.status = int(name == "false")
        elif name in {"echo", "printf"}:
            output = None
            if all(arg is not None and "\\" not in arg for arg in args):
                if name == "echo" and (not args or not args[0].startswith("-")):
                    output = " ".join(args)
                elif name == "printf" and len(args) == 2 and args[0] == "%s":
                    output = args[1]
            if name == "printf" and len(args) == 2 and args[0] == "%s\\n" and args[1] is not None:
                output = args[1] + "\n"
            if output is None or state.output is None or len(state.output) + len(output) > 4096:
                state.output, state.status = None, None
                state.reason = "autoconf-output-unsupported-or-budget"
            else:
                state.output += output + ("\n" if name == "echo" else "")
                state.status = 0
        else:
            result = self.helper(source, node, state, calls)
            if result is None:
                state.reason, state.status = state.reason or "autoconf-command-unsupported", None
            else:
                state.status = result.exit_code
                state.output = None if state.output is None or result.stdout is None else state.output + result.stdout
