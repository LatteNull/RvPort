package cn.rvport.backend.project.runtime;

import java.util.UUID;

public record ProjectRuntimeEnvironmentUpdateRequest(
        UUID sourceEnvironmentId,
        UUID targetEnvironmentId
) {
    public boolean empty() {
        return sourceEnvironmentId == null && targetEnvironmentId == null;
    }
}
