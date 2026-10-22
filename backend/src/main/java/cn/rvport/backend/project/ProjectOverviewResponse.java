package cn.rvport.backend.project;

import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentResponse;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.task.TaskResponse;
import java.util.List;

public record ProjectOverviewResponse(
        ProjectResponse project,
        CurrentContextResponse currentContext,
        WorkflowResponse workflow,
        List<TaskResponse> recentTasks,
        long latestTaskEventId
) {
    public ProjectOverviewResponse {
        recentTasks = recentTasks == null ? List.of() : List.copyOf(recentTasks);
    }

    public record CurrentContextResponse(
            SourceRevisionResponse activeSourceRevision,
            ProjectRuntimeEnvironmentResponse runtimeEnvironments
    ) {
    }

    public record WorkflowResponse(
            String recommendedStageId,
            List<WorkflowStageResponse> stages
    ) {
        public WorkflowResponse {
            stages = stages == null ? List.of() : List.copyOf(stages);
        }
    }

    public record WorkflowStageResponse(String id, WorkflowStageStatus status, String reasonCode) {
    }

    public enum WorkflowStageStatus {
        PENDING,
        RUNNING,
        DONE,
        BLOCKED
    }
}
