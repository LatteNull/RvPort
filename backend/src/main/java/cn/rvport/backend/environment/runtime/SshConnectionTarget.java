package cn.rvport.backend.environment.runtime;

import java.util.UUID;

public record SshConnectionTarget(
        UUID environmentId,
        String host,
        int port,
        String username,
        String workingDirectory,
        SshRuntimeCredential credential
) {
}
