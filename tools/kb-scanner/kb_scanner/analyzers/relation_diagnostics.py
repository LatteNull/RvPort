from __future__ import annotations

from ..core import Diagnostic, DiagnosticSeverity, Evidence


def relation_diagnostic(
    code: str,
    evidence: Evidence,
    reason: str,
    relation_kind: str,
    *,
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="analyzer.evidence-graph",
        severity=severity,
        message=f"Evidence Graph retained partial relation: {reason}",
        location=evidence.location.start if evidence.location else None,
        producer="evidence-graph-analyzer",
        details={"evidenceId": evidence.id, "reason": reason, "relationKind": relation_kind},
    )
