package cn.rvport.backend.migration;

import java.time.OffsetDateTime;
import java.util.UUID;

public record MigrationInputResponse(
        UUID id,
        UUID inputSetId,
        UUID projectId,
        UUID sourceRevisionId,
        String issueTitle,
        MigrationInputSourceType sourceType,
        UUID sourceRefId,
        String detectedLevel,
        String locationLabel,
        String recommendationSummary,
        MigrationInputStatus status,
        String note,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    static MigrationInputResponse from(MigrationInputRefView view) {
        return new MigrationInputResponse(
                view.id(),
                view.inputSetId(),
                view.projectId(),
                view.sourceRevisionId(),
                view.issueTitle(),
                view.sourceType(),
                view.sourceRefId(),
                view.detectedLevel(),
                view.locationLabel(),
                view.recommendationSummary(),
                view.status(),
                view.note(),
                view.createdAt(),
                view.updatedAt()
        );
    }
}
