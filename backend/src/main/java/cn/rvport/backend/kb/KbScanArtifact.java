package cn.rvport.backend.kb;

import java.util.Map;
import java.util.UUID;

public record KbScanArtifact(
        UUID projectId,
        UUID taskId,
        UUID scanRunId,
        KbScanArtifactType artifactType,
        String schemaVersion,
        String sha256,
        long sizeBytes,
        String contentPath,
        UUID storedArtifactId,
        Map<String, Object> summary
) {
}
