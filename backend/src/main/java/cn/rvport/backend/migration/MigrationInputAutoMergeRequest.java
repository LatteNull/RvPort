package cn.rvport.backend.migration;

import jakarta.validation.constraints.Size;
import java.util.List;

public record MigrationInputAutoMergeRequest(
        @Size(max = 8) List<MigrationInputSourceType> sourceTypes
) {
}
