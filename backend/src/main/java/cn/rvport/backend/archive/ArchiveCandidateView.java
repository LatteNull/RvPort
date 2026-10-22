package cn.rvport.backend.archive;

import cn.rvport.backend.jooq.tables.records.ArchiveCandidatesRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ArchiveCandidateView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        ArchiveNodeType nodeType,
        ArchiveCandidateType candidateType,
        String candidateKey,
        String resourceType,
        UUID resourceId,
        String title,
        Map<String, Object> summary,
        List<ArchiveArtifactRef> artifactRefs,
        ArchiveCandidateStatus status,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    static ArchiveCandidateView from(
            ArchiveCandidatesRecord record,
            Map<String, Object> summary,
            List<ArchiveArtifactRef> artifactRefs
    ) {
        return new ArchiveCandidateView(
                record.getId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                ArchiveNodeType.valueOf(record.getNodeType()),
                ArchiveCandidateType.valueOf(record.getCandidateType()),
                record.getCandidateKey(),
                record.getResourceType(),
                record.getResourceId(),
                record.getTitle(),
                summary,
                artifactRefs,
                ArchiveCandidateStatus.valueOf(record.getStatus()),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
