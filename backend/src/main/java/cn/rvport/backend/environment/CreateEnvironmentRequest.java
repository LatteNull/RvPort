package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.UUID;

public record CreateEnvironmentRequest(
        @NotBlank @Size(max = 160) String name,
        @NotNull EnvironmentRole role,
        @NotBlank @Size(max = 32) String arch,
        @NotBlank @Size(max = 255) String host,
        @Min(1) @Max(65535) Integer sshPort,
        @NotBlank @Size(max = 255) String username,
        UUID credentialId,
        EnvironmentLoginType loginType,
        String password,
        String privateKey,
        String passphrase,
        @Size(max = 160) String credentialName,
        UUID jumpHostEnvironmentId,
        @Size(max = 1000) String workingDirectory
) {
}
