package cn.rvport.backend.queue;

import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskCancelQueueMessage(
        UUID taskId,
        UUID runtimeHandleId,
        String workerInstanceId,
        OffsetDateTime requestedAt,
        String reason
) {
    public TaskCancelQueueMessage {
        if (taskId == null) {
            throw new IllegalArgumentException("Task cancel message taskId must not be null.");
        }
        if (runtimeHandleId == null) {
            throw new IllegalArgumentException("Task cancel message runtimeHandleId must not be null.");
        }
        if (workerInstanceId == null || workerInstanceId.isBlank()) {
            throw new IllegalArgumentException("Task cancel message workerInstanceId must not be blank.");
        }
        requestedAt = requestedAt == null ? OffsetDateTime.now() : requestedAt;
    }
}
