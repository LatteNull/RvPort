package cn.rvport.backend.modelprofile;

import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeRunsRecord;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.jooq.JSONB;

public record ModelProfileAgentProbeRunResponse(
        UUID id,
        UUID modelProfileId,
        String status,
        List<UUID> selectedAgentRuntimeIds,
        List<AgentRuntimeSummaryResponse> agentRuntimes,
        String message,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        List<ModelProfileAgentProbeResultResponse> results
) {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<List<UUID>> UUID_LIST_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<List<AgentRuntimeSummaryResponse>> RUNTIME_LIST_TYPE = new TypeReference<>() {
    };

    static ModelProfileAgentProbeRunResponse from(
            ModelProfileAgentProbeRunsRecord run,
            List<ModelProfileAgentProbeResultResponse> results
    ) {
        return new ModelProfileAgentProbeRunResponse(
                run.getId(),
                run.getModelProfileId(),
                run.getStatus(),
                jsonbToUuidList(run.getSelectedAgentRuntimeIds()),
                jsonbToRuntimes(run.getSelectedAgentRuntimes()),
                run.getMessage(),
                run.getStartedAt(),
                run.getFinishedAt(),
                run.getCreatedAt(),
                run.getUpdatedAt(),
                results == null ? List.of() : List.copyOf(results)
        );
    }

    private static List<UUID> jsonbToUuidList(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value.data(), UUID_LIST_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private static List<AgentRuntimeSummaryResponse> jsonbToRuntimes(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(value.data(), RUNTIME_LIST_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }
}
