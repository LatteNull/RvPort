package cn.rvport.backend.task;

import java.util.Map;
import java.util.UUID;

public record TaskCreateCommand(
        UUID projectId,
        String type,
        Map<String, ?> inputSnapshot,
        UUID createdBy,
        Integer timeoutSeconds,
        String message,
        String stageId,
        String resourceType,
        UUID resourceId,
        String resourceMode,
        String environmentRole
) {
    public TaskCreateCommand(
            UUID projectId,
            String type,
            Map<String, ?> inputSnapshot,
            UUID createdBy,
            Integer timeoutSeconds,
            String message
    ) {
        this(projectId, type, inputSnapshot, createdBy, timeoutSeconds, message, null, null, null, null, null);
    }
}
