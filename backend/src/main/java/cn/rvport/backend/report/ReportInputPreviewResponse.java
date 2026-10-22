package cn.rvport.backend.report;

import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportInputPreviewResponse(
        UUID id,
        UUID sourceRevisionId,
        String issueTitle,
        MigrationInputSourceType sourceType,
        UUID sourceRefId,
        String detectedLevel,
        String locationLabel,
        MigrationInputStatus status,
        String recommendationSummary,
        String note,
        Map<String, Object> sourceLocation,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static ReportInputPreviewResponse from(MigrationInputRefView view) {
        return new ReportInputPreviewResponse(
                view.id(),
                view.sourceRevisionId(),
                view.issueTitle(),
                view.sourceType(),
                view.sourceRefId(),
                view.detectedLevel(),
                view.locationLabel(),
                view.status(),
                view.recommendationSummary(),
                view.note(),
                Map.of(
                        "sourceType", view.sourceType().name(),
                        "sourceRefId", view.sourceRefId().toString(),
                        "sourceRevisionId", view.sourceRevisionId().toString()
                ),
                view.createdAt(),
                view.updatedAt()
        );
    }
}
