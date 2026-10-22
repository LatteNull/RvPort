package cn.rvport.backend.migration;

import cn.rvport.backend.jooq.tables.records.MigrationInputRefsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record MigrationInputRefView(
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
        String ruleId,
        String identityPath,
        String identitySymbol,
        String identityAnchor,
        String stableFingerprint,
        MigrationInputStatus status,
        String note,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static MigrationInputRefView from(MigrationInputRefsRecord record) {
        return new MigrationInputRefView(
                record.getId(),
                record.getInputSetId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                record.getIssueTitle(),
                MigrationInputSourceType.valueOf(record.getSourceType()),
                record.getSourceRefId(),
                record.getDetectedLevel(),
                record.getLocationLabel(),
                record.getRecommendationSummary(),
                record.getRuleId(),
                record.getIdentityPath(),
                record.getIdentitySymbol(),
                record.getIdentityAnchor(),
                record.getStableFingerprint(),
                MigrationInputStatus.valueOf(record.getStatus()),
                record.getNote(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
