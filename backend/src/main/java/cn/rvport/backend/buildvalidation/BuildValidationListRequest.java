package cn.rvport.backend.buildvalidation;

import cn.rvport.backend.task.TaskStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.UUID;

public record BuildValidationListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        Boolean currentOnly,
        Boolean includeStale,
        BuildValidationScope buildScope,
        TaskStatus status,
        OffsetDateTime createdFrom,
        OffsetDateTime createdTo,
        String sortBy,
        String sortDirection
) {
    public BuildValidationListRequest(
            Integer page,
            Integer pageSize,
            UUID sourceRevisionId,
            UUID environmentId,
            TaskStatus status,
            OffsetDateTime createdFrom,
            OffsetDateTime createdTo,
            String sortBy,
            String sortDirection
    ) {
        this(page, pageSize, sourceRevisionId, environmentId, null, null, null, null, status, createdFrom, createdTo, sortBy, sortDirection);
    }

    public BuildValidationListRequest(
            Integer page,
            Integer pageSize,
            UUID sourceRevisionId,
            UUID environmentId,
            BuildValidationScope buildScope,
            TaskStatus status,
            OffsetDateTime createdFrom,
            OffsetDateTime createdTo,
            String sortBy,
            String sortDirection
    ) {
        this(page, pageSize, sourceRevisionId, environmentId, null, null, null, buildScope, status, createdFrom, createdTo, sortBy, sortDirection);
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

    public BuildValidationListRequest withCurrentContext(UUID activeSourceRevisionId, long currentEnvironmentConfigVersion) {
        if (!effectiveCurrentOnly()) {
            return this;
        }
        return new BuildValidationListRequest(
                page,
                pageSize,
                sourceRevisionId == null ? activeSourceRevisionId : sourceRevisionId,
                environmentId,
                environmentConfigVersion == null ? currentEnvironmentConfigVersion : environmentConfigVersion,
                currentOnly,
                includeStale,
                buildScope,
                status,
                createdFrom,
                createdTo,
                sortBy,
                sortDirection
        );
    }
}
