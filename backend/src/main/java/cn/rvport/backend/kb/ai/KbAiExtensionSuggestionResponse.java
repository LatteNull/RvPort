package cn.rvport.backend.kb.ai;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbAiExtensionSuggestionResponse(
        UUID id,
        UUID runId,
        UUID findingId,
        String aiSummary,
        String aiSuggestion,
        BigDecimal confidence,
        String actionType,
        Map<String, Object> rawPayload,
        OffsetDateTime createdAt
) {
}
