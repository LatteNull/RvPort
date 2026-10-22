package cn.rvport.backend.archive;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ProjectArchiveListRequest(
        Integer page,
        Integer pageSize,
        UUID sourceRevisionId,
        TaskStatus status,
        OffsetDateTime createdFrom,
        OffsetDateTime createdTo,
        String sortBy,
        String sortDirection
) {
    public int normalizedPage() {
        return page == null || page < 1 ? 1 : page;
    }

    public int normalizedPageSize() {
        if (pageSize == null || pageSize < 1) {
            return 20;
        }
        return Math.min(pageSize, 100);
    }
}
