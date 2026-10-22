package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.jooq.Record;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class TaskRuntimeHandleRepository {

    private static final Table<?> TABLE = DSL.table("task_runtime_handles");

    private final DSLContext dsl;

    public TaskRuntimeHandleRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public TaskRuntimeHandleView createTaskHandle(UUID taskId, UUID projectId, String workerInstanceId) {
        Record record = dsl.insertInto(TABLE)
                .columns(
                        field("task_id", UUID.class),
                        field("project_id", UUID.class),
                        field("worker_instance_id", String.class),
                        field("handle_type", String.class),
                        field("status", String.class),
                        field("metadata", JSONB.class)
                )
                .values(
                        taskId,
                        projectId,
                        workerInstanceId,
                        TaskRuntimeHandleType.TASK.name(),
                        TaskRuntimeHandleStatus.ACTIVE.name(),
                        JSONB.valueOf("{}")
                )
                .returning()
                .fetchOne();
        TaskRuntimeHandleView created = from(record);
        return created == null ? findActiveByTaskId(taskId).orElse(null) : created;
    }

    public Optional<TaskRuntimeHandleView> findActiveByTaskId(UUID taskId) {
        return dsl.selectFrom(TABLE)
                .where(field("task_id", UUID.class).eq(taskId)
                        .and(field("status", String.class).in(
                                TaskRuntimeHandleStatus.ACTIVE.name(),
                                TaskRuntimeHandleStatus.CANCEL_REQUESTED.name(),
                                TaskRuntimeHandleStatus.CANCELLING.name()
                        )))
                .orderBy(field("updated_at", OffsetDateTime.class).desc())
                .limit(1)
                .fetchOptional()
                .map(TaskRuntimeHandleRepository::from);
    }

    public Optional<TaskRuntimeHandleView> findById(UUID id) {
        return dsl.selectFrom(TABLE)
                .where(field("id", UUID.class).eq(id))
                .fetchOptional()
                .map(TaskRuntimeHandleRepository::from);
    }

    public List<UUID> findActiveTaskIdsByWorker(String workerId) {
        return dsl.selectDistinct(field("task_id", UUID.class)).from(TABLE)
                .where(field("worker_instance_id", String.class).eq(workerId).and(active()))
                .orderBy(field("task_id", UUID.class)).fetch(field("task_id", UUID.class));
    }

    public void markCancelRequested(UUID id) {
        updateStatus(id, TaskRuntimeHandleStatus.CANCEL_REQUESTED, null, null, false);
    }

    public void markCancelling(UUID id) {
        updateStatus(id, TaskRuntimeHandleStatus.CANCELLING, null, null, false);
    }

    public void markTerminated(UUID id, TaskRuntimeHandleStatus status) {
        updateStatus(id, status, null, null, true);
    }

    public void markError(UUID id, TaskRuntimeHandleStatus status, String errorCode, String errorMessage) {
        updateStatus(id, status, errorCode, safeMessage(errorMessage), true);
    }

    public List<TaskRuntimeHandleView> markWorkerLostByWorker(String workerInstanceId, String errorMessage) {
        OffsetDateTime now = OffsetDateTime.now();
        return dsl.update(TABLE)
                .set(field("status", String.class), TaskRuntimeHandleStatus.WORKER_LOST.name())
                .set(field("terminated_at", OffsetDateTime.class), now)
                .set(field("updated_at", OffsetDateTime.class), now)
                .set(field("error_code", String.class), TaskErrorCode.WORKER_LOST)
                .set(field("error_message", String.class), safeMessage(errorMessage))
                .where(field("worker_instance_id", String.class).eq(workerInstanceId)
                        .and(field("status", String.class).in(
                                TaskRuntimeHandleStatus.ACTIVE.name(),
                                TaskRuntimeHandleStatus.CANCEL_REQUESTED.name(),
                                TaskRuntimeHandleStatus.CANCELLING.name()
                        )))
                .returning(
                        field("id", UUID.class),
                        field("task_id", UUID.class),
                        field("project_id", UUID.class),
                        field("worker_instance_id", String.class),
                        field("handle_type", String.class),
                        field("status", String.class),
                        field("local_pid", Long.class),
                        field("remote_pid", Long.class),
                        field("remote_pgid", Long.class),
                        field("environment_id", UUID.class),
                        field("command_marker", String.class),
                        field("cancel_requested_at", OffsetDateTime.class),
                        field("started_at", OffsetDateTime.class),
                        field("updated_at", OffsetDateTime.class),
                        field("terminated_at", OffsetDateTime.class),
                        field("error_code", String.class),
                        field("error_message", String.class)
                )
                .fetch(TaskRuntimeHandleRepository::from);
    }

    public void registerLocalProcess(UUID id, long pid) {
        dsl.update(TABLE)
                .set(field("handle_type", String.class), TaskRuntimeHandleType.LOCAL_PROCESS.name())
                .set(field("local_pid", Long.class), pid)
                .set(field("updated_at", OffsetDateTime.class), OffsetDateTime.now())
                .where(field("id", UUID.class).eq(id).and(active()))
                .execute();
    }

    public void registerRemoteProcess(UUID id, UUID environmentId, Long remotePid, Long remotePgid, String marker) {
        dsl.update(TABLE)
                .set(field("handle_type", String.class), TaskRuntimeHandleType.REMOTE_PROCESS.name())
                .set(field("environment_id", UUID.class), environmentId)
                .set(field("remote_pid", Long.class), remotePid)
                .set(field("remote_pgid", Long.class), remotePgid)
                .set(field("command_marker", String.class), marker)
                .set(field("updated_at", OffsetDateTime.class), OffsetDateTime.now())
                .where(field("id", UUID.class).eq(id).and(active()))
                .execute();
    }

    private void updateStatus(
            UUID id,
            TaskRuntimeHandleStatus status,
            String errorCode,
            String errorMessage,
            boolean terminal
    ) {
        var update = dsl.update(TABLE)
                .set(field("status", String.class), status.name())
                .set(field("updated_at", OffsetDateTime.class), OffsetDateTime.now());
        if (status == TaskRuntimeHandleStatus.CANCEL_REQUESTED || status == TaskRuntimeHandleStatus.CANCELLING) {
            update = update.set(field("cancel_requested_at", OffsetDateTime.class), OffsetDateTime.now());
        }
        if (terminal) {
            update = update.set(field("terminated_at", OffsetDateTime.class), OffsetDateTime.now());
        }
        if (errorCode != null) {
            update = update.set(field("error_code", String.class), errorCode);
        }
        if (errorMessage != null) {
            update = update.set(field("error_message", String.class), errorMessage);
        }
        update.where(field("id", UUID.class).eq(id).and(active())).execute();
    }

    private static org.jooq.Condition active() {
        return field("status", String.class).in("ACTIVE", "CANCEL_REQUESTED", "CANCELLING");
    }

    private static TaskRuntimeHandleView from(Record record) {
        if (record == null) {
            return null;
        }
        return new TaskRuntimeHandleView(
                record.get(field("id", UUID.class)),
                record.get(field("task_id", UUID.class)),
                record.get(field("project_id", UUID.class)),
                record.get(field("worker_instance_id", String.class)),
                TaskRuntimeHandleType.valueOf(record.get(field("handle_type", String.class))),
                TaskRuntimeHandleStatus.valueOf(record.get(field("status", String.class))),
                record.get(field("local_pid", Long.class)),
                record.get(field("remote_pid", Long.class)),
                record.get(field("remote_pgid", Long.class)),
                record.get(field("environment_id", UUID.class)),
                record.get(field("command_marker", String.class)),
                record.get(field("cancel_requested_at", OffsetDateTime.class)),
                record.get(field("started_at", OffsetDateTime.class)),
                record.get(field("updated_at", OffsetDateTime.class)),
                record.get(field("terminated_at", OffsetDateTime.class)),
                record.get(field("error_code", String.class)),
                record.get(field("error_message", String.class))
        );
    }

    private static <T> org.jooq.Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }

    private String safeMessage(String value) {
        if (value == null) {
            return null;
        }
        return value.replaceAll("(?i)(password|token|privateKey|private_key|passphrase|secret)\\S*", "$1=******");
    }
}
