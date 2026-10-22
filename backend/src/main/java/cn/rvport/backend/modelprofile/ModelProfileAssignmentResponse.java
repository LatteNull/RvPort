package cn.rvport.backend.modelprofile;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ModelProfileAssignmentResponse(
        String stage,
        UUID modelProfileId,
        ModelProfileResponse modelProfile,
        UUID agentRuntimeId,
        cn.rvport.backend.agentruntime.AgentRuntimeResponse agentRuntime,
        OffsetDateTime updatedAt
) {
    public static ModelProfileAssignmentResponse empty(ModelProfileStage stage) {
        return new ModelProfileAssignmentResponse(stage.name(), null, null, null, null, null);
    }
}
