package cn.rvport.backend.agentruntime;

import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;

public record AgentRuntimeResponse(
        UUID id,
        String agentType,
        String name,
        boolean enabled,
        String executablePath,
        List<String> defaultArgs,
        Map<String, Object> config,
        String lastProbeStatus,
        String lastProbeMessage,
        Map<String, Object> lastProbeDetails,
        OffsetDateTime lastProbeAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<List<String>> LIST_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    public static AgentRuntimeResponse from(AgentRuntimesRecord record) {
        return new AgentRuntimeResponse(
                record.getId(),
                record.getAgentType(),
                record.getName(),
                Boolean.TRUE.equals(record.getEnabled()),
                record.getExecutablePath(),
                jsonbToList(record.getDefaultArgs()),
                jsonbToMap(record.getConfig()),
                record.getLastProbeStatus(),
                record.getLastProbeMessage(),
                jsonbToMap(record.getLastProbeDetails()),
                record.getLastProbeAt(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }

    private static List<String> jsonbToList(JSONB value) {
        return jsonToList(value == null ? null : value.data());
    }

    private static List<String> jsonToList(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value, LIST_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private static Map<String, Object> jsonbToMap(JSONB value) {
        return jsonToMap(value == null ? null : value.data());
    }

    private static Map<String, Object> jsonToMap(String value) {
        if (value == null || value.isBlank()) {
            return Map.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value, MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }
}
