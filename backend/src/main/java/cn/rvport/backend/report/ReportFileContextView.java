package cn.rvport.backend.report;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ReportFileContextView(
        UUID id,
        UUID reportId,
        UUID sourceRevisionId,
        String fileKey,
        String relativePath,
        String contentHash,
        Integer totalLines,
        UUID artifactId,
        boolean contextAvailable,
        String unavailableReason,
        OffsetDateTime createdAt
) {
}
