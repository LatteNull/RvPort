package cn.rvport.backend.worker;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record WorkerInstanceListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        WorkerInstanceStatus status,
        String instanceId,
        String hostname,
        Boolean hasRunningTasks,
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
