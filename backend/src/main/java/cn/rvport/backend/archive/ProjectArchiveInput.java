package cn.rvport.backend.archive;

import java.util.UUID;

public record ProjectArchiveInput(
        UUID projectId,
        UUID sourceRevisionId
) {
}
