package cn.rvport.backend.task;

import cn.rvport.backend.jooq.tables.records.TaskLogsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskLogResponse(
        UUID id,
        UUID taskId,
        UUID projectId,
        TaskLogType logType,
        Long sizeBytes,
        Long lineCount,
        String sha256,
        String excerpt,
        OffsetDateTime createdAt
) {
    public static TaskLogResponse from(TaskLogsRecord record) {
        return new TaskLogResponse(
                record.getId(),
                record.getTaskId(),
                record.getProjectId(),
                TaskLogType.valueOf(record.getLogType()),
                record.getSizeBytes(),
                record.getLineCount(),
                record.getSha256(),
                record.getExcerpt(),
                record.getCreatedAt()
        );
    }
}
