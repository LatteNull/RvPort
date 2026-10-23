package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.environment.EnvironmentRole;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record EnvironmentTaskInput(
        UUID projectId,
        UUID environmentId,
        UUID jumpHostEnvironmentId,
        Integer timeoutSeconds,
        String scriptType,
        List<String> checkItems,
        List<String> collectScopes,
        String workingDirectory,
        Map<String, String> parameters,
        UUID scriptPayloadId,
        String scriptSha256,
        Integer scriptLength,
        Long environmentConfigVersion,
        Target target
) {
    public EnvironmentTaskInput(UUID projectId, UUID environmentId, UUID jumpHostEnvironmentId, Integer timeoutSeconds) {
        this(projectId, environmentId, jumpHostEnvironmentId, timeoutSeconds, null, null, null, null, null, null, null, null, null, null);
    }

    public EnvironmentTaskInput(
            UUID projectId,
            UUID environmentId,
            UUID jumpHostEnvironmentId,
            Integer timeoutSeconds,
            String scriptType,
            List<String> checkItems,
            List<String> collectScopes,
            String workingDirectory,
            Map<String, String> parameters,
            String scriptSha256,
            Integer scriptLength
    ) {
        this(projectId, environmentId, jumpHostEnvironmentId, timeoutSeconds, scriptType, checkItems, collectScopes,
                workingDirectory, parameters, null, scriptSha256, scriptLength, null, null);
    }

    public EnvironmentTaskInput(
            UUID projectId,
            UUID environmentId,
            UUID jumpHostEnvironmentId,
            Integer timeoutSeconds,
            String scriptType,
            List<String> checkItems,
            List<String> collectScopes,
            String workingDirectory,
            Map<String, String> parameters,
            UUID scriptPayloadId,
            String scriptSha256,
            Integer scriptLength
    ) {
        this(projectId, environmentId, jumpHostEnvironmentId, timeoutSeconds, scriptType, checkItems, collectScopes,
                workingDirectory, parameters, scriptPayloadId, scriptSha256, scriptLength, null, null);
    }

    public EnvironmentTaskInput(
            UUID projectId,
            UUID environmentId,
            UUID jumpHostEnvironmentId,
            Integer timeoutSeconds,
            String scriptType,
            List<String> checkItems,
            List<String> collectScopes,
            String workingDirectory,
            Map<String, String> parameters,
            UUID scriptPayloadId,
            String scriptSha256,
            Integer scriptLength,
            Target target
    ) {
        this(projectId, environmentId, jumpHostEnvironmentId, timeoutSeconds, scriptType, checkItems, collectScopes,
                workingDirectory, parameters, scriptPayloadId, scriptSha256, scriptLength, null, target);
    }

    public record Target(
            EnvironmentRole role,
            String arch,
            String host,
            int sshPort,
            String username,
            UUID credentialId,
            UUID temporaryCredentialPayloadId,
            String temporaryCredentialSha256,
            String workingDirectory
    ) {
    }
}
