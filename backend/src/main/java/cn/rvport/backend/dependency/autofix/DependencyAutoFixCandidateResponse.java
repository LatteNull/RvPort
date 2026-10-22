package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import java.util.UUID;

public record DependencyAutoFixCandidateResponse(
        UUID resultItemId,
        DependencyType dependencyType,
        String dependencyName,
        String dependencyVersion,
        DependencyRiskLevel riskLevel,
        DependencyTargetMatchStatus targetMatchStatus,
        String sourceProviderPackage,
        String sourceProviderVersion,
        String targetProviderPackage,
        String targetProviderVersion,
        String installPackageName,
        String installVersionConstraint,
        boolean defaultSelected,
        boolean selectable,
        String reason
) {
}
