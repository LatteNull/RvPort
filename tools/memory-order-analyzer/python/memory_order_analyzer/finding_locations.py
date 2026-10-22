"""Resolve only explicitly referenced facts to immutable project source windows."""

from pathlib import Path

from .contracts import AnalysisError, canonical
from .source_context import source_projection


def source_points(source):
    if not isinstance(source, dict):
        return []
    values = []
    for role in ("expansion", "spelling", "location"):
        point = source.get(role)
        if isinstance(point, dict) and isinstance(point.get("line"), int):
            values.append((role, point, source.get(role + "_end")))
    if not values and isinstance(source.get("line"), int):
        values.append(("location", source, None))
    if not values:
        values.extend(("inline", point, None) for point in source.get("inline_chain", [])
                      if isinstance(point, dict) and isinstance(point.get("line"), int))
    return values


def locations_for_source(source, record, snapshots, output_root, request, source_root=None):
    locations = []
    for role, point, end in source_points(source):
        file = point.get("file") or point.get("path")
        # Missing file identity is not evidence that a coordinate belongs to the main TU.
        if not file or point["line"] < 1 or not isinstance(point.get("column"), int) or point["column"] < 1:
            continue
        if source_root is not None:
            candidate = Path(file)
            if not candidate.is_absolute() and point.get("directory"):
                candidate = Path(point["directory"]) / candidate
            for mapping in sorted(record.get("source_path_map", []), key=lambda item: -len(item["from"])):
                if not candidate.is_absolute() or mapping["to"] != ".":
                    continue
                try:
                    relative = candidate.relative_to(Path(mapping["from"]))
                except ValueError:
                    continue
                candidate = Path(source_root) / relative
                break
            if not candidate.is_absolute():
                candidate = Path(source_root) / candidate
            try:
                file = candidate.resolve().relative_to(Path(source_root).resolve()).as_posix()
            except ValueError:
                continue
        snapshot = next((item for item in snapshots.values() if item.get("sourcePath") == file), None)
        if snapshot is None:
            continue
        start = {"line": point["line"], "column": point["column"]}
        if not isinstance(end, dict) or (end.get("file") or end.get("path") or point.get("file") or file) != (point.get("file") or file):
            end = {"line": start["line"], "column": start["column"] + 1}
        finish = {key: end.get(key) for key in ("line", "column")}
        if finish == start:
            finish = {"line": start["line"], "column": start["column"] + 1}
        if any(not isinstance(value, int) for value in finish.values()) or tuple(finish.values()) <= tuple(start.values()):
            continue
        try:
            location = source_projection(file, snapshot["digest"], {"start": start, "end": finish},
                                         snapshot, store_root=output_root,
                                         max_lines=request["budgets"]["context_lines"],
                                         max_characters=request["budgets"]["context_characters"])
        except AnalysisError:
            continue
        locations.append({"role": role, "location": location,
                          "physicalTuId": record["physical_tu_id"]})
    return unique_locations(locations)


def unique_locations(values):
    unique = {(value["role"], canonical(value["location"]), value["physicalTuId"]): value for value in values}
    return sorted(unique.values(), key=lambda value: (
        value["role"] != "expansion", value["location"]["file"],
        value["location"]["span"]["start"]["line"], value["location"]["span"]["start"]["column"],
        value["role"], value["physicalTuId"]))


def candidate_locations(candidate, source_facts, scope, snapshots, output_root, request, source_root=None):
    selected = set(candidate.get("physical_tu_ids", []))
    wanted = set(candidate.get("node_ids", [])) | set(candidate.get("relation_ids", []))
    locations = []
    for record in scope["records"]:
        if record["physical_tu_id"] not in selected:
            continue
        facts = source_facts.get(record["record_id"], {})
        for item in [*facts.get("nodes", []), *facts.get("relations", [])]:
            if item.get("id") in wanted:
                locations.extend(locations_for_source(item.get("source"), record, snapshots, output_root, request, source_root))
    return unique_locations(locations)


def assessment_locations(assessment, scope, module_by_record, data, snapshots, output_root, request, read_json, source_root=None):
    references = [item for item in assessment.get("evidence", []) if isinstance(item, dict)
                  and item.get("artifact_key") and item.get("id")]
    # A6 references a P4 protocol; follow its events in this Scope's graph, never scan unrelated graphs.
    protocol_id = assessment.get("p4_protocol_id")
    if protocol_id:
        graph_dir = Path(data) / "analysis" / scope["target_id"] / "publication" / "graphs"
        for path in sorted(graph_dir.glob("*.json")):
            graph = read_json(path)
            for item in graph.get("assessments", []):
                if item.get("protocol_id") == protocol_id:
                    references.extend(ref for ref in item.get("evidence", []) if isinstance(ref, dict))
    locations = []
    for record in scope["records"]:
        mapping = module_by_record.get(record["record_id"], {})
        key = mapping.get("artifact_key")
        wanted = {item["id"] for item in references if key and item.get("artifact_key") == key}
        if not wanted:
            continue
        path = Path(data) / "facts" / f"{key}.json"
        if not path.is_file():
            continue
        module = read_json(path)
        for event in module.get("events", []):
            if event.get("id") in wanted:
                locations.extend(locations_for_source(event.get("source"), record, snapshots, output_root, request, source_root))
    return unique_locations(locations)
