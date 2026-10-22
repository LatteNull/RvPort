package cn.rvport.backend.migration;

import java.util.List;

public record MigrationInputAutoMergeResponse(
        int created,
        int skipped,
        int noResult,
        List<SourceResult> sources
) {
    public record SourceResult(
            MigrationInputSourceType sourceType,
            int candidates,
            int created,
            int skipped,
            boolean noResult
    ) {
    }
}
