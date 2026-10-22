package cn.rvport.backend.source;

import java.util.Map;

public record DiffSummaryResponse(
        long total,
        Map<String, Long> byStatus,
        Map<String, Long> bySourceType,
        Map<String, Long> bySeverity
) {
    public static DiffSummaryResponse empty() {
        return new DiffSummaryResponse(0, Map.of(), Map.of(), Map.of());
    }
}
