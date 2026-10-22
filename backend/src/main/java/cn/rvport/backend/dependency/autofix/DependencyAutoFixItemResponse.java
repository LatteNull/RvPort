package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAutoFixItemResponse(
        UUID id,
        UUID dependencyAutoFixRunId,
        UUID dependencyResultItemId,
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
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
    public static DependencyAutoFixItemResponse from(DependencyAutoFixItemView view) {
        return new DependencyAutoFixItemResponse(
                view.id(),
                view.dependencyAutoFixRunId(),
                view.dependencyResultItemId(),
                view.riskLevel(),
                view.targetMatchStatus(),
                view.sourceProviderPackage(),
                view.sourceProviderVersion(),
                view.targetProviderPackage(),
                view.targetProviderVersion(),
                view.installPackageName(),
                view.installVersionConstraint(),
                view.defaultSelected(),
                view.status(),
                view.exitCode(),
                view.errorSummary(),
                view.evidence(),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt()
        );
    }
}
