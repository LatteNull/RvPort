package cn.rvport.backend.report;

import java.util.Map;

public record ReportCodeFileResponse(
        String fileKey,
        String relativePath,
        String sourceContentHash,
        boolean contextAvailable,
        long findingCount,
        long findingTypeCount,
        String highestRisk,
        Map<String, Long> riskCounts,
        Map<String, Long> typeCounts
) {
}
