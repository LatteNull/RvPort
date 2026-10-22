package cn.rvport.backend.kb;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbScanArtifactSummaryResponse(
        UUID id,
        String artifactType,
        String schemaVersion,
        String sha256,
        long sizeBytes,
        OffsetDateTime createdAt,
        Map<String, Object> summary
) {
}
