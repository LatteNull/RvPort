package cn.rvport.backend.migration;

import java.util.UUID;

record MigrationInputCandidate(
        UUID projectId,
        UUID sourceRevisionId,
        String issueTitle,
        MigrationInputSourceType sourceType,
        UUID sourceRefId,
        String detectedLevel,
        String locationLabel,
        String recommendationSummary,
        String ruleId,
        String identityPath,
        String identitySymbol,
        String identityAnchor,
        String stableFingerprint,
        MigrationInputStatus initialStatus
) {
}
