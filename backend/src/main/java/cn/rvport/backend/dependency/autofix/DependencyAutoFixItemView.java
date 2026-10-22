package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAutoFixItemView(
        UUID id,
        UUID dependencyAutoFixRunId,
        UUID dependencyResultItemId,
        UUID projectId,
        UUID sourceRevisionId,
        DependencyRiskLevel riskLevel,
        DependencyTargetMatchStatus targetMatchStatus,
        String sourceProviderPackage,
        String sourceProviderVersion,
        String targetProviderPackage,
        String targetProviderVersion,
        String installPackageName,
        String installVersionConstraint,
        boolean defaultSelected,
        DependencyAutoFixItemStatus status,
        Integer exitCode,
        String errorSummary,
        Map<String, Object> evidence,
        java.time.OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
}
