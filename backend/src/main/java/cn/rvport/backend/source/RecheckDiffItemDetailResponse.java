package cn.rvport.backend.source;

import java.util.Map;
import java.util.UUID;

public record RecheckDiffItemDetailResponse(
        UUID id,
        UUID recheckRunId,
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
        Map<String, Object> oldItem,
        Map<String, Object> newItem
) {
    public static RecheckDiffItemDetailResponse from(RecheckDiffItemView view) {
        return new RecheckDiffItemDetailResponse(
                view.id(),
                view.recheckRunId(),
                view.sourceType(),
                view.oldSourceId(),
                view.newSourceId(),
                view.diffStatus(),
                view.severity(),
                view.title(),
                view.locationLabel(),
                view.recommendation(),
                view.confirmationStatus(),
                view.fingerprint(),
                view.matchConfidence(),
                view.matchReason(),
                view.oldSnapshot(),
                view.newSnapshot()
        );
    }
}
