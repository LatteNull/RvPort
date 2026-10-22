package cn.rvport.backend.report;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ReportOrganizedInput(
        UUID id,
        UUID inputId,
        String sourceType,
        String riskLevel,
        String moduleKey,
        String moduleName,
        String moduleBasis,
        String moduleConfidence,
        List<String> relatedModuleKeys,
        String fileKey,
        String relativePath,
        String findingType,
        Integer lineStart,
        Integer lineEnd,
        Integer columnStart,
        Integer columnEnd,
        String symbol,
        String sourceContentHash,
        boolean locationAvailable,
        Map<String, Object> snapshot
) {
}
