package cn.rvport.backend.migration;

import jakarta.validation.constraints.Size;

public record MigrationInputUpdateRequest(
        MigrationInputStatus status,
        @Size(max = 2000) String note
) {
}
