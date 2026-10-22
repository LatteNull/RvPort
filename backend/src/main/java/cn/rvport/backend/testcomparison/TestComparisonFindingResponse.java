package cn.rvport.backend.testcomparison;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record TestComparisonFindingResponse(
        UUID id,
        UUID comparisonRunId,
        int sequenceNo,
        String differenceType,
        String severity,
        BigDecimal confidence,
        String title,
        String description,
        String sourceSummary,
        String targetSummary,
        String recommendation,
        Map<String, Object> rawPayload,
        OffsetDateTime createdAt
) {
    public static TestComparisonFindingResponse from(TestComparisonFindingView view) {
        return new TestComparisonFindingResponse(
                view.id(),
                view.comparisonRunId(),
                view.sequenceNo(),
                view.differenceType(),
                view.severity().name(),
                view.confidence(),
                view.title(),
                view.description(),
                view.sourceSummary(),
                view.targetSummary(),
                view.recommendation(),
                view.rawPayload(),
                view.createdAt()
        );
    }
}
