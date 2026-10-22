package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ScriptExecutionDetailResponse(
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
        UUID toolRunId,
        String toolName,
        Integer exitCode,
        Map<String, Object> summary,
        long logEventCount,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
}
