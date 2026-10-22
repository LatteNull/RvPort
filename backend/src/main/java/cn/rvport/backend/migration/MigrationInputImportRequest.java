package cn.rvport.backend.migration;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.UUID;

public record MigrationInputImportRequest(
        @NotNull MigrationInputSourceType sourceType,
        @NotNull @Size(min = 1, max = 500) List<UUID> sourceRefIds
) {
}
