package cn.rvport.backend.optimization;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.UUID;

public record OptimizationCycleListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(100) Integer pageSize,
        UUID sourceRevisionId,
        OptimizationCycleStatus status,
        OffsetDateTime createdFrom,
        OffsetDateTime createdTo,
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
