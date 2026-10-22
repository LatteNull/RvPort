package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record DependencyAutoFixItemListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        DependencyAutoFixItemStatus status,
        DependencyRiskLevel riskLevel,
        DependencyTargetMatchStatus targetMatchStatus,
        String installPackageName,
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
}
