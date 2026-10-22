package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.TaskLogEvents.TASK_LOG_EVENTS;

import cn.rvport.backend.jooq.tables.records.TaskLogEventsRecord;
import java.util.List;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;
import org.jooq.DSLContext;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class TaskLogEventRepository {

    private final DSLContext dsl;

    public TaskLogEventRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public List<TaskLogEventView> append(UUID projectId, UUID taskId, TaskLogType logType, List<String> chunks) {
        if (chunks == null || chunks.isEmpty()) {
            return List.of();
        }
        long startSequence = nextSequence(taskId);
        var insert = dsl.insertInto(
                TASK_LOG_EVENTS,
                TASK_LOG_EVENTS.PROJECT_ID,
                TASK_LOG_EVENTS.TASK_ID,
                TASK_LOG_EVENTS.LOG_TYPE,
                TASK_LOG_EVENTS.SEQUENCE,
                TASK_LOG_EVENTS.CONTENT
        );
        for (int i = 0; i < chunks.size(); i++) {
            insert = insert.values(projectId, taskId, logType.name(), startSequence + i, chunks.get(i));
        }
        return insert
                .returning()
                .fetch(TaskLogEventView::from);
    }

    public List<TaskLogEventView> listAfter(UUID taskId, long lastEventId, int limit) {
        return dsl.selectFrom(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.eq(taskId)
                        .and(TASK_LOG_EVENTS.ID.gt(lastEventId)))
                .orderBy(TASK_LOG_EVENTS.ID.asc())
                .limit(limit)
                .fetch(TaskLogEventView::from);
    }

    public long latestEventId(UUID taskId) {
        Long latest = dsl.select(DSL.max(TASK_LOG_EVENTS.ID))
                .from(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.eq(taskId))
                .fetchOne(0, Long.class);
        return latest == null ? 0L : latest;
    }

    public Map<UUID, Long> latestEventIds(Collection<UUID> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return Collections.emptyMap();
        }
        return dsl.select(TASK_LOG_EVENTS.TASK_ID, DSL.max(TASK_LOG_EVENTS.ID).as("latest_event_id"))
                .from(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.in(taskIds))
                .groupBy(TASK_LOG_EVENTS.TASK_ID)
                .fetch()
                .stream()
                .collect(Collectors.toMap(
                        record -> record.get(TASK_LOG_EVENTS.TASK_ID),
                        record -> record.get("latest_event_id", Long.class)
                ));
    }

    public Optional<TaskLogEventView> findByTaskIdAndId(UUID taskId, long eventId) {
        return dsl.selectFrom(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.eq(taskId)
                        .and(TASK_LOG_EVENTS.ID.eq(eventId)))
                .fetchOptional(TaskLogEventView::from);
    }

    public long count(UUID taskId) {
        return dsl.selectCount()
                .from(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.eq(taskId))
                .fetchOne(0, long.class);
    }

    private long nextSequence(UUID taskId) {
        Long max = dsl.select(DSL.max(TASK_LOG_EVENTS.SEQUENCE))
                .from(TASK_LOG_EVENTS)
                .where(TASK_LOG_EVENTS.TASK_ID.eq(taskId))
                .fetchOne(0, Long.class);
        return max == null ? 1L : max + 1L;
    }
}
