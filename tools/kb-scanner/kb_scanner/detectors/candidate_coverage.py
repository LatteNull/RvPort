"""Eliminate only a fully covered fallback match on the same normalized fact."""
import re
from .matchers import _ARCHITECTURE_TOKEN


def covered_identifier_candidate(fact, matches, entries):
    identifiers = {word for word in re.findall(r"[A-Za-z_]\w*", fact.canonical_value) if _ARCHITECTURE_TOKEN.search(word)}
    confirmed = {
        entries[key].canonical_value
        for _, match in matches if match is not None and match.status == "confirmed_local"
        for key in match.knowledge_ids if key in entries
    }
    return bool(identifiers) and identifiers.issubset(confirmed)
