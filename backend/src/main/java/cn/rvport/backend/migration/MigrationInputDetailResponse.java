package cn.rvport.backend.migration;

import java.util.Map;

public record MigrationInputDetailResponse(
        MigrationInputResponse reference,
        Map<String, Object> sourceDetail
) {
}
