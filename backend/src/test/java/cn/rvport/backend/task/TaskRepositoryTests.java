package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.TasksRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.exception.DataAccessException;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class TaskRepositoryTests {

    @Test
    void createsTaskAndNormalizesOptionalMetadata() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TasksRecord record = taskRecord(TaskStatus.PENDING);
            database.enqueueRecord(record);
            TaskRepository repository = new TaskRepository(database.dsl());
            TaskCreateCommand command = new TaskCreateCommand(
                    TestDataFixtures.PROJECT_ID, "KB_SCAN", Map.of("scope", "ALL"),
                    TestDataFixtures.USER_ID, 1800, "queued", " KB_SCAN ", "  ",
                    TestDataFixtures.TASK_ID, " DEFAULT ", null);

            TaskView created = repository.create(command, "{\"scope\":\"ALL\"}");

            assertThat(created.id()).isEqualTo(TestDataFixtures.TASK_ID);
            assertThat(created.status()).isEqualTo(TaskStatus.PENDING);
            assertThat(database.lastExecution().normalizedSql()).contains("insert into tasks").contains("returning");
            assertThat(database.lastExecution().bindings())
                    .contains("KB_SCAN", "PENDING", "queued", "KB_SCAN", "DEFAULT")
                    .containsNull();
            database.verifyComplete();
        }
    }

    @Test
    void findsCountsAndListsWithDynamicFiltersAndPagination() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            TasksRecord record = taskRecord(TaskStatus.RUNNING);

            database.enqueueRecord(record);
            assertThat(repository.findById(record.getId())).contains(TestDataFixtures.task());

            database.enqueueRecord(record);
            assertThat(repository.findRecordById(record.getId())).contains(record);

            database.enqueueResult(database.result(
                    new Field<?>[] {DSL.field("count", Integer.class)}, new Object[] {2}));
            assertThat(repository.count(record.getProjectId(), TaskStatus.RUNNING, " KB_SCAN ")).isEqualTo(2);
            assertThat(database.lastExecution().normalizedSql())
                    .contains("status = ?")
                    .contains("type = ?");
            assertThat(database.lastExecution().bindings()).contains("RUNNING", "KB_SCAN");

            database.enqueueRecord(record);
            assertThat(repository.list(record.getProjectId(), null, " ", 2, 10)).containsExactly(TestDataFixtures.task());
            assertThat(database.lastExecution().normalizedSql())
                    .contains("offset ? rows")
                    .contains("fetch next ? rows only");
            assertThat(database.lastExecution().bindings()).endsWith(10L, 10L);
        }
    }

    @Test
    void handlesEmptyAndPopulatedResourceLookups() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            assertThat(repository.findByIds(null)).isEmpty();
            assertThat(repository.findByIds(List.of())).isEmpty();
            assertThat(repository.findLatestByStageAndResources(TestDataFixtures.PROJECT_ID, "KB_SCAN", null)).isEmpty();
            assertThat(repository.findLatestByStageAndResourceVersions(
                    TestDataFixtures.PROJECT_ID, "KB_SCAN", Map.of())).isEmpty();
            assertThat(database.executions()).isEmpty();

            TasksRecord record = taskRecord(TaskStatus.RUNNING);
            database.enqueueRecord(record);
            assertThat(repository.findByIds(List.of(record.getId())))
                    .containsEntry(record.getId(), TestDataFixtures.task());

            database.enqueueRecord(record);
            assertThat(repository.findLatestByStage(record.getProjectId(), "KB_SCAN")).isPresent();
            assertThat(database.lastExecution().normalizedSql())
                    .contains("case when tasks.status in")
                    .contains("fetch next ? rows only");

            database.enqueueRecord(record);
            assertThat(repository.findLatestByStageAndResources(
                    record.getProjectId(), "KB_SCAN", List.of(record.getResourceId()))).isPresent();
            assertThat(database.lastExecution().normalizedSql()).contains("resource_id in");

            database.enqueueRecord(record);
            assertThat(repository.findLatestByStageAndResourceVersions(
                    record.getProjectId(), "KB_SCAN", Map.of(record.getResourceId(), 2L))).isPresent();
            assertThat(database.lastExecution().normalizedSql())
                    .contains("environmentConfigVersion")
                    .contains("resource_id = cast(? as uuid)");
            assertThat(database.lastExecution().bindings()).contains(record.getResourceId(), "2");
        }
    }

    @Test
    void returnsNullWhenConditionalStatusUpdatesLoseTheRace() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            assertThat(repository.markQueued(TestDataFixtures.TASK_ID)).isNull();
            assertThat(database.lastExecution().normalizedSql()).contains("status = ?");

            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            assertThat(repository.claim(TestDataFixtures.TASK_ID, "claimed")).isNull();

            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            assertThat(repository.failRunningWorkerLost(TestDataFixtures.TASK_ID, "worker lost")).isNull();

            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            assertThat(repository.cancelPendingOrQueued(TestDataFixtures.TASK_ID)).isNull();

            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            assertThat(repository.cancelRunning(TestDataFixtures.TASK_ID, TestDataFixtures.USER_ID, "cancel")).isNull();
        }
    }

    @Test
    void appliesProgressRetryCompletionCancellationAndWorkerLostTransitions() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());

            database.enqueueRecord(taskRecord(TaskStatus.RUNNING));
            assertThat(repository.updateProgress(TestDataFixtures.TASK_ID, 75, "working").progress()).isEqualTo(50);
            assertThat(database.lastExecution().bindings()).contains(75, "working");

            database.enqueueRecord(taskRecord(TaskStatus.QUEUED));
            assertThat(repository.markRetry(TestDataFixtures.TASK_ID, 2, "retry", "NETWORK", "timeout").status())
                    .isEqualTo(TaskStatus.QUEUED);

            database.enqueueRecord(taskRecord(TaskStatus.SUCCEEDED));
            assertThat(repository.complete(TestDataFixtures.TASK_ID, TaskStatus.SUCCEEDED, "done", null, null).status())
                    .isEqualTo(TaskStatus.SUCCEEDED);
            assertThat(database.lastExecution().normalizedSql()).contains("progress = ?");
            assertThat(database.lastExecution().bindings()).contains(100);

            database.enqueueRecord(taskRecord(TaskStatus.FAILED));
            assertThat(repository.complete(TestDataFixtures.TASK_ID, TaskStatus.FAILED, "failed", "E", "bad").status())
                    .isEqualTo(TaskStatus.FAILED);
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("progress = ?");

            database.enqueueRecord(taskRecord(TaskStatus.FAILED));
            assertThat(repository.failRunningWorkerLost(TestDataFixtures.TASK_ID, "lost").errorCode())
                    .isEqualTo(null);
            assertThat(database.lastExecution().bindings()).contains(TaskErrorCode.WORKER_LOST);

            database.enqueueRecord(taskRecord(TaskStatus.CANCELLED));
            assertThat(repository.cancelPendingOrQueued(TestDataFixtures.TASK_ID, TestDataFixtures.USER_ID, "user").status())
                    .isEqualTo(TaskStatus.CANCELLED);
            assertThat(database.lastExecution().bindings()).contains(TestDataFixtures.USER_ID, "user");

            database.enqueueRecord(taskRecord(TaskStatus.CANCELLED));
            assertThat(repository.cancelRunning(TestDataFixtures.TASK_ID, TestDataFixtures.USER_ID, "user").status())
                    .isEqualTo(TaskStatus.CANCELLED);
        }
    }

    @Test
    void fallsBackToExistingTaskWhenCompletionCannotUpdateCancelledTask() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.Tasks.TASKS.fields()));
            database.enqueueRecord(taskRecord(TaskStatus.CANCELLED));

            TaskView result = repository.complete(TestDataFixtures.TASK_ID, TaskStatus.FAILED, "late", "E", "late");

            assertThat(result.status()).isEqualTo(TaskStatus.CANCELLED);
            assertThat(database.executions()).hasSize(2);
        }
    }

    @Test
    void rejectsLateWritesAndLocksReconciliationTask() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            var fields = cn.rvport.backend.jooq.tables.Tasks.TASKS.fields();
            database.enqueueResult(database.result(fields));
            assertThat(repository.completeIfActive(TestDataFixtures.TASK_ID, TaskStatus.SUCCEEDED, "late", null, null)).isNull();
            assertThat(database.lastExecution().normalizedSql()).contains("status in");
            assertThat(database.lastExecution().bindings()).contains("PENDING", "QUEUED", "RUNNING");
            database.enqueueResult(database.result(fields));
            assertThat(repository.markRetry(TestDataFixtures.TASK_ID, 1, "retry", "E", "late")).isNull();
            assertThat(database.lastExecution().bindings()).contains("RUNNING");
            assertThat(database.lastExecution().normalizedSql()).contains("tasks.status = ?");
            database.enqueueResult(database.result(fields));
            assertThat(repository.updateProgress(TestDataFixtures.TASK_ID, 90, "late")).isNull();
            assertThat(database.lastExecution().normalizedSql()).contains("tasks.status = ?");
            assertThat(database.lastExecution().bindings()).contains("RUNNING");
            database.enqueueResult(database.result(fields));
            assertThat(repository.lockById(TestDataFixtures.TASK_ID)).isNull();
            database.enqueueRecord(taskRecord(TaskStatus.FAILED));
            assertThat(repository.lockById(TestDataFixtures.TASK_ID).status()).isEqualTo(TaskStatus.FAILED);
            assertThat(database.lastExecution().normalizedSql()).contains("for update");
            database.verifyComplete();
        }
    }

    @Test
    void findsPendingTasksAndClassifiesTerminalStates() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskRepository repository = new TaskRepository(database.dsl());
            database.enqueueRecord(taskRecord(TaskStatus.PENDING));

            assertThat(repository.findPendingBefore(TestDataFixtures.NOW.plusHours(1), 5)).hasSize(1);
            assertThat(database.lastExecution().normalizedSql())
                    .contains("created_at <")
                    .contains("order by tasks.created_at asc");
            assertThat(repository.isTerminal(TaskStatus.SUCCEEDED)).isTrue();
            assertThat(repository.isTerminal(TaskStatus.FAILED)).isTrue();
            assertThat(repository.isTerminal(TaskStatus.CANCELLED)).isTrue();
            assertThat(repository.isTerminal(TaskStatus.TIMEOUT)).isTrue();
            assertThat(repository.isTerminal(TaskStatus.RUNNING)).isFalse();
        }
    }

    @Test
    void propagatesDatabaseErrors() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            database.enqueueFailure(new SQLException("database unavailable"));
            TaskRepository repository = new TaskRepository(database.dsl());

            assertThatThrownBy(() -> repository.findById(TestDataFixtures.TASK_ID))
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("database unavailable");
        }
    }

    private static TasksRecord taskRecord(TaskStatus status) {
        return new TasksRecord(
                TestDataFixtures.TASK_ID,
                TestDataFixtures.PROJECT_ID,
                "KB_SCAN",
                status.name(),
                50,
                "running",
                JSONB.valueOf("{}"),
                TestDataFixtures.USER_ID,
                TestDataFixtures.NOW,
                TestDataFixtures.NOW,
                TestDataFixtures.NOW,
                status == TaskStatus.RUNNING ? null : TestDataFixtures.NOW,
                1800,
                null,
                null,
                0,
                null,
                null,
                null,
                "KB_SCAN",
                "KB_SCAN_RUN",
                TestDataFixtures.TASK_ID,
                "DEFAULT",
                "TARGET_RISCV"
        );
    }
}
