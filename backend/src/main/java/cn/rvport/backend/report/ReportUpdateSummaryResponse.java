package cn.rvport.backend.report;

import java.util.List;
import java.util.UUID;

public record ReportUpdateSummaryResponse(
        boolean latestReportMissing,
        long added,
        long removed,
        long changed,
        long currentConfirmedInputCount,
        long latestReportInputCount,
        List<Item> addedSamples,
        List<Item> removedSamples,
        List<Item> changedSamples
) {
    public boolean upToDate() {
        return !latestReportMissing && added == 0 && removed == 0 && changed == 0;
    }

    public static ReportUpdateSummaryResponse missing(long currentConfirmedInputCount) {
        return new ReportUpdateSummaryResponse(true, currentConfirmedInputCount, 0, 0,
                currentConfirmedInputCount, 0, List.of(), List.of(), List.of());
    }

    public record Item(
            UUID migrationInputRefId,
            String issueTitle,
            String sourceType,
            String detectedLevel,
            String locationLabel
    ) {
    }
}
