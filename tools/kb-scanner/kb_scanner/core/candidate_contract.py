"""Admission contract shared by detection, classification and report boundaries."""
import re


class CandidateAdmissionError(ValueError):
    """A classification bypassed the architecture candidate admission boundary."""


def architecture_attribute(value: str) -> bool:
    # Attribute *names*, not arbitrary strings/arguments containing an ISA name.
    without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', value)
    without_strings = re.sub(r'/\*.*?\*/|//[^\r\n]*', ' ', without_strings, flags=re.S)
    return bool(re.search(r'(?<![\w])(?:__)?(?:target|target_clones|vector_size|ext_vector_type|arch|cpu_specific|cpu_dispatch)(?:__)?\s*\(', without_strings))


def invalid_candidate(observation) -> bool:
    if observation.status != 'candidate':
        return False
    metadata = observation.metadata
    if metadata.get('architectureDisposition') in {'foreign', 'not-architecture-related', 'duplicate-child'}:
        return True
    if observation.kind not in {'inline_asm_candidate', 'target_attribute_candidate'}:
        return False
    basis = {'inline_asm_candidate': 'unclassified_inline_asm', 'target_attribute_candidate': 'architecture_attribute'}[observation.kind]
    disposition = metadata.get('architectureDisposition')
    return not (observation.evidence_ids and metadata.get('candidateBasis') == basis and (disposition == 'unknown' or (disposition == 'x86' and metadata.get('branchRole') == 'x86')))


def validate_candidates(detections, classifications) -> None:
    observations = {item.id: item for item in (*detections.observations, *classifications.observations)}
    for classification in classifications.classifications:
        for identifier in classification.observation_ids:
            item = observations.get(identifier)
            if item is not None and invalid_candidate(item):
                raise CandidateAdmissionError('candidate.invalid-admission: classification references an ineligible candidate')
