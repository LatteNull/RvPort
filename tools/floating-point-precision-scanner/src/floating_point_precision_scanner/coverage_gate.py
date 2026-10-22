"""对同一 coverage JSON 执行整体和受影响模块双指标门禁。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CoverageMetrics:
    lines: float
    branches: float


def _ratio(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered * 100.0 / total


def metrics_for(files: Iterable[Mapping[str, Any]]) -> CoverageMetrics:
    covered_lines = total_lines = covered_branches = total_branches = 0
    for item in files:
        summary = item["summary"]
        covered_lines += int(summary["covered_lines"])
        total_lines += int(summary["num_statements"])
        covered_branches += int(summary.get("covered_branches", 0))
        total_branches += int(summary.get("num_branches", 0))
    return CoverageMetrics(
        _ratio(covered_lines, total_lines), _ratio(covered_branches, total_branches)
    )


def evaluate(
    document: Mapping[str, Any], affected: tuple[str, ...], minimum: float = 90.0
) -> tuple[bool, dict[str, CoverageMetrics]]:
    file_map = document.get("files")
    if not isinstance(file_map, Mapping) or not file_map:
        raise ValueError("coverage_json_has_no_files")
    all_files = [value for value in file_map.values() if isinstance(value, Mapping)]
    affected_groups: dict[str, list[Mapping[str, Any]]] = {}
    for marker in affected:
        normalized = marker.replace(".", "/")
        matched = [
            value
            for path, value in file_map.items()
            if isinstance(value, Mapping) and normalized in str(path).replace("\\", "/")
        ]
        if not matched:
            raise ValueError("affected_modules_not_found")
        affected_groups[marker] = matched
    affected_files = [item for values in affected_groups.values() for item in values]
    metrics = {
        "overall": metrics_for(all_files),
        "affected": metrics_for(affected_files),
        **{f"affected:{marker}": metrics_for(values) for marker, values in affected_groups.items()},
    }
    passed = all(value.lines >= minimum and value.branches >= minimum for value in metrics.values())
    return passed, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--affected", action="append", required=True)
    parser.add_argument("--minimum", type=float, default=90.0)
    args = parser.parse_args(argv)
    document = json.loads(args.report.read_text(encoding="utf-8"))
    passed, metrics = evaluate(document, tuple(args.affected), args.minimum)
    print(
        json.dumps(
            {
                name: {"lines": value.lines, "branches": value.branches}
                for name, value in metrics.items()
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
