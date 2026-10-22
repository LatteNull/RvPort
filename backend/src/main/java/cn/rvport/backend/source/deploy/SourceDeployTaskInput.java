package cn.rvport.backend.source.deploy;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record SourceDeployTaskInput(
        UUID projectId,
        UUID sourceDeploymentId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        boolean force,
        Integer timeoutSeconds
) {
}
