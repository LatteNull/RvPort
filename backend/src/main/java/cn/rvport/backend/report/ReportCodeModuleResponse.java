package cn.rvport.backend.report;

import java.util.List;
import java.util.Map;

public record ReportCodeModuleResponse(
        String moduleKey,
        String moduleName,
        String basis,
        String confidence,
        List<String> relatedModuleKeys,
        long fileCount,
        long findingCount,
        long findingTypeCount,
        String highestRisk,
        Map<String, Long> riskCounts,
        Map<String, Long> typeCounts
) {
}
