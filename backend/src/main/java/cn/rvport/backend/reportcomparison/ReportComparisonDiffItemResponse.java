package cn.rvport.backend.reportcomparison;

import java.util.UUID;

public record ReportComparisonDiffItemResponse(
        UUID id,
        UUID comparisonRunId,
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
    public static ReportComparisonDiffItemResponse from(ReportComparisonDiffItemView view) {
        return new ReportComparisonDiffItemResponse(
                view.id(),
                view.comparisonRunId(),
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
