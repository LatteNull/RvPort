package cn.rvport.backend.kb;

import java.util.UUID;

public record KbScanArtifactDownload(
        UUID id,
        UUID projectId,
        UUID scanRunId,
        String artifactType,
        String sha256,
        long sizeBytes,
        String contentPath,
        UUID storedArtifactId
) {
}
