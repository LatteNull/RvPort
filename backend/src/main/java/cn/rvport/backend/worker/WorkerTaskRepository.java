package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.Record;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class WorkerTaskRepository {

    private static final Table<?> TASK_RUNTIME_HANDLES = DSL.table(DSL.name("task_runtime_handles"));
    private static final Table<?> TASKS = DSL.table(DSL.name("tasks"));
    private static final Table<?> PROJECTS = DSL.table(DSL.name("projects"));

    private final DSLContext dsl;

    public WorkerTaskRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public List<WorkerTaskResponse> findRunningTasks(String workerInstanceId) {
        return dsl.select(
                        field("t", "id", java.util.UUID.class),
                        field("t", "project_id", java.util.UUID.class),
                        field("p", "name", String.class),
                        field("t", "type", String.class),
                        field("t", "status", String.class),
                        field("t", "progress", Integer.class),
                        field("t", "message", String.class),
                        field("t", "started_at", OffsetDateTime.class)
                )
                .from(TASK_RUNTIME_HANDLES.as("h"))
                .join(TASKS.as("t"))
                .on(field("h", "task_id", java.util.UUID.class).eq(field("t", "id", java.util.UUID.class)))
                .leftJoin(PROJECTS.as("p"))
                .on(field("t", "project_id", java.util.UUID.class).eq(field("p", "id", java.util.UUID.class)))
                .where(field("h", "worker_instance_id", String.class).eq(workerInstanceId)
                        .and(field("h", "status", String.class).in(
                                TaskRuntimeHandleStatus.ACTIVE.name(),
                                TaskRuntimeHandleStatus.CANCEL_REQUESTED.name(),
                                TaskRuntimeHandleStatus.CANCELLING.name()
                        ))
                        .and(field("t", "status", String.class).eq(TaskStatus.RUNNING.name())))
                .orderBy(field("t", "started_at", OffsetDateTime.class).asc().nullsLast())
                .fetch(WorkerTaskRepository::from);
    }

    private static WorkerTaskResponse from(Record record) {
        return new WorkerTaskResponse(
                record.get(field("t", "id", java.util.UUID.class)),
                record.get(field("t", "project_id", java.util.UUID.class)),
                record.get(field("p", "name", String.class)),
                record.get(field("t", "type", String.class)),
                TaskStatus.valueOf(record.get(field("t", "status", String.class))),
                valueOrZero(record.get(field("t", "progress", Integer.class))),
                record.get(field("t", "message", String.class)),
                record.get(field("t", "started_at", OffsetDateTime.class))
        );
    }

    private static int valueOrZero(Integer value) {
        return value == null ? 0 : value;
    }

    private static <T> Field<T> field(String tableAlias, String name, Class<T> type) {
        return DSL.field(DSL.name(tableAlias, name), type);
    }
}
