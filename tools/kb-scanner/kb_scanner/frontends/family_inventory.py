"""Attach authorized path observations, never synthetic source Evidence."""
from dataclasses import replace

from ..core import CompletionStatus, StageResult


def annotate_inventory(result, workspace, context):
    if result.value is None:
        return result
    authorized = frozenset(workspace.files)
    entities = []
    for entity in result.value.entities:
        if entity.kind == "source_file" and entity.name in authorized:
            entity = replace(entity, properties={**entity.properties, "pathObservation": {
                "path": entity.name, "scope": "authorized-file-list",
                "parseStatus": "unknown" if result.status != CompletionStatus.COMPLETE else "complete",
                "excludedNames": context.excludes, "excludedPaths": context.exclude_paths,
            }})
        entities.append(entity)
    return StageResult(replace(result.value, entities=tuple(entities)), result.status, result.diagnostics)
