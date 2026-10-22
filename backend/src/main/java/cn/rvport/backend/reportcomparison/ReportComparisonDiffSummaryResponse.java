package cn.rvport.backend.reportcomparison;

import java.util.Map;

public record ReportComparisonDiffSummaryResponse(
        long total,
        Map<String, Long> byStatus,
        Map<String, Long> bySourceType,
        Map<String, Long> bySeverity,
        Map<String, Long> byMatchConfidence
) {
    public static ReportComparisonDiffSummaryResponse empty() {
        return new ReportComparisonDiffSummaryResponse(0, Map.of(), Map.of(), Map.of(), Map.of());
    }
}
