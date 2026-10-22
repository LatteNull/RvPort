"""保守状态聚合与固定退出码。"""

from __future__ import annotations

EXIT_CODES = {"complete": 0, "invalid_request": 2, "failed": 3, "partial": 4, "internal_error": 5}


def aggregate_status(
    *,
    planned: int,
    completed: int,
    failed: int,
    unknown: int,
    invalid: bool = False,
    internal: bool = False,
) -> str:
    if internal:
        return "internal_error"
    if invalid:
        return "invalid_request"
    if planned == 0 or completed == 0:
        return "failed"
    if failed > 0 or unknown > 0 or completed < planned:
        return "partial"
    return "complete"


def exit_code(status: str) -> int:
    try:
        return EXIT_CODES[status]
    except KeyError as exc:
        raise ValueError("unknown_scan_status") from exc
