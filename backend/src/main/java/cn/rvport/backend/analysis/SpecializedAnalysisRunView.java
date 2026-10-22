package cn.rvport.backend.analysis;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record SpecializedAnalysisRunView(
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
        String bcDegradationReason,
        Long environmentConfigVersion,
        String toolVersion,
        String requestSchemaVersion,
        String resultSchemaVersion,
        String policyId,
        SpecializedAnalysisStatus status,
        String verdict,
        Integer exitCode,
        Map<String, Object> summary,
        UUID requestArtifactId,
        UUID resultJsonArtifactId,
        UUID resultHtmlArtifactId,
        UUID auditBundleArtifactId,
        int findingCount,
        int candidateCount,
        int diagnosticCount,
        UUID createdBy,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public SpecializedAnalysisRunView(
            UUID id, UUID projectId, UUID taskId, SpecializedAnalyzerType analyzerType,
            UUID sourceRevisionId, UUID buildRunId, String artifactSetId, Long environmentConfigVersion,
            String toolVersion, String requestSchemaVersion, String resultSchemaVersion, String policyId,
            SpecializedAnalysisStatus status, String verdict, Integer exitCode, Map<String, Object> summary,
            UUID requestArtifactId, UUID resultJsonArtifactId, UUID resultHtmlArtifactId, UUID auditBundleArtifactId,
            int findingCount, int candidateCount, int diagnosticCount, UUID createdBy,
            OffsetDateTime startedAt, OffsetDateTime finishedAt, OffsetDateTime createdAt, OffsetDateTime updatedAt
    ) {
        this(id, projectId, taskId, analyzerType, sourceRevisionId, buildRunId, artifactSetId,
                artifactSetId == null ? SpecializedAnalysisMode.AST_ONLY : SpecializedAnalysisMode.AST_BC_MIXED,
                artifactSetId == null ? "UNKNOWN" : "LEGACY_UNKNOWN", 0, 0, 0,
                artifactSetId == null ? "LEGACY_EVIDENCE_UNKNOWN" : null, environmentConfigVersion, toolVersion,
                requestSchemaVersion, resultSchemaVersion, policyId, status, verdict, exitCode, summary,
                requestArtifactId, resultJsonArtifactId, resultHtmlArtifactId, auditBundleArtifactId,
                findingCount, candidateCount, diagnosticCount, createdBy, startedAt, finishedAt, createdAt, updatedAt);
    }
}
