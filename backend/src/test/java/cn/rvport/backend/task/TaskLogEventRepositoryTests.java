package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.TaskLogEventsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.exception.DataAccessException;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class TaskLogEventRepositoryTests {

    @Test
    void appendShortCircuitsEmptyChunksAndAllocatesSequences() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskLogEventRepository repository = new TaskLogEventRepository(database.dsl());
            assertThat(repository.append(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    TaskLogType.STDOUT, null)).isEmpty();
            assertThat(repository.append(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    TaskLogType.STDOUT, List.of())).isEmpty();
            assertThat(database.executions()).isEmpty();

            database.enqueueResult(database.result(new Field<?>[] {DSL.field("max", Long.class)},
                    new Object[] {null}));
            database.enqueueResult(database.result(
                    cn.rvport.backend.jooq.tables.TaskLogEvents.TASK_LOG_EVENTS.fields(),
                    event(1, 1, "one").intoArray(), event(2, 2, "two").intoArray()));

            List<TaskLogEventView> appended = repository.append(TestDataFixtures.PROJECT_ID,
                    TestDataFixtures.TASK_ID, TaskLogType.STDOUT, List.of("one", "two"));

            assertThat(appended).extracting(TaskLogEventView::sequence).containsExactly(1L, 2L);
            assertThat(database.lastExecution().normalizedSql()).contains("insert into task_log_events");
            assertThat(database.lastExecution().bindings()).contains("one", "two");
        }
    }

    @Test
    void queriesLatestEventsAndCountsIncludingEmptyInput() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskLogEventRepository repository = new TaskLogEventRepository(database.dsl());
            assertThat(repository.latestEventIds(null)).isEmpty();
            assertThat(repository.latestEventIds(List.of())).isEmpty();

            database.enqueueRecord(event(9, 3, "tail"));
            assertThat(repository.listAfter(TestDataFixtures.TASK_ID, 8, 100))
                    .extracting(TaskLogEventView::content).containsExactly("tail");

            database.enqueueResult(database.result(new Field<?>[] {DSL.field("max", Long.class)},
                    new Object[] {9L}));
            assertThat(repository.latestEventId(TestDataFixtures.TASK_ID)).isEqualTo(9);

            database.enqueueResult(database.result(new Field<?>[] {DSL.field("max", Long.class)},
                    new Object[] {null}));
            assertThat(repository.latestEventId(TestDataFixtures.TASK_ID)).isZero();

            Field<Long> latest = DSL.field("latest_event_id", Long.class);
            database.enqueueResult(database.result(new Field<?>[] {
                    cn.rvport.backend.jooq.tables.TaskLogEvents.TASK_LOG_EVENTS.TASK_ID, latest
            }, new Object[] {TestDataFixtures.TASK_ID, 9L}));
            assertThat(repository.latestEventIds(List.of(TestDataFixtures.TASK_ID)))
                    .isEqualTo(Map.of(TestDataFixtures.TASK_ID, 9L));

            database.enqueueRecord(event(9, 3, "tail"));
            assertThat(repository.findByTaskIdAndId(TestDataFixtures.TASK_ID, 9)).isPresent();

            database.enqueueResult(database.result(new Field<?>[] {DSL.field("count", Integer.class)},
                    new Object[] {3}));
            assertThat(repository.count(TestDataFixtures.TASK_ID)).isEqualTo(3);
        }
    }

    @Test
    void usesMaxSequenceAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskLogEventRepository repository = new TaskLogEventRepository(database.dsl());
            database.enqueueResult(database.result(new Field<?>[] {DSL.field("max", Long.class)},
                    new Object[] {7L}));
            database.enqueueRecord(event(10, 8, "next"));
            assertThat(repository.append(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    TaskLogType.STDERR, List.of("next"))).extracting(TaskLogEventView::sequence).containsExactly(8L);

            database.enqueueFailure(new SQLException("event query failed"));
            assertThatThrownBy(() -> repository.count(TestDataFixtures.TASK_ID))
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("event query failed");
        }
    }

    private static TaskLogEventsRecord event(long id, long sequence, String content) {
        return new TaskLogEventsRecord(id, TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                TaskLogType.STDOUT.name(), sequence, content, TestDataFixtures.NOW);
    }
}
