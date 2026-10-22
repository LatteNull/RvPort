package cn.rvport.backend.environment;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record EnvironmentBasicInfoView(
        UUID snapshotId,
        String snapshotKind,
        String osName,
        String osVersion,
        String kernelVersion,
        String arch,
        String packageManager,
        Map<String, ?> basicTools,
        Map<String, ?> toolVersions,
        Map<String, ?> workingDirectory,
        Map<String, ?> permissions,
        String remoteUser,
        OffsetDateTime checkedAt
) {
}
