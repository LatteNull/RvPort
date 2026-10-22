package cn.rvport.backend.report;

import java.util.Map;
import java.util.UUID;

public record ReportCodeFindingResponse(
        UUID id,
        UUID sourceRefId,
        String issueTitle,
        String riskLevel,
        String findingType,
        String relativePath,
        Integer lineStart,
        Integer lineEnd,
        Integer columnStart,
        Integer columnEnd,
        String symbol,
        boolean locationAvailable,
        String recommendation,
        Map<String, Object> sourceDetail
) {
}
