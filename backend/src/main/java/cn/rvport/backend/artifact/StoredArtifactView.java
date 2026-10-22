package cn.rvport.backend.artifact;

import cn.rvport.backend.jooq.tables.records.StoredArtifactsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record StoredArtifactView(
        UUID id,
        UUID projectId,
        UUID taskId,
        StoredArtifactOwnerType ownerType,
        UUID ownerId,
        String artifactType,
        String bucket,
        String objectKey,
        String contentType,
        long sizeBytes,
        String sha256,
        Map<String, Object> summary,
        OffsetDateTime createdAt
) {

    static StoredArtifactView from(StoredArtifactsRecord record, Map<String, Object> summary) {
        return new StoredArtifactView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                StoredArtifactOwnerType.valueOf(record.getOwnerType()),
                record.getOwnerId(),
                record.getArtifactType(),
                record.getBucket(),
                record.getObjectKey(),
                record.getContentType(),
                record.getSizeBytes(),
                record.getSha256(),
                summary,
                record.getCreatedAt()
        );
    }
}
