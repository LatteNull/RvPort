package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import cn.rvport.backend.jooq.tables.records.TaskEventsRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.jooq.Record;
import org.springframework.stereotype.Repository;

@Repository
public class TaskEventRepository {

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public TaskEventRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public TaskEventView append(
            UUID projectId,
            UUID taskId,
            TaskEventType eventType,
            TaskStatus status,
            Integer progress,
            String message,
            String logLevel,
            String logExcerpt
    ) {
        TaskEventMetadata metadata = taskId == null ? TaskEventMetadata.empty() : metadataForTask(taskId);
        return append(projectId, taskId, eventType, status, progress, message, logLevel, logExcerpt,
                metadata.stageId(), metadata.resource(), List.of());
    }

    public TaskEventView appendProjectContextChanged(
            UUID projectId,
            String stageId,
            TaskEventResource resource,
            List<String> changedFields,
            String message
    ) {
        return append(projectId, null, TaskEventType.PROJECT_CONTEXT_CHANGED, null, null, message, null, null,
                stageId, resource, changedFields);
    }

    private TaskEventView append(
            UUID projectId,
            UUID taskId,
            TaskEventType eventType,
            TaskStatus status,
            Integer progress,
            String message,
            String logLevel,
            String logExcerpt,
            String stageId,
            TaskEventResource resource,
            List<String> changedFields
    ) {
        TaskEventsRecord record = dsl.insertInto(TASK_EVENTS)
                .set(TASK_EVENTS.EVENT_ID, "evt_" + UUID.randomUUID())
                .set(TASK_EVENTS.PROJECT_ID, projectId)
                .set(TASK_EVENTS.TASK_ID, taskId)
                .set(TASK_EVENTS.EVENT_TYPE, eventType.value())
                .set(TASK_EVENTS.STATUS, status == null ? null : status.name())
                .set(TASK_EVENTS.PROGRESS, progress)
                .set(TASK_EVENTS.MESSAGE, message)
                .set(TASK_EVENTS.LOG_LEVEL, logLevel)
                .set(TASK_EVENTS.LOG_EXCERPT, logExcerpt)
                .set(TASK_EVENTS.STAGE_ID, blankToNull(stageId))
                .set(TASK_EVENTS.RESOURCE, JSONB.valueOf(toJson(resource == null ? Map.of() : resource.toMap())))
                .set(TASK_EVENTS.CHANGED_FIELDS, JSONB.valueOf(toJson(changedFields == null ? List.of() : changedFields)))
                .set(TASK_EVENTS.OCCURRED_AT, OffsetDateTime.now())
                .returning()
                .fetchOne();
        TaskEventMetadata metadata = taskId == null ? TaskEventMetadata.empty() : metadataForTask(taskId);
        return TaskEventView.from(record, metadata.taskType(), metadata.stageId(), resource(record, metadata.resource()), changedFields(record));
    }

    public List<TaskEventView> listAfter(UUID projectId, long lastEventId, int limit) {
        return dsl.select(TASK_EVENTS.fields())
                .select(TASKS.TYPE)
                .select(TASKS.STAGE_ID)
                .select(TASKS.RESOURCE_TYPE)
                .select(TASKS.RESOURCE_ID)
                .select(TASKS.RESOURCE_MODE)
                .select(TASKS.ENVIRONMENT_ROLE)
                .from(TASK_EVENTS)
                .leftJoin(TASKS).on(TASKS.ID.eq(TASK_EVENTS.TASK_ID))
                .where(TASK_EVENTS.PROJECT_ID.eq(projectId)
                        .and(TASK_EVENTS.ID.gt(lastEventId)))
                .orderBy(TASK_EVENTS.ID.asc())
                .limit(limit)
                .fetch(this::mapEvent);
    }

