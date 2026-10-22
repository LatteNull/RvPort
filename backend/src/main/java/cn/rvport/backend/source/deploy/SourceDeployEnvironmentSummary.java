package cn.rvport.backend.source.deploy;

import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import java.util.UUID;

public record SourceDeployEnvironmentSummary(
        UUID id,
        String name,
        EnvironmentRole role,
        String arch,
        EnvironmentStatus status,
        boolean enabled,
        long configVersion
) {
    public SourceDeployEnvironmentSummary(
            UUID id,
            String name,
            EnvironmentRole role,
            String arch,
            EnvironmentStatus status,
            boolean enabled
    ) {
        this(id, name, role, arch, status, enabled, 1L);
    }

    public static SourceDeployEnvironmentSummary from(EnvironmentView view) {
        return new SourceDeployEnvironmentSummary(
                view.id(),
                view.name(),
                view.role(),
                view.arch(),
                view.status(),
                view.enabled(),
                view.configVersion()
        );
    }
}
