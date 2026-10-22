package cn.rvport.backend.kb.ai;

import java.util.Map;
import java.util.UUID;

public record KbAiExtensionReadinessResponse(
        boolean ready,
        String reason,
        UUID kbScanRunId,
        long findingCount,
        boolean modelConfigured,
        Map<String, Object> model
) {
}
