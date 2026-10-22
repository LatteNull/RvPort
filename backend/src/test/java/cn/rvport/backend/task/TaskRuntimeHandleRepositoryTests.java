package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class TaskRuntimeHandleRepositoryTests {

    @Test
    void listsWorkerTasksInStableLockOrder() throws Exception {
        try (var database = new JooqMockDatabase()) {
            var repository = new TaskRuntimeHandleRepository(database.dsl());
            var id = UUID.randomUUID();
            database.enqueueResult(database.result(new Field<?>[]{field("task_id", UUID.class)}, new Object[]{id}));
            assertThat(repository.findActiveTaskIdsByWorker("worker")).containsExactly(id);
            assertThat(database.lastExecution().normalizedSql()).contains("select distinct", "order by task_id");
            assertThat(database.lastExecution().bindings()).contains("worker", "ACTIVE", "CANCEL_REQUESTED", "CANCELLING");
        }
    }

    @Test
    void createsFindsAndFallsBackAfterConcurrentInsert() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRuntimeHandleRepository repository = new TaskRuntimeHandleRepository(database.dsl());
            Object[] row = handleRow(TaskRuntimeHandleStatus.ACTIVE, null);
            database.enqueueResult(database.result(handleFields(), row));
            database.enqueueResult(database.result(handleFields(), row));
            TaskRuntimeHandleView created = repository.createTaskHandle(
                    TestDataFixtures.TASK_ID, TestDataFixtures.PROJECT_ID, "worker-1");
            assertThat(created.workerInstanceId()).isEqualTo("worker-1");

            database.enqueueResult(database.result(handleFields()));
            database.enqueueResult(database.result(handleFields(), row));
            assertThat(repository.createTaskHandle(TestDataFixtures.TASK_ID,
                    TestDataFixtures.PROJECT_ID, "worker-1")).isEqualTo(created);

            database.enqueueResult(database.result(handleFields(), row));
            assertThat(repository.findActiveByTaskId(TestDataFixtures.TASK_ID)).contains(created);
            database.enqueueResult(database.result(handleFields()));
            assertThat(repository.findById(UUID.randomUUID())).isEmpty();
        }
    }

    @Test
    void updatesStatusesProcessesAndRedactsSensitiveErrors() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRuntimeHandleRepository repository = new TaskRuntimeHandleRepository(database.dsl());
            UUID id = UUID.randomUUID();
            for (Runnable update : new Runnable[] {
                    () -> repository.markCancelRequested(id),
                    () -> repository.markCancelling(id),
                    () -> repository.markTerminated(id, TaskRuntimeHandleStatus.TERMINATED),
                    () -> repository.markError(id, TaskRuntimeHandleStatus.FAILED, "SSH", "password=value token=abc"),
                    () -> repository.registerLocalProcess(id, 123L),
                    () -> repository.registerRemoteProcess(id, TestDataFixtures.ENVIRONMENT_ID, 44L, 45L, "marker")
            }) {
                database.enqueueRows(1);
                update.run();
                assertThat(database.lastExecution().normalizedSql()).startsWith("update task_runtime_handles");
            }
            assertThat(database.executions().get(3).bindings())
                    .anySatisfy(value -> assertThat(String.valueOf(value)).contains("password=******"));
            assertThat(database.executions().get(4).bindings()).contains(123L);
            assertThat(database.executions().get(5).bindings()).contains(44L, 45L, "marker");
        }
    }

    @Test
    void marksAllActiveWorkerHandlesLostAndPreservesNullMessage() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRuntimeHandleRepository repository = new TaskRuntimeHandleRepository(database.dsl());
            database.enqueueResult(database.result(handleFields(),
                    handleRow(TaskRuntimeHandleStatus.WORKER_LOST, "worker gone")));

            assertThat(repository.markWorkerLostByWorker("worker-1", "secret=value worker gone"))
                    .extracting(TaskRuntimeHandleView::status)
                    .containsExactly(TaskRuntimeHandleStatus.WORKER_LOST);
            assertThat(database.lastExecution().bindings())
                    .anySatisfy(value -> assertThat(String.valueOf(value)).contains("secret=******"));

            database.enqueueRows(1);
            repository.markError(UUID.randomUUID(), TaskRuntimeHandleStatus.FAILED, null, null);
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("error_code").doesNotContain("error_message");
        }
    }

    private static Field<?>[] handleFields() {
        return new Field<?>[] {
                field("id", UUID.class), field("task_id", UUID.class), field("project_id", UUID.class),
                field("worker_instance_id", String.class), field("handle_type", String.class),
                field("status", String.class), field("local_pid", Long.class), field("remote_pid", Long.class),
                field("remote_pgid", Long.class), field("environment_id", UUID.class), field("command_marker", String.class),
                field("cancel_requested_at", OffsetDateTime.class), field("started_at", OffsetDateTime.class),
                field("updated_at", OffsetDateTime.class), field("terminated_at", OffsetDateTime.class),
                field("error_code", String.class), field("error_message", String.class)
        };
    }

    private static Object[] handleRow(TaskRuntimeHandleStatus status, String errorMessage) {
        return new Object[] {UUID.fromString("00000000-0000-0000-0000-000000000099"), TestDataFixtures.TASK_ID,
                TestDataFixtures.PROJECT_ID, "worker-1", TaskRuntimeHandleType.TASK.name(), status.name(),
                null, null, null, null, null, null, TestDataFixtures.NOW, TestDataFixtures.NOW,
                status == TaskRuntimeHandleStatus.ACTIVE ? null : TestDataFixtures.NOW,
                status == TaskRuntimeHandleStatus.WORKER_LOST ? TaskErrorCode.WORKER_LOST : null, errorMessage};
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }
}
