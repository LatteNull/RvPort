package cn.rvport.backend.dependency.autofix;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAutoFixRunView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID dependencyAnalysisRunId,
        UUID sourceRevisionId,
        UUID targetEnvironmentId,
        long environmentConfigVersion,
        UUID rerunDependencyAnalysisRunId,
        UUID rerunDependencyAnalysisTaskId,
        DependencyAutoFixRunStatus status,
        int selectedCount,
        int succeededCount,
        int failedCount,
        int skippedCount,
        Map<String, Object> summary,
        String errorSummary,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
}
