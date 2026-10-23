package cn.rvport.backend.project.runtime;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ProjectRuntimeEnvironmentView(
        UUID projectId,
        UUID sourceEnvironmentId,
        UUID targetEnvironmentId,
        long version,
        UUID updatedBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static ProjectRuntimeEnvironmentView empty(UUID projectId) {
        return new ProjectRuntimeEnvironmentView(projectId, null, null, 1L, null, null, null);
    }
}
