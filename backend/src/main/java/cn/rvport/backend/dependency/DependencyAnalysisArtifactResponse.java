package cn.rvport.backend.dependency;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAnalysisArtifactResponse(
        UUID id,
        String artifactType,
        String contentType,
        Long sizeBytes,
        String sha256,
        Map<String, Object> summary,
        OffsetDateTime createdAt
) {
}
