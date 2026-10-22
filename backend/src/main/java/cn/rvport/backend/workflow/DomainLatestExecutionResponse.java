package cn.rvport.backend.workflow;

import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.UUID;

public record DomainLatestExecutionResponse(
        UUID id,
        UUID taskId,
        TaskStatus status,
        Integer progress,
        String message,
        String errorCode,
        String errorMessage,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
    public static DomainLatestExecutionResponse from(UUID id, TaskView task) {
        if (task == null) {
            return null;
        }
        return new DomainLatestExecutionResponse(
                id,
                task.id(),
                task.status(),
                task.progress(),
                task.message(),
                task.errorCode(),
                task.errorMessage(),
                task.createdAt(),
                task.startedAt(),
                task.finishedAt()
        );
    }
}
