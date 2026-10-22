package cn.rvport.backend.source;

import java.time.OffsetDateTime;
import java.util.UUID;

public record SourceRevisionResponse(
        UUID id,
        UUID projectId,
        SourceRevisionType revisionType,
        String versionLabel,
        String sourceUri,
        String gitUrl,
        String gitBranch,
        String gitCommit,
        String versionNote,
        boolean active,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static SourceRevisionResponse from(SourceRevisionView view) {
        if (view == null) {
            return null;
        }
        return new SourceRevisionResponse(
                view.id(),
                view.projectId(),
                view.revisionType(),
                view.versionLabel(),
                view.sourceUri(),
                view.gitUrl(),
                view.gitBranch(),
                view.gitCommit(),
                view.versionNote(),
                view.active(),
                view.createdBy(),
                view.createdAt()
        );
    }
}
