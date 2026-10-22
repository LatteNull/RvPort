package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import java.util.UUID;

public record UpdateEnvironmentRequest(
        @Size(max = 160) String name,
        EnvironmentRole role,
        @Size(max = 32) String arch,
        @Size(max = 255) String host,
        @Min(1) @Max(65535) Integer sshPort,
        @Size(max = 255) String username,
        UUID credentialId,
        EnvironmentLoginType loginType,
        String password,
        String privateKey,
        String passphrase,
        @Size(max = 160) String credentialName,
        UUID jumpHostEnvironmentId,
        Boolean clearJumpHost,
        @Size(max = 1000) String workingDirectory,
        Boolean enabled
) {
}
