"""Demand-driven fixed-argument macro forwarding; terminal tokens stay original."""
from collections import defaultdict
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Token:
    value: str
    evidence_id: str | None
    forwarding: tuple[str, ...] = ()


@dataclass(frozen=True)
class Effects:
    paths: tuple[tuple[str, ...], ...]
    reasons: tuple[str, ...]
    expanded_tokens: int


def arguments(tokens, start):
    result, current, depth = [], [], 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if token.value == ')' and depth == 0:
            if current or result:
                result.append(tuple(current))
            return tuple(result), index + 1
        if token.value == ',' and depth == 0:
            result.append(tuple(current))
            current = []
        else:
            depth += 1 if token.value == '(' else -1 if token.value == ')' else 0
            current.append(token)
    return None, len(tokens)


class MacroEffectIndex:
    def __init__(self, evidence, demand_symbols=None):
        self.evidence = {item.id: item for item in evidence}
        self.parameters, self.replacements = defaultdict(list), defaultdict(list)
        self.names = set()
        for item in evidence:
            if item.kind == 'macro_definition':
                self.names.add(str(item.value))
            table = self.parameters if item.kind == 'macro_parameter' else self.replacements if item.kind == 'macro_replacement_token' else None
            if table is not None:
                table[item.metadata.get('macroDefinitionEvidenceId')].append(item)
        for table in (self.parameters, self.replacements):
            for items in table.values():
                items.sort(key=lambda item: item.metadata.get('ordinal', 0))
        # This is only a conservative query index, never an expansion proof.
        # Reach backwards from formal knowledge, including object aliases and
        # wrapper names supplied as actual arguments; preserve every raw record.
        self.demanded_calls = set()
        reachable = set(demand_symbols or ())
        if demand_symbols is not None:
            users = defaultdict(set)
            for definition_id, items in self.replacements.items():
                definition = self.evidence.get(definition_id)
                if definition is not None:
                    for item in items:
                        users[str(item.value)].add(str(definition.value))
            pending = list(reachable)
            while pending:
                for name in users.get(pending.pop(), ()):
                    if name not in reachable:
                        reachable.add(name)
                        pending.append(name)
        for item in evidence:
            if item.kind == 'call_expression' and str(item.value) in self.names:
                if demand_symbols is None or str(item.value) in reachable or any(
                    token['value'] in reachable
                    for arg in item.metadata.get('macroCall', {}).get('arguments', ()) for token in arg
                ):
                    self.demanded_calls.add(item.id)

    def resolve(self, call, environment, *, depth_limit=32, token_limit=4096):
        paths, reasons, count = set(), set(), 0
        data = call.metadata.get('macroCall', {})
        if data.get('status') != 'complete':
            return Effects((), (data.get('reason') or 'missing-call-arguments',), 0)
        for arg in data['arguments']:
            for token in arg:
                identifier = token.get('evidenceId')
                if identifier is None:
                    continue
                original = self.evidence.get(identifier)
                if (original is None or original.kind != 'macro_argument_token'
                    or original.subject_id != call.subject_id or original.value != token['value']
                    or original.metadata.get('callEvidenceId', call.id) != call.id
                    or original.metadata.get('compilationContextId') != call.metadata.get('compilationContextId')):
                    return Effects((), ('invalid-macro-argument-reference',), 0)
        actual = tuple(tuple(Token(t['value'], t.get('evidenceId')) for t in arg) for arg in data['arguments'])

        def invoke(name, args, prefix, trail, terminal=None):
            nonlocal count
            if len(trail) >= depth_limit or name in trail:
                reasons.add('macro-expansion-cycle-or-depth')
                return
            state = environment.get(name)
            if state is None or state.defined is False:
                if terminal is not None and terminal.evidence_id in self.evidence:
                    paths.add((*prefix, *terminal.forwarding, terminal.evidence_id))
                if terminal is not None:
                    for arg in args:
                        walk(arg, prefix, trail)
                return
            if state.defined is None or len(state.evidence_ids) != 1:
                reasons.add('macro-definition-unknown-or-conflicting')
                return
            definition = self.evidence.get(state.evidence_id)
            if definition is None or definition.kind != 'macro_definition':
                reasons.add('macro-definition-source-missing')
                return
            prefix = (*prefix, definition.id)
            if not state.function_like:
                if state.value and re.fullmatch(r'[A-Za-z_]\w*', state.value):
                    candidates = [item for item in self.replacements[definition.id] if item.value == state.value]
                    alias_token = Token(state.value,candidates[0].id) if len(candidates) == 1 else terminal
                    invoke(state.value, args, prefix, (*trail, name), alias_token)
                else:
                    reasons.add('unsupported-object-call')
                return
            params = self.parameters[definition.id]
            body = [token for token in self.replacements[definition.id] if token.metadata.get('tokenRole') != 'comment']
            if len(params) != len(args) or any(not arg for arg in args):
                reasons.add('macro-argument-count')
                return
            if any(t.metadata.get('unsupportedSemantics') for t in body) or any(p.value == '...' for p in params):
                reasons.add('unsupported-macro-semantics')
                return
            bindings = {str(parameter.value): (parameter, value) for parameter, value in zip(params, args)}
            substituted = []
            for item in body:
                if item.value in bindings:
                    parameter, tokens = bindings[item.value]
                    substituted.extend(Token(t.value, t.evidence_id, (*t.forwarding, parameter.id, item.id)) for t in tokens)
                else:
                    substituted.append(Token(str(item.value), item.id))
                count += len(bindings[item.value][1]) if item.value in bindings else 1
                if count > token_limit:
                    reasons.add('macro-token-budget')
                    return
            walk(substituted, prefix, (*trail, name))

        def walk(tokens, prefix, trail):
            index = 0
            while index + 1 < len(tokens):
                callee, opening = index, index + 1
                while callee < len(tokens) and tokens[callee].value == '(':
                    callee += 1
                parentheses = callee - index
                closing = callee + 1
                if parentheses and callee < len(tokens) and all(
                    i < len(tokens) and tokens[i].value == ')' for i in range(closing, closing+parentheses)
                ):
                    opening = closing + parentheses
                elif parentheses:
                    index += 1
                    continue
                token = tokens[callee] if callee < len(tokens) else tokens[index]
                if re.fullmatch(r'[A-Za-z_]\w*', token.value) and opening < len(tokens) and tokens[opening].value == '(':
                    nested, finish = arguments(tokens, opening+1)
                    if nested is None:
                        reasons.add('malformed-macro-replacement')
                        return
                    invoke(token.value, nested, (*prefix, *((token.evidence_id,) if token.evidence_id and not token.forwarding else ())),
                           trail, token)
                    index = finish
                else:
                    index += 1

        invoke(str(call.value), actual, (call.id,), ())
        # A truncated expansion cannot certify even an earlier terminal in that call.
        return Effects(tuple(sorted(paths)) if not reasons else (), tuple(sorted(reasons)), count)
