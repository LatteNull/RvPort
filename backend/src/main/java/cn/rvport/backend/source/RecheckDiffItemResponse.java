package cn.rvport.backend.source;

import java.util.UUID;

public record RecheckDiffItemResponse(
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
        String matchReason
) {
    public static RecheckDiffItemResponse from(RecheckDiffItemView view) {
        return new RecheckDiffItemResponse(
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
                view.matchReason()
        );
    }
}
