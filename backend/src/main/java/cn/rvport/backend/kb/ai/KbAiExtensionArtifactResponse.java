package cn.rvport.backend.kb.ai;

import cn.rvport.backend.artifact.StoredArtifactView;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbAiExtensionArtifactResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        String artifactType,
        String contentType,
        long sizeBytes,
        String sha256,
        Map<String, Object> summary,
        OffsetDateTime createdAt
) {
    static KbAiExtensionArtifactResponse from(StoredArtifactView artifact) {
        return new KbAiExtensionArtifactResponse(
                artifact.id(),
                artifact.projectId(),
                artifact.taskId(),
                artifact.artifactType(),
                artifact.contentType(),
                artifact.sizeBytes(),
                artifact.sha256(),
                artifact.summary(),
                artifact.createdAt()
        );
    }
}
