package cn.rvport.backend.archive;

import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProjectArchiveResponse(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        SourceRevisionResponse sourceRevision,
        UUID taskId,
        UUID storedArtifactId,
        String name,
        TaskStatus status,
        Map<String, Object> summary,
        Long sizeBytes,
        String sha256,
        List<ProjectArchiveItemResponse> items,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
