package cn.rvport.backend.migration;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record MigrationInputListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        MigrationInputSourceType sourceType,
        String detectedLevel,
        MigrationInputStatus status,
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
