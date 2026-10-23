package cn.rvport.backend.project.runtime;

import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.source.deploy.SourceDeployEnvironmentSummary;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public record ProjectRuntimeEnvironmentResponse(
        UUID projectId,
        SourceDeployEnvironmentSummary sourceEnvironment,
        SourceDeployEnvironmentSummary targetEnvironment,
        long version,
        boolean ready,
        List<String> missing,
        UUID updatedBy,
        OffsetDateTime updatedAt
) {
    public static ProjectRuntimeEnvironmentResponse from(
            ProjectRuntimeEnvironmentView view,
            EnvironmentView sourceEnvironment,
            EnvironmentView targetEnvironment
    ) {
        List<String> missing = new ArrayList<>();
        if (sourceEnvironment == null) {
            missing.add("sourceEnvironment");
        }
        if (targetEnvironment == null) {
            missing.add("targetEnvironment");
        }
        if (sourceEnvironment != null && sourceEnvironment.status() != EnvironmentStatus.AVAILABLE) {
            missing.add("sourceEnvironmentTest");
        }
        if (targetEnvironment != null && targetEnvironment.status() != EnvironmentStatus.AVAILABLE) {
            missing.add("targetEnvironmentTest");
        }
        return new ProjectRuntimeEnvironmentResponse(
                view.projectId(),
                sourceEnvironment == null ? null : SourceDeployEnvironmentSummary.from(sourceEnvironment),
                targetEnvironment == null ? null : SourceDeployEnvironmentSummary.from(targetEnvironment),
                view.version(),
                missing.isEmpty(),
                List.copyOf(missing),
                view.updatedBy(),
                view.updatedAt()
        );
    }
}
