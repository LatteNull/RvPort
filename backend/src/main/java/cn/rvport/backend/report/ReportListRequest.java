package cn.rvport.backend.report;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ReportListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        TaskStatus status,
        String riskLevel,
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
