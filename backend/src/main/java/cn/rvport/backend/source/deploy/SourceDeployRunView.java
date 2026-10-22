package cn.rvport.backend.source.deploy;

import cn.rvport.backend.jooq.tables.records.SourceDeployRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;

public record SourceDeployRunView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        String remotePath,
        SourceDeployStrategy deployStrategy,
        boolean force,
        TaskStatus status,
        Integer fileCount,
        Long totalBytes,
        Integer exitCode,
        JSONB summary,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt
) {
    public SourceDeployRunView(
            UUID id,
            UUID projectId,
            UUID taskId,
            UUID sourceRevisionId,
            UUID environmentId,
            String remotePath,
            SourceDeployStrategy deployStrategy,
            boolean force,
            TaskStatus status,
            Integer fileCount,
            Long totalBytes,
            Integer exitCode,
            JSONB summary,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            OffsetDateTime createdAt
    ) {
        this(id, projectId, taskId, sourceRevisionId, environmentId, null, remotePath, deployStrategy, force,
                status, fileCount, totalBytes, exitCode, summary, startedAt, finishedAt, createdAt);
    }

    public static SourceDeployRunView from(SourceDeployRunsRecord record) {
        return new SourceDeployRunView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getSourceRevisionId(),
                record.getEnvironmentId(),
                record.getEnvironmentConfigVersion(),
                record.getRemotePath(),
                SourceDeployStrategy.valueOf(record.getDeployStrategy()),
                Boolean.TRUE.equals(record.getForce()),
                TaskStatus.valueOf(record.getStatus()),
                record.getFileCount(),
                record.getTotalBytes(),
                record.getExitCode(),
                record.getSummary(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getCreatedAt()
        );
    }

    public Map<String, Object> resource() {
        return Map.of("type", "SOURCE_DEPLOY", "id", id);
    }
}
