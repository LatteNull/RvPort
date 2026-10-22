package cn.rvport.backend.kb;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record FindingListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        String ruleId,
        String category,
        String severity,
        String title,
        String filePath,
        String symbol,
        String status,
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
