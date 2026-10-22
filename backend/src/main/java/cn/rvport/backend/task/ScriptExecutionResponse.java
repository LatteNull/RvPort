package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ScriptExecutionResponse(
        UUID id,
        UUID taskId,
        UUID projectId,
        UUID environmentId,
        String environmentName,
        ScriptExecutionStatus status,
        TaskStatus taskStatus,
        Integer progress,
        String message,
        String scriptSha256,
        Integer scriptLength,
        Integer exitCode,
        long logEventCount,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
}
