package cn.rvport.backend.environment;

import cn.rvport.backend.credential.CredentialSummaryResponse;
import java.time.OffsetDateTime;
import java.util.UUID;

public record EnvironmentResponse(
        UUID id,
        UUID projectId,
        String name,
        EnvironmentRole role,
        String arch,
        String host,
        int sshPort,
        String username,
        CredentialSummaryResponse credential,
        JumpHostSummaryResponse jumpHost,
        String workingDirectory,
        EnvironmentStatus status,
        boolean enabled,
        long configVersion,
        OffsetDateTime lastConnectedAt,
        OffsetDateTime lastCollectedAt,
        EnvironmentBasicInfoResponse basicInfo,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static EnvironmentResponse from(
            EnvironmentView view,
            CredentialSummaryResponse credential,
            JumpHostSummaryResponse jumpHost,
            EnvironmentBasicInfoResponse basicInfo
    ) {
        return new EnvironmentResponse(
                view.id(),
                view.projectId(),
                view.name(),
                view.role(),
                view.arch(),
                view.host(),
                view.sshPort(),
                view.username(),
                credential,
                jumpHost,
                view.workingDirectory(),
                view.status(),
                view.enabled(),
                view.configVersion(),
                view.lastConnectedAt(),
                view.lastCollectedAt(),
                basicInfo,
                view.createdBy(),
                view.createdAt(),
                view.updatedAt()
        );
    }
}
