package cn.rvport.backend.kb;

import java.util.Map;
import java.util.UUID;

public record KbFindingInput(
        UUID projectId,
        UUID scanRunId,
        UUID sourceRevisionId,
        String ruleId,
        String category,
        String severity,
        String title,
        String description,
        String filePath,
        Integer lineStart,
        Integer lineEnd,
        String symbol,
        Map<String, Object> evidence,
        String suggestion,
        String fingerprint
) {
}
