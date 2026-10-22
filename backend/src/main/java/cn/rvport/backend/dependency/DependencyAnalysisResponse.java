package cn.rvport.backend.dependency;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public record DependencyAnalysisResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID sourceBuildRunId,
        UUID targetEnvironmentId,
        Long environmentConfigVersion,
        long currentEnvironmentConfigVersion,
        boolean currentSourceRevision,
        boolean currentRuntimeEnvironment,
        List<String> staleReasons,
        TaskStatus status,
        Map<String, Object> summary,
        Object warnings,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
    public static DependencyAnalysisResponse from(DependencyAnalysisView view, long currentEnvironmentConfigVersion) {
        return from(view, currentEnvironmentConfigVersion, false);
    }

    public static DependencyAnalysisResponse from(DependencyAnalysisView view, long currentEnvironmentConfigVersion, boolean currentSourceRevision) {
        boolean current = view.environmentConfigVersion() != null && Objects.equals(view.environmentConfigVersion(), currentEnvironmentConfigVersion);
        return new DependencyAnalysisResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.sourceRevisionId(),
                view.sourceBuildRunId(),
                view.targetEnvironmentId(),
                view.environmentConfigVersion(),
                currentEnvironmentConfigVersion,
                currentSourceRevision,
                current,
                staleReasons(currentSourceRevision, current),
                view.status(),
                view.summary(),
                view.warnings(),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt()
        );
    }

    private static List<String> staleReasons(boolean currentSourceRevision, boolean currentRuntimeEnvironment) {
        List<String> reasons = new ArrayList<>();
        if (!currentSourceRevision) {
            reasons.add("SOURCE_REVISION_CHANGED");
        }
        if (!currentRuntimeEnvironment) {
            reasons.add("RUNTIME_ENVIRONMENT_CHANGED");
        }
        return List.copyOf(reasons);
    }
}
