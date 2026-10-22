"""Conservative necessary ARM conditions, not an instruction vocabulary.

Compiler platform selectors are syntax attribution only. Unknown expressions,
negation, redefinition and missing macro provenance never prove exclusion.
"""
from __future__ import annotations

import re

ARM_SELECTORS = frozenset({'__aarch64__', '__arm__', '_M_ARM', '_M_ARM64'})


def required_foreign(expression: str, resolve=lambda name: ()) -> tuple[str, ...]:
    text = re.sub(r'/\*.*?\*/|//[^\r\n]*', ' ', expression, flags=re.S).replace('\\\n', ' ').strip()
    while text.startswith('(') and _matching_end(text) == len(text) - 1:
        text = text[1:-1].strip()
    for operator in ('||', '&&'):
        pieces = _split(text, operator)
        if len(pieces) > 1:
            proofs = [required_foreign(piece, resolve) for piece in pieces]
            if operator == '||' and not all(proofs):
                return ()
            return tuple(sorted({item for proof in proofs for item in proof}))
    atom = re.fullmatch(r'(?:defined\s*\(\s*([A-Za-z_]\w*)\s*\)|defined\s+([A-Za-z_]\w*)|([A-Za-z_]\w*))', text)
    if atom is None:
        return ()
    name = next(value for value in atom.groups() if value is not None)
    return (name,) if name in ARM_SELECTORS else resolve(name)


def _matching_end(text: str) -> int:
    depth = 0
    for index, char in enumerate(text):
        depth += (char == '(') - (char == ')')
        if depth == 0:
            return index
    return -1


def _split(text: str, operator: str) -> list[str]:
    depth, start = 0, 0
    result = []
    for index, char in enumerate(text):
        depth += (char == '(') - (char == ')')
        if depth == 0 and text.startswith(operator, index):
            result.append(text[start:index])
            start = index + len(operator)
    return [*result, text[start:]]


def foreign_guard_proof(condition, evidence_items, seen=frozenset()) -> tuple[str, ...]:
    """Return defining Evidence IDs for a same-file, unambiguous selector.

Definitions under else/elif, forward definitions, undef and cycles are rejected.
No project preprocessing or expression execution is performed.
"""
    if condition.id in seen or len(seen) >= 8 or condition.location is None:
        return ()
    if condition.metadata.get('nodeType') == 'preproc_ifndef' or condition.metadata.get('conditionNegated'):
        return ()
    same_file = [item for item in evidence_items if item.subject_id == condition.subject_id and item.location is not None]
    if any((item.kind == 'macro_definition' and item.value in ARM_SELECTORS) or item.metadata.get('macroUndefName') in ARM_SELECTORS for item in same_file):
        return ()
    provenance = {condition.id}

    def resolve(name):
        if any(item.kind == 'macro_expansion' and (item.metadata.get('macroUndefName') == name or (str(item.value) == '#undef' and not item.metadata.get('macroUndefName'))) for item in same_file):
            return ()
        definitions = [item for item in same_file if item.kind == 'macro_definition' and item.value == name]
        if len(definitions) != 1:
            return ()
        definition = definitions[0]
        if definition.location.start.line >= condition.location.start.line:
            return ()
        parents = [item for item in same_file if item.kind in {'preprocessor_condition', 'preprocessor_branch'} and item.id != condition.id and _contains(item.location, definition.location)]
        if not parents:
            return ()
        parent = min(parents, key=lambda item: (item.location.end.line - item.location.start.line, (item.location.end.column or 1) - (item.location.start.column or 1)))
        if parent.kind == 'preprocessor_branch' or parent.metadata.get('nodeType') == 'preproc_elif':
            return ()
        proof = foreign_guard_proof(parent, evidence_items, seen | {condition.id})
        if proof:
            provenance.update((*proof, definition.id))
        return proof

    return tuple(sorted(provenance)) if required_foreign(str(condition.value), resolve) else ()


def _contains(outer, inner):
    return (outer.start.line, outer.start.column or 1) <= (inner.start.line, inner.start.column or 1) and (inner.end.line, inner.end.column or 1) <= (outer.end.line, outer.end.column or 1)
