package cn.rvport.backend.source;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record SourceListRequest(
        SourceRevisionType revisionType,
        Boolean active,
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }
}
