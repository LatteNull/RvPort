package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record TaskResponse(
        UUID id,
        UUID projectId,
        String type,
        TaskStatus status,
        Integer progress,
        String message,
        OffsetDateTime createdAt,
        OffsetDateTime queuedAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        String errorCode,
        String errorMessage,
        Map<String, Object> resource
) {
    public static TaskResponse from(TaskView task) {
        return new TaskResponse(
                task.id(),
                task.projectId(),
                task.type(),
                task.status(),
                task.progress(),
                task.message(),
                task.createdAt(),
                task.queuedAt(),
                task.startedAt(),
                task.finishedAt(),
                task.errorCode(),
                task.errorMessage(),
                task.resource().toMap()
        );
    }
}
