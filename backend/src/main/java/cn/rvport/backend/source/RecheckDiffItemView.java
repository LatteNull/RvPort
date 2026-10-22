package cn.rvport.backend.source;

import cn.rvport.backend.jooq.tables.records.DiffItemsRecord;
import java.util.Map;
import java.util.UUID;

public record RecheckDiffItemView(
        UUID id,
        UUID recheckRunId,
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
        Map<String, Object> newSnapshot
) {
    public static RecheckDiffItemView from(DiffItemsRecord record, Map<String, Object> oldSnapshot, Map<String, Object> newSnapshot) {
        return new RecheckDiffItemView(
                record.getId(),
                record.getRecheckRunId(),
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
                newSnapshot
        );
    }
}
