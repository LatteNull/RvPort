package cn.rvport.backend.report;

import cn.rvport.backend.reportcomparison.ReportComparisonSummaryResponse;
import java.util.List;

public record ReportReadinessResponse(
        boolean canGenerate,
        List<ReportReadinessIssueResponse> blockers,
        List<ReportReadinessIssueResponse> warnings,
        ReportSourceRevisionSummaryResponse sourceRevision,
        ReportInputSummaryResponse inputSummary,
        ReportResponse latestReport,
        boolean reportUpToDate,
        ReportUpdateSummaryResponse reportDiffSummary,
        LatestComparableReportResponse latestComparableReport,
        ReportComparisonSummaryResponse latestComparison
) {
}
