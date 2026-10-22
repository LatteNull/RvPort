package cn.rvport.backend.modelprofile;

import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeRunsRecord;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.jooq.JSONB;

public record ActiveAgentProbeRunResponse(
        UUID runId,
        String status,
        List<AgentRuntimeSummaryResponse> agentRuntimes,
        OffsetDateTime createdAt
) {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<List<AgentRuntimeSummaryResponse>> RUNTIMES_TYPE = new TypeReference<>() {
    };

    static ActiveAgentProbeRunResponse from(ModelProfileAgentProbeRunsRecord record) {
        if (record == null) {
            return null;
        }
        return new ActiveAgentProbeRunResponse(
                record.getId(),
                record.getStatus(),
                jsonbToRuntimes(record.getSelectedAgentRuntimes()),
                record.getCreatedAt()
        );
    }

    private static List<AgentRuntimeSummaryResponse> jsonbToRuntimes(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value.data(), RUNTIMES_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }
}
