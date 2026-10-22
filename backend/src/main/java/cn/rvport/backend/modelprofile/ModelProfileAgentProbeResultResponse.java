package cn.rvport.backend.modelprofile;

import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeResultsRecord;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;

public record ModelProfileAgentProbeResultResponse(
        UUID id,
        UUID runId,
        UUID modelProfileId,
        UUID agentRuntimeId,
        String agentType,
        String status,
        Boolean basicAvailable,
        Boolean agentCompatible,
        List<Map<String, Object>> checks,
        Map<String, Object> details,
        String errorCode,
        String message,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        Long durationMs,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<List<Map<String, Object>>> LIST_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    static ModelProfileAgentProbeResultResponse from(ModelProfileAgentProbeResultsRecord record) {
        return new ModelProfileAgentProbeResultResponse(
                record.getId(),
                record.getRunId(),
                record.getModelProfileId(),
                record.getAgentRuntimeId(),
                record.getAgentType(),
                record.getStatus(),
                record.getBasicAvailable(),
                record.getAgentCompatible(),
                jsonbToList(record.getChecks()),
                jsonbToMap(record.getDetails()),
                record.getErrorCode(),
                record.getMessage(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getDurationMs(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }

    private static List<Map<String, Object>> jsonbToList(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value.data(), LIST_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private static Map<String, Object> jsonbToMap(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return Map.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }
}
