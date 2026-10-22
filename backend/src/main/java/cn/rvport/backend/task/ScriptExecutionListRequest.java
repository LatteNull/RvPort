package cn.rvport.backend.task;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record ScriptExecutionListRequest(
        ScriptExecutionStatus status,
        UUID environmentId,
        String keyword,
        String sort,
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }

    public String normalizedSort() {
        return sort == null || sort.isBlank() ? "createdAt.desc" : sort.trim();
    }
}
