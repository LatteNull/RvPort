package cn.rvport.backend.archive;

import cn.rvport.backend.jooq.tables.records.ArchiveItemsRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProjectArchiveItemView(
        UUID id,
        UUID archiveId,
        UUID candidateId,
        ArchiveNodeType nodeType,
        ArchiveCandidateType candidateType,
        String candidateKey,
        String resourceType,
        UUID resourceId,
        String title,
        List<ArchiveArtifactRef> artifactRefs,
        Map<String, Object> metadata,
        OffsetDateTime createdAt
) {
    static ProjectArchiveItemView from(
            ArchiveItemsRecord record,
            List<ArchiveArtifactRef> artifactRefs,
            Map<String, Object> metadata
    ) {
        return new ProjectArchiveItemView(
                record.getId(),
                record.getArchiveId(),
                record.getCandidateId(),
                record.getNodeType() == null ? null : ArchiveNodeType.valueOf(record.getNodeType()),
                record.getCandidateType() == null ? null : ArchiveCandidateType.valueOf(record.getCandidateType()),
                record.getCandidateKey(),
                record.getResourceType(),
                record.getResourceId(),
                record.getTitle(),
                artifactRefs,
                metadata,
                record.getCreatedAt()
        );
    }
}
