package cn.rvport.backend.testcomparison;

import cn.rvport.backend.jooq.tables.records.TestComparisonFindingsRecord;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record TestComparisonFindingView(
        UUID id,
        UUID comparisonRunId,
        int sequenceNo,
        String differenceType,
        TestComparisonRiskLevel severity,
        BigDecimal confidence,
        String title,
        String description,
        String sourceSummary,
        String targetSummary,
        String recommendation,
        Map<String, Object> rawPayload,
        OffsetDateTime createdAt
) {
    public static TestComparisonFindingView from(TestComparisonFindingsRecord record, Map<String, Object> rawPayload) {
        return new TestComparisonFindingView(
                record.getId(),
                record.getComparisonRunId(),
                record.getSequenceNo(),
                record.getDifferenceType(),
                TestComparisonRiskLevel.valueOf(record.getSeverity()),
                record.getConfidence(),
                record.getTitle(),
                record.getDescription(),
                record.getSourceSummary(),
                record.getTargetSummary(),
                record.getRecommendation(),
                rawPayload == null ? Map.of() : rawPayload,
                record.getCreatedAt()
        );
    }
}
