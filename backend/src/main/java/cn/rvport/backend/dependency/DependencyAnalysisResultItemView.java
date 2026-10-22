package cn.rvport.backend.dependency;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record DependencyAnalysisResultItemView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID taskId,
        UUID dependencyAnalysisRunId,
        DependencyType dependencyType,
        String dependencyName,
        String dependencyVersion,
        String sourceProviderPackage,
        String sourceProviderVersion,
        String sourceDetectedVersion,
        String targetProviderPackage,
        String targetProviderVersion,
        String targetDetectedVersion,
        String providerVersionStatus,
        String versionEvidenceConfidence,
        DependencyTargetMatchStatus targetMatchStatus,
        DependencyRiskLevel riskLevel,
        String locationLabel,
        String recommendation,
        DependencyConfidence confidence,
        Map<String, Object> evidence,
        OffsetDateTime createdAt
) {
}
