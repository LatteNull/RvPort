package cn.rvport.backend.migration;

import java.util.List;

public record MigrationInputImportResponse(
        MigrationInputSourceType sourceType,
        int requested,
        int created,
        int skipped,
        List<MigrationInputResponse> items
) {
}
