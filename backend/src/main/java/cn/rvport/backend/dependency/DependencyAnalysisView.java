package cn.rvport.backend.dependency;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAnalysisView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID sourceBuildRunId,
        UUID targetEnvironmentId,
        Long environmentConfigVersion,
        TaskStatus status,
        Map<String, Object> summary,
        Object warnings,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
}
