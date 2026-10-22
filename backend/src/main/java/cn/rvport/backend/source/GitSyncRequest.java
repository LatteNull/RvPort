package cn.rvport.backend.source;

import cn.rvport.backend.credential.CredentialKind;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.UUID;

public record GitSyncRequest(
        @NotBlank @Size(max = 2000) String gitUrl,
        @Size(max = 255) String gitBranch,
        @Size(max = 255) String gitCommit,
        UUID credentialId,
        CredentialKind credentialKind,
        @Size(max = 160) String credentialName,
        @Size(max = 255) String username,
        String password,
        String token,
        @Size(max = 160) String versionLabel,
        @Size(max = 2000) String versionNote,
        Boolean activate
) {
}
