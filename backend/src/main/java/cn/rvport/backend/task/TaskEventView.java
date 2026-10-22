package cn.rvport.backend.task;

import cn.rvport.backend.jooq.tables.records.TaskEventsRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record TaskEventView(
        long id,
        String eventId,
        UUID projectId,
        UUID taskId,
        String taskType,
        String eventType,
        TaskStatus status,
        Integer progress,
        String message,
        String logLevel,
        String logExcerpt,
        String stageId,
        TaskEventResource resource,
        List<String> changedFields,
        OffsetDateTime occurredAt
) {
    public static TaskEventView from(TaskEventsRecord record) {
        return from(record, null, null, TaskEventResource.empty(), List.of());
    }

    public static TaskEventView from(
            TaskEventsRecord record,
            String taskType,
            String taskStageId,
            TaskEventResource resource,
            List<String> changedFields
    ) {
        return new TaskEventView(
                record.getId(),
                record.getEventId(),
                record.getProjectId(),
                record.getTaskId(),
                taskType,
                record.getEventType(),
                record.getStatus() == null ? null : TaskStatus.valueOf(record.getStatus()),
                record.getProgress(),
                record.getMessage(),
                record.getLogLevel(),
                record.getLogExcerpt(),
                record.getStageId() == null ? taskStageId : record.getStageId(),
                resource == null ? TaskEventResource.empty() : resource,
                changedFields == null ? List.of() : changedFields,
                record.getOccurredAt()
        );
    }
}
