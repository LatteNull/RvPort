package cn.rvport.backend.task;

import cn.rvport.backend.jooq.tables.records.TaskLogEventsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record TaskLogEventView(
        long id,
        UUID projectId,
        UUID taskId,
        TaskLogType logType,
        long sequence,
        String content,
        OffsetDateTime createdAt
) {
    public static TaskLogEventView from(TaskLogEventsRecord record) {
        return new TaskLogEventView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                TaskLogType.valueOf(record.getLogType()),
                record.getSequence(),
                record.getContent(),
                record.getCreatedAt()
        );
    }
}
