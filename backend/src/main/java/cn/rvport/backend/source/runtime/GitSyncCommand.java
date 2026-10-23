package cn.rvport.backend.source.runtime;

import cn.rvport.backend.credential.CredentialService;
import java.nio.file.Path;
import java.time.Duration;
import java.util.function.Consumer;

public record GitSyncCommand(
        String gitUrl,
        String gitBranch,
        String gitCommit,
        Path worktreeDir,
        CredentialService.GitRuntimeCredential credential,
        Duration timeout,
        Consumer<Process> processRegistrar
) {
}
