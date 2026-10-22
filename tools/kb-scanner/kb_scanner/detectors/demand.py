"""Conservative proof requests using the same rules as final local detection."""
from collections import defaultdict

from .definitions import DEFAULT_DEFINITIONS
from .matchers import KnowledgeIndex, match_fact


class FactProofDemand:
    def __init__(self, definitions=DEFAULT_DEFINITIONS, matcher=match_fact):
        self._definitions = defaultdict(list)
        for definition in definitions.values():
            self._definitions[definition.input_kind].append(definition)
        self._matcher = matcher

    def __call__(self, facts, knowledge):
        index = KnowledgeIndex(knowledge)
        evidence_ids = set()
        for fact in facts.facts:
            if any(self._matcher(definition, fact, index) is not None
                   for definition in self._definitions.get(fact.kind, ())):
                evidence_ids.update(fact.evidence_ids)
        return frozenset(evidence_ids)
