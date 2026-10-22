package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record DependencyAutoFixCandidateListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        DependencyType dependencyType,
        DependencyTargetMatchStatus targetMatchStatus,
        DependencyRiskLevel riskLevel,
        Boolean defaultSelected,
        Boolean selectable,
        String keyword,
        String sortBy,
        String sortDirection
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }

    public boolean effectiveSelectable() {
        return selectable == null || selectable;
    }
}
