package cn.rvport.backend.buildvalidation;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record BuildValidationCreateRequest(
        UUID sourceRevisionId,
        List<UUID> sourceDeploymentIds,
        BuildValidationScope buildScope,
        @NotBlank @Size(max = 12000) String script,
        @Min(10) @Max(86400) Integer timeoutSeconds,
        Map<String, String> environmentVariables
) {
    public BuildValidationCreateRequest(
            UUID sourceRevisionId,
            List<UUID> sourceDeploymentIds,
            String script,
            Integer timeoutSeconds
    ) {
        this(sourceRevisionId, sourceDeploymentIds, null, script, timeoutSeconds, null);
    }

    public BuildValidationCreateRequest(
            UUID sourceRevisionId,
            List<UUID> sourceDeploymentIds,
            String script,
            Integer timeoutSeconds,
            Map<String, String> environmentVariables
    ) {
        this(sourceRevisionId, sourceDeploymentIds, null, script, timeoutSeconds, environmentVariables);
    }

    public BuildValidationScope effectiveBuildScope() {
        return buildScope == null ? BuildValidationScope.BOTH : buildScope;
    }
}
