package cn.rvport.backend.report;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record LatestComparableReportResponse(
        UUID id,
        UUID sourceRevisionId,
        TaskStatus status,
        String title,
        String riskLevel,
        OffsetDateTime generatedAt,
        OffsetDateTime createdAt
) {
    public static LatestComparableReportResponse from(ReportView view) {
        if (view == null) {
            return null;
        }
        return new LatestComparableReportResponse(
                view.id(),
                view.sourceRevisionId(),
                view.status(),
                view.title(),
                view.riskLevel(),
                view.generatedAt(),
                view.createdAt()
        );
    }
}
