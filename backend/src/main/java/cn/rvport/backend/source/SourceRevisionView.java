package cn.rvport.backend.source;

import cn.rvport.backend.jooq.tables.records.SourceRevisionsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record SourceRevisionView(
        UUID id,
        UUID projectId,
        SourceRevisionType revisionType,
        String versionLabel,
        String sourceUri,
        String gitUrl,
        String gitBranch,
        String gitCommit,
        String archivePath,
        String workingCopyPath,
        String versionNote,
        boolean active,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static SourceRevisionView from(SourceRevisionsRecord record) {
        return new SourceRevisionView(
                record.getId(),
                record.getProjectId(),
                SourceRevisionType.valueOf(record.getRevisionType()),
                record.getVersionLabel(),
                record.getSourceUri(),
                record.getGitUrl(),
                record.getGitBranch(),
                record.getGitCommit(),
                record.getArchivePath(),
                record.getWorkingCopyPath(),
                record.getVersionNote(),
                Boolean.TRUE.equals(record.getIsActive()),
                record.getCreatedBy(),
                record.getCreatedAt()
        );
    }
}
