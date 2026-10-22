from __future__ import annotations

from ..core.context import ScanRequest
from ..core.results import CompletionStatus, PipelineResult
from .profile import ApplicationProfile


class ScanApplication:
    __slots__ = ("_profile",)

    def __init__(self, profile: ApplicationProfile) -> None:
        self._profile = profile

    def run(self, request: ScanRequest) -> PipelineResult:
        context_result = self._profile.context_factory.build(request)
        if context_result.value is None:
            exit_code = 2 if context_result.status is CompletionStatus.FAILED else 1
            return PipelineResult(
                success=False,
                exit_code=exit_code,
                status=context_result.status,
                diagnostics=context_result.diagnostics,
            )
        result = self._profile.runner.run(context_result.value, context_result.diagnostics)
        if context_result.status is CompletionStatus.PARTIAL and result.status is CompletionStatus.COMPLETE:
            return PipelineResult(
                success=result.success,
                exit_code=result.exit_code,
                status=CompletionStatus.PARTIAL,
                diagnostics=result.diagnostics,
                artifacts=result.artifacts,
            )
        return result
