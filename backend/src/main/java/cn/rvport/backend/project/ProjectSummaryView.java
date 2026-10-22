package cn.rvport.backend.project;

import java.time.OffsetDateTime;

public record ProjectSummaryView(
        long highRiskCount,
        OffsetDateTime latestScanAt,
        String latestBuildStatus,
        String latestTestStatus
) {
    public static ProjectSummaryView empty() {
        return new ProjectSummaryView(0, null, null, null);
    }

    public ProjectSummaryView withHighRiskCount(long value) {
        return new ProjectSummaryView(value, latestScanAt, latestBuildStatus, latestTestStatus);
    }

    public ProjectSummaryView withLatestScanAt(OffsetDateTime value) {
        return new ProjectSummaryView(highRiskCount, max(latestScanAt, value), latestBuildStatus, latestTestStatus);
    }

    public ProjectSummaryView withLatestBuildStatus(String value) {
        return new ProjectSummaryView(highRiskCount, latestScanAt, value, latestTestStatus);
    }

    public ProjectSummaryView withLatestTestStatus(String value) {
        return new ProjectSummaryView(highRiskCount, latestScanAt, latestBuildStatus, value);
    }

    private static OffsetDateTime max(OffsetDateTime current, OffsetDateTime candidate) {
        if (candidate == null) {
            return current;
        }
        if (current == null || candidate.isAfter(current)) {
            return candidate;
        }
        return current;
    }
}
