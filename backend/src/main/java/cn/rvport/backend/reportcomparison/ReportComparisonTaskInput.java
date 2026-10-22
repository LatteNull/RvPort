package cn.rvport.backend.reportcomparison;

import java.util.UUID;

public record ReportComparisonTaskInput(
        UUID projectId,
        UUID comparisonRunId,
        UUID baseReportId,
        UUID targetReportId
) {
}
