package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record DependencyAutoFixRunListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        Long environmentConfigVersion,
        Boolean includeStale,
        DependencyAutoFixRunStatus status,
        String sortBy,
        String sortDirection
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }

    public boolean includeStaleEffective() {
        return Boolean.TRUE.equals(includeStale);
    }
}
