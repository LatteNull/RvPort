package cn.rvport.backend.kb.ai;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.UUID;

public record KbAiExtensionListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        KbAiExtensionStatus status,
        UUID sourceRevisionId,
        UUID kbScanRunId,
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
