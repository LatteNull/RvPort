package cn.rvport.backend.environment;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record EnvironmentSnapshotResponse(
        UUID id,
        UUID environmentId,
        UUID projectId,
        UUID taskId,
        long environmentConfigVersion,
        String osName,
        String osVersion,
        String kernelVersion,
        String arch,
        String packageManager,
        String snapshotKind,
        TaskStatus status,
        OffsetDateTime collectedAt
) {
    public static EnvironmentSnapshotResponse from(EnvironmentSnapshotView view) {
        return new EnvironmentSnapshotResponse(
                view.id(),
                view.environmentId(),
                view.projectId(),
                view.taskId(),
                view.environmentConfigVersion(),
                view.osName(),
                view.osVersion(),
                view.kernelVersion(),
                view.arch(),
                view.packageManager(),
                view.snapshotKind(),
                view.status(),
                view.collectedAt()
        );
    }
}
