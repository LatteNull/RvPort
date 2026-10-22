from pathlib import Path

import pytest

from memory_order_analyzer.contracts import AnalysisError, file_hash
from memory_order_analyzer.execution import OutputStore
from memory_order_analyzer.source_context import (
    build_context, resolve_source, snapshot_source, source_projection,
    unavailable_context, validate_project_path,
)


def test_project_paths_and_resolved_boundary(tmp_path):
    source = tmp_path / "src/a.c"; source.parent.mkdir(); source.write_text("int x;\n", encoding="utf-8")
    assert validate_project_path("src/a.c") == "src/a.c"
    assert resolve_source(tmp_path, "src/a.c") == source.resolve()
    for value in ("../a.c", "/a.c", "C:/a.c", r"src\a.c", "./a.c"):
        with pytest.raises(AnalysisError, match="project-relative"):
            validate_project_path(value)
    with pytest.raises(AnalysisError, match="unavailable"):
        resolve_source(tmp_path, "src/missing.c")
    link = tmp_path / "src/link.c"
    try:
        link.symlink_to(source)
    except OSError:
        pass
    else:
        with pytest.raises(AnalysisError, match="symbolic"):
            resolve_source(tmp_path, "src/link.c")
    for value in ("", "a/./b", "D:relative"):
        with pytest.raises(AnalysisError):
            validate_project_path(value)


def test_snapshot_is_content_addressed_deduplicated_and_rejects_changes(tmp_path):
    root = tmp_path / "project"; root.mkdir()
    source = root / "a.c"; source.write_text("α\nβ\n", encoding="utf-8")
    digest = file_hash(source)
    store = OutputStore(tmp_path / "output")
    first = snapshot_source(store, root, "a.c", digest)
    second = snapshot_source(store, root, "a.c", digest)
    assert first == second and (store.root / first["path"]).is_file()
    source.write_text("changed\n", encoding="utf-8")
    with pytest.raises(AnalysisError, match="changed"):
        snapshot_source(store, root, "a.c", digest)
    snapshot = store.root / first["path"]
    snapshot.write_text("corrupt", encoding="utf-8")
    source.write_text("α\nβ\n", encoding="utf-8")
    with pytest.raises(AnalysisError, match="snapshot digest"):
        snapshot_source(store, root, "a.c", digest)


def test_context_line_numbers_highlights_unicode_and_boundaries(tmp_path):
    source = tmp_path / "source"; source.write_text("one\n二三\nthree\nfour\n", encoding="utf-8")
    span = {"start": {"line": 2, "column": 1}, "end": {"line": 3, "column": 3}}
    value = build_context(source, span, before=1, after=1)
    assert value["status"] == "complete"
    assert [item["line"] for item in value["lines"]] == [1, 2, 3, 4]
    assert value["highlights"] == [{"line": 2, "startColumn": 1, "endColumn": 3},
                                    {"line": 3, "startColumn": 1, "endColumn": 3}]
    for broken in (
        {"start": {"line": 2, "column": 1}, "end": {"line": 2, "column": 1}},
        {"start": {"line": 9, "column": 1}, "end": {"line": 9, "column": 2}},
        {"start": {"line": 1, "column": 99}, "end": {"line": 2, "column": 1}},
    ):
        with pytest.raises(AnalysisError, match="span"):
            build_context(source, broken)
    with pytest.raises(AnalysisError, match="budget"):
        build_context(source, span, max_lines=0)


def test_context_truncation_unavailable_and_projection(tmp_path):
    source = tmp_path / "source"; source.write_text("\n".join(f"line-{i}" for i in range(300)), encoding="utf-8")
    span = {"start": {"line": 150, "column": 1}, "end": {"line": 151, "column": 3}}
    context = build_context(source, span, before=100, after=100, max_lines=8, max_characters=30)
    assert context["status"] == "partial" and context["budget"]["truncated"]
    unavailable = unavailable_context("no-debug")
    assert unavailable["status"] == "unavailable" and unavailable["reasonCodes"] == ["no-debug"]
    digest = file_hash(source)
    store = OutputStore(tmp_path / "store")
    with store.temporary() as temporary:
        staged = temporary / "source"; staged.write_bytes(source.read_bytes())
        store.publish(staged, f"source-snapshots/{digest}.source")
    snapshot = {"kind": "SourceSnapshot", "id": digest, "digest": digest,
                "path": f"source-snapshots/{digest}.source", "sourcePath": "src/a.c"}
    projected = source_projection("src/a.c", digest, span, snapshot, store_root=store.root,
                                  max_lines=8, max_characters=30)
    assert projected["context"]["status"] == "partial"
    missing = source_projection("src/a.c", "f" * 64, span, snapshot, store_root=store.root)
    assert missing["context"]["status"] == "unavailable"
    with pytest.raises(AnalysisError, match="unavailable"):
        build_context(tmp_path / "missing", span)
    source.write_bytes(b"\xff")
    with pytest.raises(AnalysisError, match="unavailable"):
        build_context(source, {"start": {"line": 1, "column": 1},
                               "end": {"line": 1, "column": 2}})


def test_context_required_range_and_character_edges(tmp_path):
    source = tmp_path / "many"
    source.write_text("\n".join("abcdef" for _ in range(10)), encoding="utf-8")
    span = {"start": {"line": 2, "column": 1}, "end": {"line": 8, "column": 4}}
    value = build_context(source, span, before=5, after=5, max_lines=3, max_characters=7)
    assert value["status"] == "partial" and len(value["lines"]) <= 2
    assert value["budget"]["truncated"]
    projected = source_projection(
        "src/a.c", file_hash(source), span,
        {"path": "missing", "digest": file_hash(source)}, store_root=tmp_path,
    )
    assert projected["context"]["reasonCodes"] == ["snapshot-unavailable"]
