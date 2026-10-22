package cn.rvport.backend.kb;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record KbScanArtifactListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        KbScanArtifactType artifactType,
        String schemaVersion,
        String sha256,
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
