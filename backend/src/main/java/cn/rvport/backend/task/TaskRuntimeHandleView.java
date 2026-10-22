package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskRuntimeHandleView(
        UUID id,
        UUID taskId,
        UUID projectId,
        String workerInstanceId,
        TaskRuntimeHandleType handleType,
        TaskRuntimeHandleStatus status,
        Long localPid,
        Long remotePid,
        Long remotePgid,
        UUID environmentId,
        String commandMarker,
        OffsetDateTime cancelRequestedAt,
        OffsetDateTime startedAt,
        OffsetDateTime updatedAt,
        OffsetDateTime terminatedAt,
        String errorCode,
        String errorMessage
) {
}
