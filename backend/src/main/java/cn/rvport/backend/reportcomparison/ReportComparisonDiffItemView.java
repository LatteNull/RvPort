package cn.rvport.backend.reportcomparison;

import cn.rvport.backend.jooq.tables.records.ReportComparisonDiffItemsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportComparisonDiffItemView(
        UUID id,
        UUID comparisonRunId,
        UUID projectId,
        String sourceType,
        UUID oldSourceId,
        UUID newSourceId,
        String diffStatus,
        String severity,
        String title,
        String locationLabel,
        String recommendation,
        String confirmationStatus,
        String fingerprint,
        String matchConfidence,
        String matchReason,
        Map<String, Object> oldSnapshot,
        Map<String, Object> newSnapshot,
        OffsetDateTime createdAt
) {
    static ReportComparisonDiffItemView from(
            ReportComparisonDiffItemsRecord record,
            Map<String, Object> oldSnapshot,
            Map<String, Object> newSnapshot
    ) {
        return new ReportComparisonDiffItemView(
                record.getId(),
                record.getComparisonRunId(),
                record.getProjectId(),
                record.getSourceType(),
                record.getOldSourceId(),
                record.getNewSourceId(),
                record.getDiffStatus(),
                record.getSeverity(),
                record.getTitle(),
                record.getLocationLabel(),
                record.getRecommendation(),
                record.getConfirmationStatus(),
                record.getFingerprint(),
                record.getMatchConfidence(),
                record.getMatchReason(),
                oldSnapshot,
                newSnapshot,
                record.getCreatedAt()
        );
    }
}
