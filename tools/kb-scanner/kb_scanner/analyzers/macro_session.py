"""One translation-unit/configuration state walk over immutable frontend records."""
from collections import defaultdict
from pathlib import PurePosixPath

from .macro_state import MacroState, Evaluation, evaluate, join


def condition(item, environment):
    kind = item.metadata.get('nodeType')
    text = str(item.value)
    if kind in {'preproc_ifdef', 'preproc_ifndef'}:
        text = f'defined({text})'
        if kind == 'preproc_ifndef' or item.metadata.get('conditionNegated'):
            text = '!' + text
    result = evaluate(text, environment)
    if item.metadata.get('structureComplete') is False:
        return Evaluation(None, result.evidence_ids, result.names, 'partial-condition-structure')
    return result


def conjunction(left, right):
    return False if left is False or right is False else None if left is None or right is None else True


def order(item):
    return item.metadata.get('sourceOrder', item.location.start.line * 1000000 + (item.location.start.column or 1))


class MacroSession:
    def __init__(self, evidence, files, *, event_limit=100000, include_depth=16, include_limit=128):
        self.files = files
        self.event_limit, self.include_depth, self.include_limit = event_limit, include_depth, include_limit
        self.events, self.visits, self.reasons = 0, 0, set()
        self.processed = set()
        self.by_subject, self.replacements = defaultdict(list), defaultdict(list)
        baseline = {item.subject_id for item in evidence if item.parse_mode == 'tree_sitter_baseline'}
        for item in evidence:
            if item.kind == 'macro_replacement_token':
                self.replacements[item.metadata.get('macroDefinitionEvidenceId')].append(item)
            if item.location and (item.subject_id not in baseline or item.parse_mode == 'tree_sitter_baseline'):
                if item.kind in {'preprocessor_condition', 'preprocessor_branch', 'macro_definition', 'include', 'call_expression', 'macro_expansion'}:
                    self.by_subject[item.subject_id].append(item)
        for items in self.by_subject.values():
            items.sort(key=lambda item: (order(item), item.id))
        for items in self.replacements.values():
            items.sort(key=lambda item: item.metadata.get('ordinal', 0))

    def invalidate(self, environment, reason):
        self.reasons.add(reason)
        return {name: MacroState(None, None, state.evidence_id, state.origins) for name, state in environment.items()}

    def run(self, file, environment, callback, *, active=True, trail=()):
        self.processed.add(file.id)
        self.visits += 1
        if len(trail) >= self.include_depth or file.id in trail or self.visits > self.include_limit:
            return self.invalidate(environment, 'macro-include-cycle-or-budget')
        trail = (*trail, file.id)
        items = self.by_subject[file.id]

        def sequence(first, last, env, outer):
            index = first
            while index < last:
                item = items[index]
                index += 1
                self.events += 1
                if self.events > self.event_limit:
                    return self.invalidate(env, 'macro-event-budget')
                kind = item.metadata.get('nodeType')
                if item.kind == 'preprocessor_condition' and kind not in {'preproc_call', 'preproc_elif'}:
                    region = item.metadata.get('preprocessorRegion', {})
                    end = region.get('groupEnd', (item.location.end.line + 1) * 1000000)
                    finish = index
                    alternatives = []
                    while finish < last and order(items[finish]) < end:
                        candidate = items[finish]
                        other = candidate.metadata.get('preprocessorRegion', {})
                        if region and other.get('groupStart') == region.get('groupStart'):
                            alternatives.append(finish)
                        finish += 1
                    starts = [index - 1, *alternatives]
                    outcomes, remaining = [], True
                    for arm, stop in zip(starts, [*alternatives, finish]):
                        branch = items[arm]
                        is_else = branch.kind == 'preprocessor_branch'
                        result = Evaluation(1) if is_else else condition(branch, env)
                        feasible = conjunction(remaining, result.truth)
                        callback(branch, env, conjunction(outer, feasible), result)
                        if feasible is not False:
                            outcomes.append(sequence(arm + 1, stop, dict(env), conjunction(outer, feasible)))
                        else:
                            # Preserve occurrence activity without executing any inactive define/include.
                            for inactive in items[arm+1:stop]:
                                self.events += 1
                                if self.events > self.event_limit:
                                    return self.invalidate(env, 'macro-event-budget')
                                if inactive.kind == 'call_expression':
                                    callback(inactive, env, False, None)
                        remaining = conjunction(remaining, None if result.truth is None else not result.truth)
                    if remaining is not False:
                        outcomes.append(dict(env))
                    env = join(outcomes)
                    index = finish
                    continue
                if item.metadata.get('unsupportedMacroStateDirective'):
                    env = self.invalidate(env, 'unsupported-macro-state-directive')
                elif item.kind == 'preprocessor_branch' or kind == 'preproc_elif':
                    env = self.invalidate(env, 'unbound-preprocessor-alternative')
                elif item.kind == 'macro_definition' or item.metadata.get('macroUndefName'):
                    name = item.metadata.get('macroUndefName') or str(item.value)
                    tokens = self.replacements.get(item.id, ())
                    supported = item.metadata.get('structureComplete') is not False and not any(t.metadata.get('unsupportedSemantics') for t in tokens)
                    value = ' '.join(str(token.value) for token in tokens)
                    env[name] = MacroState(not bool(item.metadata.get('macroUndefName')) if supported else None,
                                           value if supported else None, item.id,
                                           function_like=bool(item.metadata.get('functionLike') or kind == 'preproc_function_def'))
                elif item.kind == 'include':
                    path = str(item.value)
                    relative = path.strip('"')
                    target = PurePosixPath(file.name).parent / relative
                    included = self.files.get(target.as_posix())
                    if path.startswith('<') or '..' in target.parts or target.is_absolute() or included is None:
                        env = self.invalidate(env, 'macro-include-unresolved')
                    else:
                        callback(item, env, outer, None)
                        env = self.run(included, env, callback, active=outer, trail=trail)
                else:
                    callback(item, env, outer, None)
            return env

        if active is False:
            return dict(environment)
        return sequence(0, len(items), dict(environment), active)
