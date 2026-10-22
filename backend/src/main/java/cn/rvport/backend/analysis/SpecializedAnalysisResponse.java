package cn.rvport.backend.analysis;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record SpecializedAnalysisResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        SpecializedAnalyzerType analyzerType,
        UUID sourceRevisionId,
        UUID buildRunId,
        String artifactSetId,
        SpecializedAnalysisMode analysisMode,
        String bcStatus,
        int bcPlannedCount,
        int bcUsableCount,
        int bcFailedCount,
        int astOnlyCount,
        String bcDegradationReason,
        Long environmentConfigVersion,
        String toolVersion,
        SpecializedAnalysisStatus status,
        String verdict,
        Integer exitCode,
        Map<String, Object> summary,
        int findingCount,
        int candidateCount,
        int diagnosticCount,
        boolean currentSourceRevision,
        List<String> staleReasons,
        UUID requestArtifactId,
        UUID resultJsonArtifactId,
        UUID resultHtmlArtifactId,
        UUID auditBundleArtifactId,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
    public static SpecializedAnalysisResponse from(SpecializedAnalysisRunView run, UUID activeSourceRevisionId) {
        boolean current = java.util.Objects.equals(run.sourceRevisionId(), activeSourceRevisionId);
        return new SpecializedAnalysisResponse(run.id(), run.projectId(), run.taskId(), run.analyzerType(),
                run.sourceRevisionId(), run.buildRunId(), run.artifactSetId(), run.analysisMode(), run.bcStatus(),
                run.bcPlannedCount(), run.bcUsableCount(), run.bcFailedCount(),
                Math.max(0, run.bcPlannedCount() - run.bcUsableCount()), run.bcDegradationReason(),
                run.environmentConfigVersion(),
                run.toolVersion(), run.status(), run.verdict(), run.exitCode(), run.summary(), run.findingCount(),
                run.candidateCount(), run.diagnosticCount(), current,
                current ? List.of() : List.of("SOURCE_REVISION_CHANGED"), run.requestArtifactId(),
                run.resultJsonArtifactId(), run.resultHtmlArtifactId(), run.auditBundleArtifactId(), run.startedAt(),
                run.finishedAt(), run.createdAt());
    }
}
