package cn.rvport.backend.testcomparison;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record TestComparisonFindingListRequest(
        TestComparisonRiskLevel severity,
        String differenceType,
        @Min(1) Integer page,
        @Min(1) @Max(500) Integer pageSize,
        String sortBy,
        String sortDirection
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 50 : pageSize;
    }
}
