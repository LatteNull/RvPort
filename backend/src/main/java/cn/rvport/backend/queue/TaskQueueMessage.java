package cn.rvport.backend.queue;

import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskQueueMessage(
        UUID taskId,
        String taskType,
        UUID projectId,
        OffsetDateTime createdAt,
        int attempt
) {
    public TaskQueueMessage {
        if (taskId == null) {
            throw new IllegalArgumentException("Task queue message taskId must not be null.");
        }
        if (taskType == null || taskType.isBlank()) {
            throw new IllegalArgumentException("Task queue message taskType must not be blank.");
        }
        createdAt = createdAt == null ? OffsetDateTime.now() : createdAt;
        attempt = attempt <= 0 ? 1 : attempt;
    }

    public TaskQueueMessage(UUID taskId, String taskType, UUID projectId, OffsetDateTime createdAt) {
        this(taskId, taskType, projectId, createdAt, 1);
    }

    public TaskQueueMessage nextAttempt() {
        return new TaskQueueMessage(taskId, taskType, projectId, createdAt, attempt + 1);
    }
}