    public Optional<TaskEventView> findByProjectIdAndId(UUID projectId, long eventId) {
        return dsl.select(TASK_EVENTS.fields())
                .select(TASKS.TYPE)
                .select(TASKS.STAGE_ID)
                .select(TASKS.RESOURCE_TYPE)
                .select(TASKS.RESOURCE_ID)
                .select(TASKS.RESOURCE_MODE)
                .select(TASKS.ENVIRONMENT_ROLE)
                .from(TASK_EVENTS)
                .leftJoin(TASKS).on(TASKS.ID.eq(TASK_EVENTS.TASK_ID))
                .where(TASK_EVENTS.PROJECT_ID.eq(projectId)
                        .and(TASK_EVENTS.ID.eq(eventId)))
                .fetchOptional(this::mapEvent);
    }

    public long latestId(UUID projectId) {
        Long latestId = dsl.select(TASK_EVENTS.ID)
                .from(TASK_EVENTS)
                .where(TASK_EVENTS.PROJECT_ID.eq(projectId))
                .orderBy(TASK_EVENTS.ID.desc())
                .limit(1)
                .fetchOne(TASK_EVENTS.ID);
        return latestId == null ? 0L : latestId;
    }

    private TaskEventView mapEvent(Record record) {
        TaskEventsRecord event = record.into(TASK_EVENTS);
        TaskEventResource taskResource = new TaskEventResource(
                firstNonBlank(record.get(TASKS.RESOURCE_TYPE), record.get(TASKS.TYPE)),
                record.get(TASKS.RESOURCE_ID) == null ? event.getTaskId() : record.get(TASKS.RESOURCE_ID),
                record.get(TASKS.RESOURCE_MODE),
                record.get(TASKS.ENVIRONMENT_ROLE)
        );
        return TaskEventView.from(event, record.get(TASKS.TYPE), record.get(TASKS.STAGE_ID),
                resource(event, taskResource), changedFields(event));
    }

    private TaskEventMetadata metadataForTask(UUID taskId) {
        Record record = dsl.select(TASKS.TYPE, TASKS.STAGE_ID, TASKS.RESOURCE_TYPE, TASKS.RESOURCE_ID, TASKS.RESOURCE_MODE, TASKS.ENVIRONMENT_ROLE)
                .from(TASKS)
                .where(TASKS.ID.eq(taskId))
                .fetchOne();
        if (record == null) {
            return TaskEventMetadata.empty();
        }
        return new TaskEventMetadata(
                record.get(TASKS.TYPE),
                record.get(TASKS.STAGE_ID),
                new TaskEventResource(
                        firstNonBlank(record.get(TASKS.RESOURCE_TYPE), record.get(TASKS.TYPE)),
                        record.get(TASKS.RESOURCE_ID) == null ? taskId : record.get(TASKS.RESOURCE_ID),
                        record.get(TASKS.RESOURCE_MODE),
                        record.get(TASKS.ENVIRONMENT_ROLE)
                )
        );
    }

    private TaskEventResource resource(TaskEventsRecord event, TaskEventResource fallback) {
        if (event.getResource() == null || event.getResource().data() == null || event.getResource().data().isBlank()) {
            return fallback == null ? TaskEventResource.empty() : fallback;
        }
        try {
            TaskEventResource parsed = objectMapper.readValue(event.getResource().data(), TaskEventResource.class);
            if (parsed.type() == null && parsed.id() == null && fallback != null) {
                return fallback;
            }
            return parsed;
        } catch (JsonProcessingException ex) {
            return fallback == null ? TaskEventResource.empty() : fallback;
        }
    }

    private List<String> changedFields(TaskEventsRecord event) {
        if (event.getChangedFields() == null || event.getChangedFields().data() == null || event.getChangedFields().data().isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(event.getChangedFields().data(), new TypeReference<>() {
            });
        } catch (JsonProcessingException ex) {
            return List.of();
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            return value instanceof List ? "[]" : "{}";
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String firstNonBlank(String first, String second) {
        return first == null || first.isBlank() ? second : first;
    }

    private record TaskEventMetadata(String taskType, String stageId, TaskEventResource resource) {
        static TaskEventMetadata empty() {
            return new TaskEventMetadata(null, null, TaskEventResource.empty());
        }
    }
}
