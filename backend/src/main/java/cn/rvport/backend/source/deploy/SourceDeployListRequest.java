package cn.rvport.backend.source.deploy;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.UUID;

public record SourceDeployListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        UUID environmentId,
        TaskStatus status,
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
