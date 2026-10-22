package cn.rvport.backend.buildvalidation;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.Map;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record BuildValidationTaskInput(
        UUID projectId,
        UUID buildRunId,
        BuildValidationScope buildScope,
        UUID sourceDeploymentId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        UUID scriptPayloadId,
        String scriptSha256,
        Integer scriptLength,
        Integer timeoutSeconds,
        Map<String, String> environmentVariables
) {
    public BuildValidationTaskInput(
            UUID projectId,
            UUID buildRunId,
            UUID sourceDeploymentId,
            UUID sourceRevisionId,
            UUID environmentId,
            Long environmentConfigVersion,
            UUID scriptPayloadId,
            String scriptSha256,
            Integer scriptLength,
            Integer timeoutSeconds,
            Map<String, String> environmentVariables
    ) {
        this(projectId, buildRunId, BuildValidationScope.BOTH, sourceDeploymentId, sourceRevisionId, environmentId,
                environmentConfigVersion, scriptPayloadId, scriptSha256, scriptLength, timeoutSeconds, environmentVariables);
    }
}
