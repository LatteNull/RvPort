package cn.rvport.backend.testcomparison;

import java.math.BigDecimal;
import java.util.Map;

public record TestComparisonParsedFinding(
        String differenceType,
        TestComparisonRiskLevel severity,
        BigDecimal confidence,
        String title,
        String description,
        String sourceSummary,
        String targetSummary,
        String recommendation,
        Map<String, Object> rawPayload
) {
}
