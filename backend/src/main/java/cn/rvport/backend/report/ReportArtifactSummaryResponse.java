package cn.rvport.backend.report;

import cn.rvport.backend.artifact.StoredArtifactView;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportArtifactSummaryResponse(
        UUID id,
        String artifactType,
        String contentType,
        long sizeBytes,
        String sha256,
        Map<String, Object> summary,
        OffsetDateTime createdAt
) {
    public static ReportArtifactSummaryResponse from(StoredArtifactView view) {
        return new ReportArtifactSummaryResponse(
                view.id(),
                view.artifactType(),
                view.contentType(),
                view.sizeBytes(),
                view.sha256(),
                view.summary(),
                view.createdAt()
        );
    }
}
