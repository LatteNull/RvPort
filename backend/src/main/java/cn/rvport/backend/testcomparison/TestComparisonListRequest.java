package cn.rvport.backend.testcomparison;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record TestComparisonListRequest(
        TestComparisonStatus status,
        TestComparisonRiskLevel riskLevel,
        UUID testBatchId,
        UUID sourceTestRunId,
        UUID targetTestRunId,
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
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
