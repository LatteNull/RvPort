package cn.rvport.backend.dependency;

import cn.rvport.backend.task.TaskResponse;
import java.util.UUID;

public record DependencyAnalysisCreateResponse(
        UUID analysisRunId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID sourceBuildRunId,
        TaskResponse task
) {
}
