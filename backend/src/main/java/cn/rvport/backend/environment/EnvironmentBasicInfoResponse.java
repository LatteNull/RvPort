package cn.rvport.backend.environment;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record EnvironmentBasicInfoResponse(
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
    public static EnvironmentBasicInfoResponse from(EnvironmentBasicInfoView view) {
        if (view == null) {
            return null;
        }
        return new EnvironmentBasicInfoResponse(
                view.snapshotId(),
                view.snapshotKind(),
                view.osName(),
                view.osVersion(),
                view.kernelVersion(),
                view.arch(),
                view.packageManager(),
                view.basicTools(),
                view.toolVersions(),
                view.workingDirectory(),
                view.permissions(),
                view.remoteUser(),
                view.checkedAt()
        );
    }
}
