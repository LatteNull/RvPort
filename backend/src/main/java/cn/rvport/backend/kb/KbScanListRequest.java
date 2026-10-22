package cn.rvport.backend.kb;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record KbScanListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        TaskStatus status,
        UUID sourceRevisionId,
        Boolean currentOnly,
        Boolean includeStale,
        String kbVersion,
        String sortBy,
        String sortDirection
) {
    public KbScanListRequest(
            Integer page,
            Integer pageSize,
            TaskStatus status,
            UUID sourceRevisionId,
            String kbVersion,
            String sortBy,
            String sortDirection
    ) {
        this(page, pageSize, status, sourceRevisionId, null, null, kbVersion, sortBy, sortDirection);
    }

    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }

    public boolean effectiveCurrentOnly() {
        if (Boolean.TRUE.equals(includeStale)) {
            return false;
        }
        return currentOnly == null || currentOnly;
    }

    public KbScanListRequest withCurrentSourceRevision(UUID activeSourceRevisionId) {
        if (!effectiveCurrentOnly()) {
            return this;
        }
        return new KbScanListRequest(
                page,
                pageSize,
                status,
                sourceRevisionId == null ? activeSourceRevisionId : sourceRevisionId,
                currentOnly,
                includeStale,
                kbVersion,
                sortBy,
                sortDirection
        );
    }
}
