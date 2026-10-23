package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.credential.CredentialKind;

public record SshRuntimeCredential(
        CredentialKind kind,
        String username,
        String password,
        String privateKey,
        String passphrase
) {
}
