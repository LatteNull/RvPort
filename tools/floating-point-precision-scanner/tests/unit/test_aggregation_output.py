from __future__ import annotations

import json
from pathlib import Path

import pytest

from floating_point_precision_scanner.aggregation import aggregate_status, exit_code
from floating_point_precision_scanner.output import serialize_json, write_atomic


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"planned": 1, "completed": 1, "failed": 0, "unknown": 0}, "complete"),
        ({"planned": 2, "completed": 1, "failed": 1, "unknown": 0}, "partial"),
        ({"planned": 1, "completed": 1, "failed": 0, "unknown": 1}, "partial"),
        ({"planned": 1, "completed": 0, "failed": 1, "unknown": 0}, "failed"),
        ({"planned": 0, "completed": 0, "failed": 0, "unknown": 0}, "failed"),
        (
            {"planned": 1, "completed": 1, "failed": 0, "unknown": 0, "invalid": True},
            "invalid_request",
        ),
        (
            {"planned": 1, "completed": 1, "failed": 0, "unknown": 0, "internal": True},
            "internal_error",
        ),
    ],
)
def test_aggregate_status(kwargs: dict[str, int | bool], status: str) -> None:
    assert aggregate_status(**kwargs) == status


def test_exit_codes_and_unknown() -> None:
    assert [
        exit_code(item)
        for item in ["complete", "invalid_request", "failed", "partial", "internal_error"]
    ] == [0, 2, 3, 4, 5]
    with pytest.raises(ValueError, match="unknown"):
        exit_code("other")


def test_deterministic_serialization() -> None:
    assert serialize_json({"b": 2, "a": "中"}) == serialize_json({"a": "中", "b": 2})
    assert serialize_json({"a": 1}).endswith(b"\n")


def test_atomic_write_replaces_complete_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "result.json"
    write_atomic({"value": 1}, target)
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 1}
    write_atomic({"value": 2}, target)
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 2}
    assert list(target.parent.glob("*.tmp")) == []


def test_atomic_write_preserves_old_file_on_sync_failure(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")

    def fail(_: int) -> None:
        raise OSError("sync failed")

    with pytest.raises(OSError, match="sync"):
        write_atomic({"value": 2}, target, sync=fail)
    assert target.read_text(encoding="utf-8") == "old"


def test_atomic_write_preserves_old_file_on_replace_failure(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")

    def fail(_: str, __: str) -> None:
        raise OSError("replace failed")

    with pytest.raises(OSError, match="replace"):
        write_atomic({"value": 2}, target, replace=fail)
    assert target.read_text(encoding="utf-8") == "old"
    assert not any(path.suffix == ".tmp" for path in tmp_path.iterdir())
