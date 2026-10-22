package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.TaskLogs.TASK_LOGS;

import cn.rvport.backend.jooq.tables.records.TaskLogsRecord;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.springframework.stereotype.Repository;

@Repository
public class TaskLogRepository {

    private final DSLContext dsl;

    public TaskLogRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public long count(UUID taskId, TaskLogType logType) {
        return dsl.selectCount()
                .from(TASK_LOGS)
                .where(filter(taskId, logType))
                .fetchOne(0, long.class);
    }

    public List<TaskLogResponse> list(UUID taskId, TaskLogType logType, int page, int pageSize) {
        return dsl.selectFrom(TASK_LOGS)
                .where(filter(taskId, logType))
                .orderBy(TASK_LOGS.CREATED_AT.desc(), TASK_LOGS.ID.asc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(TaskLogResponse::from);
    }

    public Optional<TaskLogsRecord> findForTask(UUID taskId, UUID logId) {
        return dsl.selectFrom(TASK_LOGS)
                .where(TASK_LOGS.TASK_ID.eq(taskId).and(TASK_LOGS.ID.eq(logId)))
                .fetchOptional();
    }

    public Optional<TaskLogResponse> findLatest(UUID taskId, TaskLogType logType) {
        return dsl.selectFrom(TASK_LOGS)
                .where(filter(taskId, logType))
                .orderBy(TASK_LOGS.CREATED_AT.desc(), TASK_LOGS.ID.desc())
                .limit(1)
                .fetchOptional(TaskLogResponse::from);
    }

    public Optional<TaskLogsRecord> findLatestRecord(UUID taskId, TaskLogType logType) {
        return dsl.selectFrom(TASK_LOGS)
                .where(filter(taskId, logType))
                .orderBy(TASK_LOGS.CREATED_AT.desc(), TASK_LOGS.ID.desc())
                .limit(1)
                .fetchOptional();
    }

    public TaskLogResponse create(
            UUID projectId,
            UUID taskId,
            TaskLogType logType,
            String filePath,
            long sizeBytes,
            long lineCount,
            String sha256,
            String excerpt
    ) {
        TaskLogsRecord record = dsl.insertInto(TASK_LOGS)
                .set(TASK_LOGS.PROJECT_ID, projectId)
                .set(TASK_LOGS.TASK_ID, taskId)
                .set(TASK_LOGS.LOG_TYPE, logType.name())
                .set(TASK_LOGS.FILE_PATH, filePath)
                .set(TASK_LOGS.SIZE_BYTES, sizeBytes)
                .set(TASK_LOGS.LINE_COUNT, lineCount)
                .set(TASK_LOGS.SHA256, sha256)
                .set(TASK_LOGS.EXCERPT, excerpt)
                .returning()
                .fetchOne();
        return TaskLogResponse.from(record);
    }

    private Condition filter(UUID taskId, TaskLogType logType) {
        Condition condition = TASK_LOGS.TASK_ID.eq(taskId);
        if (logType != null) {
            condition = condition.and(TASK_LOGS.LOG_TYPE.eq(logType.name()));
        }
        return condition;
    }
}
