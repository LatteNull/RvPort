"""Bounded, bilingual occurrence views over immutable macro effect relations."""
from collections import defaultdict


class MacroEffectsProjection:
    def __init__(self, relations):
        groups = defaultdict(list)
        for relation in relations:
            effect = relation.metadata.get('macroEffect')
            if effect:
                key = effect['terminalEvidenceId'], str(relation.metadata.get('configuration', 'default'))
                groups[key].append(effect)
        self.uses = defaultdict(dict)
        for (eid, configuration), effects in sorted(groups.items()):
            states = {item.get('active') for item in effects}
            state = 'inactive' if states == {False} else 'selected' if states == {True} and all(item.get('buildBound') for item in effects) else 'unknown'
            complete = all(item.get('proven') for item in effects)
            reasons = tuple(sorted({reason for item in effects for reason in item.get('reasonCodes', ())}))
            self.uses[eid][configuration] = {
                'configuration':configuration, 'selectionStatus':state,
                'proofStatus':'complete' if complete else 'unknown',
                'translationUnits':tuple(sorted({item['translationUnit'] for item in effects})),
                'reasonCodes':reasons,
                'description':'固定实参调用链已证明；编译选择状态单独展示。' if complete else '保留实参事实，但尚不能证明该实参被调用。',
                'description_en':'Fixed-argument call forwarding is proven; compilation selection is shown separately.' if complete else 'The original argument fact is retained, but calling this argument is not proven.',
            }

    def configurations(self, eid):
        return tuple(self.uses.get(eid, ()))

    def extension(self, eid, *, limit=32):
        uses = self.uses.get(eid, {})
        if not uses:
            return {}
        return {'org.rvport.kb-scanner.macro-effects': {
            'uses':tuple(uses[key] for key in tuple(uses)[:limit]), 'truncated':len(uses) > limit,
            'totalUses':len(uses), 'limit':limit}}
