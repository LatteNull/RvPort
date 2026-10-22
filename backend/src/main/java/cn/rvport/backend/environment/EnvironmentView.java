package cn.rvport.backend.environment;

import java.time.OffsetDateTime;
import java.util.UUID;

public record EnvironmentView(
        UUID id,
        UUID projectId,
        String name,
        EnvironmentRole role,
        String arch,
        String host,
        int sshPort,
        String username,
        UUID credentialId,
        UUID jumpHostEnvironmentId,
        String workingDirectory,
        EnvironmentStatus status,
        boolean enabled,
        long configVersion,
        OffsetDateTime lastConnectedAt,
        OffsetDateTime lastCollectedAt,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public EnvironmentView(
            UUID id,
            UUID projectId,
            String name,
            EnvironmentRole role,
            String arch,
            String host,
            int sshPort,
            String username,
            UUID credentialId,
            UUID jumpHostEnvironmentId,
            String workingDirectory,
            EnvironmentStatus status,
            boolean enabled,
            OffsetDateTime lastConnectedAt,
            OffsetDateTime lastCollectedAt,
            UUID createdBy,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
        this(id, projectId, name, role, arch, host, sshPort, username, credentialId, jumpHostEnvironmentId,
                workingDirectory, status, enabled, 1L, lastConnectedAt, lastCollectedAt, createdBy, createdAt, updatedAt);
    }
}
