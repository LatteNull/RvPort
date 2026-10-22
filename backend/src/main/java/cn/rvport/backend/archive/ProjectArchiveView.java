package cn.rvport.backend.archive;

import cn.rvport.backend.jooq.tables.records.ArchivesRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ProjectArchiveView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID taskId,
        UUID storedArtifactId,
        String name,
        TaskStatus status,
        Map<String, Object> summary,
        Long sizeBytes,
        String sha256,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    static ProjectArchiveView from(ArchivesRecord record, Map<String, Object> summary) {
        return new ProjectArchiveView(
                record.getId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                record.getTaskId(),
                record.getStoredArtifactId(),
                record.getName(),
                TaskStatus.valueOf(record.getStatus()),
                summary,
                record.getSizeBytes(),
                record.getSha256(),
                record.getCreatedBy(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
