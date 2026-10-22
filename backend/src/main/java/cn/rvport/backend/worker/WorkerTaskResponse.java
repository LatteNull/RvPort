package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record WorkerTaskResponse(
        UUID taskId,
        UUID projectId,
        String projectName,
        String type,
        TaskStatus status,
        int progress,
        String message,
        OffsetDateTime startedAt
) {
}
