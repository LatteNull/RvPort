package cn.rvport.backend.report;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record ReportInputListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        ReportInputType inputType,
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
