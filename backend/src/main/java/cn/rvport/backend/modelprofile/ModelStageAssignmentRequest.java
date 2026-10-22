package cn.rvport.backend.modelprofile;

import java.util.List;
import java.util.UUID;

public record ModelStageAssignmentRequest(List<Entry> assignments) {
    public record Entry(String stage, UUID modelProfileId, UUID agentRuntimeId) {
    }
}
