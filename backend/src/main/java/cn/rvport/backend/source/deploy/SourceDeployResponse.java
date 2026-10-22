package cn.rvport.backend.source.deploy;

import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record SourceDeployResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        long currentEnvironmentConfigVersion,
        boolean currentRuntimeEnvironment,
        String remotePath,
        SourceDeployStrategy deployStrategy,
        boolean force,
        TaskStatus status,
        Integer fileCount,
        Long totalBytes,
        Integer exitCode,
        Map<String, Object> summary,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        SourceRevisionResponse sourceRevision,
        SourceDeployEnvironmentSummary environment
) {
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    public static SourceDeployResponse from(SourceDeployRunView view, ObjectMapper objectMapper) {
        return from(view, null, null, objectMapper);
    }

    public static SourceDeployResponse from(
            SourceDeployRunView view,
            SourceRevisionResponse sourceRevision,
            SourceDeployEnvironmentSummary environment,
            ObjectMapper objectMapper
    ) {
        return from(view, sourceRevision, environment, objectMapper, 0L);
    }

    public static SourceDeployResponse from(
            SourceDeployRunView view,
            SourceRevisionResponse sourceRevision,
            SourceDeployEnvironmentSummary environment,
            ObjectMapper objectMapper,
            long currentEnvironmentConfigVersion
    ) {
        boolean isCurrent = view.environmentConfigVersion() != null
                && view.environmentConfigVersion() == currentEnvironmentConfigVersion;
        return new SourceDeployResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.sourceRevisionId(),
                view.environmentId(),
                view.environmentConfigVersion(),
                currentEnvironmentConfigVersion,
                isCurrent,
                view.remotePath(),
                view.deployStrategy(),
                view.force(),
                view.status(),
                view.fileCount(),
                view.totalBytes(),
                view.exitCode(),
                summary(view, objectMapper),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt(),
                sourceRevision,
                environment
        );
    }

    private static Map<String, Object> summary(SourceDeployRunView view, ObjectMapper objectMapper) {
        if (view.summary() == null || view.summary().data() == null || view.summary().data().isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(view.summary().data(), MAP_TYPE);
        } catch (JsonProcessingException ex) {
            return Map.of();
        }
    }
}
