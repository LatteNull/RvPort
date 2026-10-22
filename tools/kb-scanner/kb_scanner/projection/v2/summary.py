from __future__ import annotations

from ...core import AssessmentSnapshot, WorkspaceSnapshot
from .models import Finding, Summary


class V2SummaryReducer:
    def reduce(self, workspace: WorkspaceSnapshot, findings: tuple[Finding, ...], assessments: AssessmentSnapshot, *, input_complete: bool) -> Summary:
        hints = sum(item.conclusion.severity == "info" for item in findings)
        inactive = sum(item.conclusion.status == "inactive" for item in findings)
        blocking = sum(item.conclusion.blocking for item in findings)
        readiness = _readiness(assessments, findings, input_complete)
        status = "complete" if input_complete else "partial"
        reasons = () if input_complete else ("missing_input",)
        gaps = sum(
            bool((item.conclusion.extensions or {}).get("org.rvport.kb-scanner.classification", {}).get("portabilityGap"))
            for item in findings
        ) if input_complete else None
        return Summary(
            files=len(workspace.files), findings=len(findings), issues=len(findings) - hints, hints=hints,
            blocking=blocking, portabilityGaps=gaps, inactiveOrGuarded=inactive,
            referenceSources=0, references=0, readiness=readiness, status=status, reasonCodes=reasons,
        )


def _readiness(assessments, findings, complete):
    projects = [item for item in assessments.assessments if item.kind == "project_migration_state"]
    if not complete:
        return "unknown"
    if projects:
        state = projects[0].state
        if state in {"riscv_blocked", "x86_only"}:
            return "x86_only"
        if state in {"ready", "riscv_ready"}:
            return "ready"
        return "provisional"
    return "provisional" if findings else "unknown"
