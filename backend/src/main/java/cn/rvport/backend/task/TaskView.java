package cn.rvport.backend.task;

import cn.rvport.backend.jooq.tables.records.TasksRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskView(
        UUID id,
        UUID projectId,
        String type,
        TaskStatus status,
        Integer progress,
        String message,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime queuedAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        Integer timeoutSeconds,
        String errorCode,
        String errorMessage,
        int retryCount,
        String stageId,
        String resourceType,
        UUID resourceId,
        String resourceMode,
        String environmentRole
) {
    public TaskView(
            UUID id,
            UUID projectId,
            String type,
            TaskStatus status,
            Integer progress,
            String message,
            UUID createdBy,
            OffsetDateTime createdAt,
            OffsetDateTime queuedAt,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            Integer timeoutSeconds,
            String errorCode,
            String errorMessage,
            int retryCount
    ) {
        this(id, projectId, type, status, progress, message, createdBy, createdAt, queuedAt, startedAt, finishedAt,
                timeoutSeconds, errorCode, errorMessage, retryCount, null, null, null, null, null);
    }

    public static TaskView from(TasksRecord record) {
        return new TaskView(
                record.getId(),
                record.getProjectId(),
                record.getType(),
                TaskStatus.valueOf(record.getStatus()),
                record.getProgress(),
                record.getMessage(),
                record.getCreatedBy(),
                record.getCreatedAt(),
                record.getQueuedAt(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getTimeoutSeconds(),
                record.getErrorCode(),
                record.getErrorMessage(),
                record.getRetryCount(),
                record.getStageId(),
                record.getResourceType(),
                record.getResourceId(),
                record.getResourceMode(),
                record.getEnvironmentRole()
        );
    }

    public TaskEventResource resource() {
        return TaskEventResource.fromTask(this);
    }
}
