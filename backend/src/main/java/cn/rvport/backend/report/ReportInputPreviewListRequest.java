package cn.rvport.backend.report;

import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record ReportInputPreviewListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        MigrationInputSourceType sourceType,
        MigrationInputStatus status,
        String riskLevel,
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
