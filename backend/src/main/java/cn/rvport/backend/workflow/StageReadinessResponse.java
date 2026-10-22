package cn.rvport.backend.workflow;

import java.util.List;

public record StageReadinessResponse(
        String stageId,
        ProjectContextSnapshot context,
        List<StagePrerequisiteResponse> prerequisites
) {
}
