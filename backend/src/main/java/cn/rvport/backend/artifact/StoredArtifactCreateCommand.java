package cn.rvport.backend.artifact;

import java.util.Map;
import java.util.UUID;

public record StoredArtifactCreateCommand(
        UUID projectId,
        UUID taskId,
        StoredArtifactOwnerType ownerType,
        UUID ownerId,
        String artifactType,
        String contentType,
        byte[] content,
        Map<String, ?> summary,
        String extension
) {
}
