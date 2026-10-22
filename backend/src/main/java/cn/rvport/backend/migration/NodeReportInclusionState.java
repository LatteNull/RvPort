package cn.rvport.backend.migration;

import java.util.UUID;

public record NodeReportInclusionState(
        UUID migrationInputRefId,
        MigrationInputStatus migrationInputStatus,
        boolean confirmedForNextReport,
        boolean includedInLatestReport,
        UUID latestReportId
) {
    public static NodeReportInclusionState empty() {
        return new NodeReportInclusionState(null, null, false, false, null);
    }
}
