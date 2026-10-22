package cn.rvport.backend.testcomparison;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record TestComparisonResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID testBatchId,
        UUID sourceTestRunId,
        UUID targetTestRunId,
        String status,
        String overallStatus,
        String riskLevel,
        BigDecimal confidence,
        String summary,
        String recommendation,
        String unavailableCode,
        String unavailableMessage,
        String errorCode,
        String errorMessage,
        boolean inputTruncated,
        Map<String, Object> inputSummary,
        Map<String, Object> sourceTestStats,
        Map<String, Object> targetTestStats,
        UUID agentOutputArtifactId,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime updatedAt
) {
    public static TestComparisonResponse from(TestComparisonRunView view) {
        return new TestComparisonResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.testBatchId(),
                view.sourceTestRunId(),
                view.targetTestRunId(),
                view.status().name(),
                view.overallStatus() == null ? null : view.overallStatus().name(),
                view.riskLevel() == null ? null : view.riskLevel().name(),
                view.confidence(),
                view.summary(),
                view.recommendation(),
                view.unavailableCode(),
                view.unavailableMessage(),
                view.errorCode(),
                view.errorMessage(),
                view.inputTruncated(),
                view.inputSummary(),
                view.sourceTestStats(),
                view.targetTestStats(),
                view.agentOutputArtifactId(),
                view.createdAt(),
                view.startedAt(),
                view.finishedAt(),
                view.updatedAt()
        );
    }
}
