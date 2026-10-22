package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class WorkerTaskRepositoryTests {
    private static final UUID TASK_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void findsRunningTasksAndDefaultsNullProgressToZero() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerTaskRepository repository = new WorkerTaskRepository(database.dsl());
            Field<?>[] fields = fields();
            database.enqueueResult(database.result(fields,
                    new Object[]{TASK_ID, PROJECT_ID, "Project", "KB_SCAN", TaskStatus.RUNNING.name(), 75, "running", NOW},
                    new Object[]{UUID.randomUUID(), PROJECT_ID, null, "REPORT", TaskStatus.RUNNING.name(), null, null, null}));
            assertThat(repository.findRunningTasks("worker-1")).hasSize(2)
                    .extracting(WorkerTaskResponse::progress).containsExactly(75, 0);
            assertThat(database.lastExecution().normalizedSql()).contains("worker_instance_id =", "status in", "t.status =", "started_at asc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void propagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerTaskRepository repository = new WorkerTaskRepository(database.dsl());
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findRunningTasks("worker-1"))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class).hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static Field<?>[] fields() {
        return new Field<?>[]{field("t", "id", UUID.class), field("t", "project_id", UUID.class),
                field("p", "name", String.class), field("t", "type", String.class), field("t", "status", String.class),
                field("t", "progress", Integer.class), field("t", "message", String.class),
                field("t", "started_at", OffsetDateTime.class)};
    }

    private static <T> Field<T> field(String table, String name, Class<T> type) {
        return DSL.field(DSL.name(table, name), type);
    }
}
