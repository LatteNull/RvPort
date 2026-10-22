package cn.rvport.backend.dependency;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.UUID;

public record DependencyAnalysisListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        Long environmentConfigVersion,
        Boolean currentOnly,
        Boolean includeStale,
        TaskStatus status,
        String riskLevel,
        OffsetDateTime createdFrom,
        OffsetDateTime createdTo,
        String sortBy,
        String sortDirection
) {
    public DependencyAnalysisListRequest(
            Integer page,
            Integer pageSize,
            UUID sourceRevisionId,
            TaskStatus status,
            String riskLevel,
            OffsetDateTime createdFrom,
            OffsetDateTime createdTo,
            String sortBy,
            String sortDirection
    ) {
        this(page, pageSize, sourceRevisionId, null, null, null, status, riskLevel, createdFrom, createdTo, sortBy, sortDirection);
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

    public DependencyAnalysisListRequest withCurrentContext(UUID activeSourceRevisionId, long currentEnvironmentConfigVersion) {
        if (!effectiveCurrentOnly()) {
            return this;
        }
        return new DependencyAnalysisListRequest(
                page,
                pageSize,
                sourceRevisionId == null ? activeSourceRevisionId : sourceRevisionId,
                environmentConfigVersion == null ? currentEnvironmentConfigVersion : environmentConfigVersion,
                currentOnly,
                includeStale,
                status,
                riskLevel,
                createdFrom,
                createdTo,
                sortBy,
                sortDirection
        );
    }
}
