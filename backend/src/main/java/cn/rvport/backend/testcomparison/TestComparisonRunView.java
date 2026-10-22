package cn.rvport.backend.testcomparison;

import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record TestComparisonRunView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID testBatchId,
        UUID sourceTestRunId,
        UUID targetTestRunId,
        TestComparisonStatus status,
        TestComparisonOverallStatus overallStatus,
        TestComparisonRiskLevel riskLevel,
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
    public static TestComparisonRunView from(
            TestComparisonRunsRecord record,
            Map<String, Object> inputSummary,
            Map<String, Object> sourceTestStats,
            Map<String, Object> targetTestStats
    ) {
        return new TestComparisonRunView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getTestBatchId(),
                record.getSourceTestRunId(),
                record.getTargetTestRunId(),
                TestComparisonStatus.valueOf(record.getStatus()),
                enumOrNull(TestComparisonOverallStatus.class, record.getOverallStatus()),
                enumOrNull(TestComparisonRiskLevel.class, record.getRiskLevel()),
                record.getConfidence(),
                record.getSummary(),
                record.getRecommendation(),
                record.getUnavailableCode(),
                record.getUnavailableMessage(),
                record.getErrorCode(),
                record.getErrorMessage(),
                Boolean.TRUE.equals(record.getInputTruncated()),
                inputSummary == null ? Map.of() : inputSummary,
                sourceTestStats == null ? Map.of() : sourceTestStats,
                targetTestStats == null ? Map.of() : targetTestStats,
                record.getAgentOutputArtifactId(),
                record.getCreatedAt(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getUpdatedAt()
        );
    }

    private static <T extends Enum<T>> T enumOrNull(Class<T> type, String value) {
        return value == null ? null : Enum.valueOf(type, value);
    }
}
