package cn.rvport.backend.dependency.autofix;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAutoFixRunResponse(
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
    public static DependencyAutoFixRunResponse from(DependencyAutoFixRunView view) {
        return new DependencyAutoFixRunResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.dependencyAnalysisRunId(),
                view.sourceRevisionId(),
                view.targetEnvironmentId(),
                view.environmentConfigVersion(),
                view.rerunDependencyAnalysisRunId(),
                view.rerunDependencyAnalysisTaskId(),
                view.status(),
                view.selectedCount(),
                view.succeededCount(),
                view.failedCount(),
                view.skippedCount(),
                view.summary(),
                view.errorSummary(),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt()
        );
    }
}
