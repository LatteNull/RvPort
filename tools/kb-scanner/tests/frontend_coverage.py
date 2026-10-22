from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CoverageGateResult:
    line_percent: float
    branch_percent: float
    missing_modules: tuple[str, ...]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate_frontend_coverage(
    payload: dict[str, Any],
    required_modules: tuple[str, ...],
    *,
    line_threshold: float,
    branch_threshold: float,
    enforce_module_thresholds: bool = False,
) -> CoverageGateResult:
    totals = payload.get("totals", {})
    statement_count = int(totals.get("num_statements", 0))
    covered_lines = int(totals.get("covered_lines", 0))
    branch_count = int(totals.get("num_branches", 0))
    covered_branches = int(totals.get("covered_branches", 0))
    line_percent = 100.0 if statement_count == 0 else covered_lines * 100.0 / statement_count
    branch_percent = 100.0 if branch_count == 0 else covered_branches * 100.0 / branch_count

    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    missing_modules = []
    failures = []
    for module in required_modules:
        normalized = module.replace("\\", "/")
        details = normalized_files.get(normalized)
        summary = details.get("summary", {}) if isinstance(details, dict) else {}
        if not details or int(summary.get("num_statements", 0)) == 0 or int(summary.get("covered_lines", 0)) == 0:
            missing_modules.append(normalized)
            continue
        if enforce_module_thresholds:
            module_statements = int(summary.get("num_statements", 0))
            module_lines = int(summary.get("covered_lines", 0)) * 100.0 / module_statements
            module_branches_count = int(summary.get("num_branches", 0))
            module_branches = (
                100.0
                if module_branches_count == 0
                else int(summary.get("covered_branches", 0)) * 100.0 / module_branches_count
            )
            if module_lines < line_threshold:
                failures.append(f"{normalized} line coverage {module_lines:.2f}% is below {line_threshold:.2f}%")
            if module_branches < branch_threshold:
                failures.append(f"{normalized} branch coverage {module_branches:.2f}% is below {branch_threshold:.2f}%")

    if line_percent < line_threshold:
        failures.append(f"line coverage {line_percent:.2f}% is below {line_threshold:.2f}%")
    if branch_percent < branch_threshold:
        failures.append(f"branch coverage {branch_percent:.2f}% is below {branch_threshold:.2f}%")
    if missing_modules:
        failures.append("modules without executed lines: " + ", ".join(missing_modules))
    return CoverageGateResult(
        line_percent=line_percent,
        branch_percent=branch_percent,
        missing_modules=tuple(missing_modules),
        failures=tuple(failures),
    )
