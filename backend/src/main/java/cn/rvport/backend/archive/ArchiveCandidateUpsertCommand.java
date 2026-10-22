package cn.rvport.backend.archive;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ArchiveCandidateUpsertCommand(
        UUID projectId,
        UUID sourceRevisionId,
        ArchiveNodeType nodeType,
        ArchiveCandidateType candidateType,
        String candidateKey,
        String resourceType,
        UUID resourceId,
        String title,
        Map<String, ?> summary,
        List<ArchiveArtifactRef> artifactRefs
) {
}
