package cn.rvport.backend.workflow;

import java.util.UUID;

public record ProjectContextSnapshot(
        UUID sourceRevisionId,
        Long runtimeEnvironmentVersion
) {
}
