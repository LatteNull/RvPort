package cn.rvport.backend.source.runtime;

import java.util.UUID;

public record SourceGitSyncInput(
        UUID projectId,
        UUID sourceImportId,
        String gitUrl,
        String gitBranch,
        String gitCommit,
        UUID credentialId,
        String versionLabel,
        String versionNote,
        boolean activate
) {
}
