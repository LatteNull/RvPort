package cn.rvport.backend.automatedtest;

import cn.rvport.backend.task.TaskStatus;
import java.util.UUID;

public record AutomatedTestListRequest(
        TaskStatus status,
        UUID environmentId,
        UUID sourceRevisionId,
        int page,
        int pageSize,
        String sortBy,
        String sortDirection
) {
    public int normalizedPage() {
        return page <= 0 ? 1 : page;
    }

    public int normalizedPageSize() {
        if (pageSize <= 0) {
            return 20;
        }
        return Math.min(pageSize, 100);
    }
}
