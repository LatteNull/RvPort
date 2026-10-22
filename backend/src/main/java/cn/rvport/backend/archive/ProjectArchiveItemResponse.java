package cn.rvport.backend.archive;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProjectArchiveItemResponse(
        UUID id,
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
    static ProjectArchiveItemResponse from(ProjectArchiveItemView view) {
        return new ProjectArchiveItemResponse(
                view.id(),
                view.candidateId(),
                view.nodeType(),
                view.candidateType(),
                view.candidateKey(),
                view.resourceType(),
                view.resourceId(),
                view.title(),
                view.artifactRefs(),
                view.metadata(),
                view.createdAt()
        );
    }
}
