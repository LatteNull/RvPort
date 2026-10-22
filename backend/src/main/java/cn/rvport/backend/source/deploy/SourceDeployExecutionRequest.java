package cn.rvport.backend.source.deploy;

import java.util.UUID;

public record SourceDeployExecutionRequest(
        UUID projectId,
        UUID taskId,
        UUID sourceDeploymentId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        String remotePath,
        boolean force,
        Integer timeoutSeconds
) {
    public long environmentConfigVersionValue() {
        return environmentConfigVersion == null ? 0L : environmentConfigVersion;
    }
}
