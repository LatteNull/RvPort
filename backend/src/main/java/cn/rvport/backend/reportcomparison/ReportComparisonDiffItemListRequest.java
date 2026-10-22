package cn.rvport.backend.reportcomparison;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record ReportComparisonDiffItemListRequest(
        String diffStatus,
        String sourceType,
        String severity,
        String matchConfidence,
        String keyword,
        String sortBy,
        String sortDirection,
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }
}
