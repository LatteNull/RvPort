package cn.rvport.backend.report;

import java.util.Map;

public record ReportInputSummaryResponse(
        long total,
        long confirmed,
        long candidate,
        long excluded,
        long lowCandidate,
        Map<String, Long> byStatus,
        Map<String, Long> bySourceType,
        Map<String, Long> byRiskLevel
) {
    public static ReportInputSummaryResponse empty() {
        return new ReportInputSummaryResponse(0, 0, 0, 0, 0, Map.of(), Map.of(), Map.of());
    }
}
