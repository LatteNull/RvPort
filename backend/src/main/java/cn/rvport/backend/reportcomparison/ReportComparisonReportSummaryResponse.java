package cn.rvport.backend.reportcomparison;

import cn.rvport.backend.report.ReportType;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ReportComparisonReportSummaryResponse(
        UUID id,
        UUID sourceRevisionId,
        ReportType reportType,
        TaskStatus status,
        String title,
        String riskLevel,
        OffsetDateTime generatedAt,
        OffsetDateTime createdAt
) {
    public static ReportComparisonReportSummaryResponse from(ReportView view) {
        if (view == null) {
            return null;
        }
        return new ReportComparisonReportSummaryResponse(
                view.id(),
                view.sourceRevisionId(),
                view.reportType(),
                view.status(),
                view.title(),
                view.riskLevel(),
                view.generatedAt(),
                view.createdAt()
        );
    }
}
