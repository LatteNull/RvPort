"""Immutable source snapshots and bounded, line-accurate code-context projection."""

from pathlib import Path, PurePosixPath
import shutil

from .contracts import AnalysisError, file_hash
from .execution import OutputStore


def validate_project_path(value):
    text = str(value)
    path = PurePosixPath(text)
    raw_parts = text.split("/")
    if (not text or path.is_absolute() or ".." in raw_parts or "." in raw_parts or text.startswith("./") or
            "\\" in text or (path.parts and ":" in path.parts[0])):
        raise AnalysisError("path_unsafe", f"Source path must be project-relative POSIX: {value}")
    return text


def resolve_source(root, relative):
    root = Path(root).resolve()
    relative = validate_project_path(relative)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise AnalysisError("path_unsafe", f"Source path contains a symbolic link: {relative}")
    resolved = current.resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise AnalysisError("source_unavailable", f"Source is unavailable inside the declared root: {relative}")
    return resolved


def snapshot_source(store, root, relative, expected_digest):
    source = resolve_source(root, relative)
    if file_hash(source) != expected_digest:
        raise AnalysisError("source_digest_mismatch", f"Source changed before snapshot: {relative}")
    with store.temporary() as temporary:
        staged = temporary / "source"
        # A hard link is not a snapshot: later workspace writes would mutate the
        # supposedly immutable analysis-time source artifact.
        shutil.copyfile(source, staged)
        if file_hash(staged) != expected_digest:
            raise AnalysisError("source_digest_mismatch", f"Source changed while snapshotting: {relative}")
        destination = store.path(f"source-snapshots/{expected_digest}.source")
        if destination.exists():
            if file_hash(destination) != expected_digest:
                raise AnalysisError("snapshot_corrupt", f"Existing snapshot digest mismatch: {expected_digest}")
        else:
            store.publish(staged, f"source-snapshots/{expected_digest}.source")
    return {"kind": "SourceSnapshot", "id": expected_digest, "digest": expected_digest,
            "path": f"source-snapshots/{expected_digest}.source", "sourcePath": relative}


def unavailable_context(code="source-unavailable", *, before=20, after=20,
                        max_lines=256, max_characters=65536):
    return {"status": "unavailable", "reasonCodes": [code], "lines": [], "highlights": [],
            "budget": {"beforeLines": before, "afterLines": after, "maxLines": max_lines,
                       "maxCharacters": max_characters, "truncated": False}}


def _validate_span(lines, span):
    start, end = span["start"], span["end"]
    if (start["line"], start["column"]) >= (end["line"], end["column"]):
        raise AnalysisError("span_invalid", "Source span must be nonempty and end-exclusive")
    if start["line"] > len(lines) or end["line"] > len(lines):
        raise AnalysisError("span_invalid", "Source span lies outside the snapshot")
    if start["column"] > len(lines[start["line"] - 1]) + 1 or end["column"] > len(lines[end["line"] - 1]) + 1:
        raise AnalysisError("span_invalid", "Source span column lies outside the snapshot")


def build_context(snapshot_path, span, *, before=20, after=20, max_lines=256,
                  max_characters=65536):
    if not 1 <= max_lines <= 256 or not 1 <= max_characters <= 65536 or before < 0 or after < 0:
        raise AnalysisError("context_budget", "Invalid source context budget")
    try:
        text = Path(snapshot_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AnalysisError("source_unavailable", f"Source context unavailable: {snapshot_path}") from exc
    lines = text.splitlines()
    _validate_span(lines, span)
    first, last = span["start"]["line"], span["end"]["line"]
    if last > first and span["end"]["column"] == 1:
        last -= 1
    selected_first = max(1, first - before)
    selected_last = min(len(lines), last + after)
    required = last - first + 1
    if required > max_lines:
        selected_first, selected_last = first, first + max_lines - 1
    elif selected_last - selected_first + 1 > max_lines:
        spare = max_lines - required
        selected_first = max(1, first - min(before, spare // 2))
        selected_last = min(len(lines), selected_first + max_lines - 1)
        selected_first = max(1, selected_last - max_lines + 1)
    projected, used = [], 0
    truncated = selected_first > max(1, first - before) or selected_last < min(len(lines), last + after)
    for number in range(selected_first, selected_last + 1):
        raw = lines[number - 1]
        encoded = raw.encode("utf-8")
        remaining = max_characters - used
        if remaining <= 0:
            truncated = True
            break
        if len(encoded) > remaining:
            raw = encoded[:remaining].decode("utf-8", errors="ignore")
            truncated = True
        projected.append({"line": number, "text": raw})
        used += len(raw.encode("utf-8"))
        if len(encoded) > remaining:
            break
    available_lines = {item["line"]: item["text"] for item in projected}
    highlights = []
    for number in range(first, last + 1):
        if number not in available_lines:
            truncated = True
            continue
        start = span["start"]["column"] if number == first else 1
        end = span["end"]["column"] if number == span["end"]["line"] else len(lines[number - 1]) + 1
        end = min(end, len(available_lines[number]) + 1)
        if end > start:
            highlights.append({"line": number, "startColumn": start, "endColumn": end})
        else:
            truncated = True
    reasons = ["context-truncated"] if truncated else []
    return {"status": "partial" if truncated else "complete", "reasonCodes": reasons,
            "lines": projected, "highlights": highlights,
            "budget": {"beforeLines": before, "afterLines": after, "maxLines": max_lines,
                       "maxCharacters": max_characters, "truncated": truncated}}


def source_projection(relative, digest, span, snapshot, *, store_root, **budgets):
    validate_project_path(relative)
    path = Path(store_root) / snapshot["path"]
    if not path.is_file() or file_hash(path) != digest or snapshot["digest"] != digest:
        context = unavailable_context("snapshot-unavailable", **budgets)
    else:
        try:
            context = build_context(path, span, **budgets)
        except AnalysisError as exc:
            context = unavailable_context(exc.code, **budgets)
    return {"file": relative, "span": span, "sourceSha256": digest,
            "snapshot": snapshot, "context": context}
