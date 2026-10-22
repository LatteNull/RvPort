package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.task.TaskResponse;
import java.util.UUID;

public record DependencyAutoFixCreateResponse(
        UUID autoFixRunId,
        UUID taskId,
        int selectedCount,
        TaskResponse task
) {
}
