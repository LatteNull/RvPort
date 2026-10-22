package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import org.jooq.Field;
import org.jooq.Result;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class WorkerInstanceRepositoryTests {
    @Test
    void locksRegisteredWorkerBeforeClaim() throws Exception {
        try (var database = new JooqMockDatabase()) {
            var repository = new WorkerInstanceRepository(database.dsl());
            Field<?>[] fields = {DSL.field("instance_id", String.class)};
            database.enqueueResult(database.result(fields, new Object[]{"worker"}));
            assertThat(repository.lockForClaim("worker")).isTrue();
            assertThat(database.lastExecution().normalizedSql()).contains("for update");
            database.enqueueResult(database.result(fields));
            assertThat(repository.lockForClaim("missing")).isFalse();
        }
    }
    private static final OffsetDateTime RECENT = OffsetDateTime.now().plusMinutes(1);
    private static final OffsetDateTime STALE = OffsetDateTime.now().minusHours(1);

    @Test
    void upsertsHeartbeatAndMapsReturnedWorker() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            database.enqueueResult(workerResult(database, RECENT, 4, 2, 2));
            WorkerInstanceView view = repository.upsertHeartbeat("worker-1", "host", 42, "v1", 4, 2, 2);
            assertThat(view).isNull();
            assertThat(database.lastExecution().normalizedSql()).contains("on conflict", "do update", "last_heartbeat_at");
            database.verifyComplete();
        }
    }

    @Test
    void listsOnlineWorkersWithFiltersPaginationAndNullCounterDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            WorkerInstanceListRequest request = new WorkerInstanceListRequest(2, 5, WorkerInstanceStatus.ONLINE,
                    " worker ", " host ", true, "activeTaskCount", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(workerResult(database, RECENT, null, null, null));
            var page = repository.list(request, 60);
            assertThat(page.total()).isEqualTo(1);
            assertThat(page.items().getFirst().activeTaskCount()).isZero();
            assertThat(database.executions().getFirst().normalizedSql()).contains("last_heartbeat_at >=", "lower", "active_task_count >");
            assertThat(database.executions().get(1).normalizedSql()).contains("active_task_count asc nulls last", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void listsOfflineIdleWorkersAndSupportsAllSorts() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            String[] sorts = {"instanceId", "hostname", "status", "concurrencyLimit", "activeConcurrency", "startedAt", "updatedAt", ""};
            for (String ignored : sorts) {
                database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{0L}))
                        .enqueueResult(database.result(workerFields()));
            }
            for (String sort : sorts) repository.list(new WorkerInstanceListRequest(null, null, WorkerInstanceStatus.OFFLINE,
                    null, null, false, sort, "desc"), 60);
            assertThat(database.executions().get(0).normalizedSql()).contains("last_heartbeat_at <", "active_task_count =");
            assertThat(database.executions().get(1).normalizedSql()).contains("instance_id desc nulls last");
            assertThat(database.executions().get(15).normalizedSql()).contains("last_heartbeat_at desc nulls last");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{0L}));
            assertThatThrownBy(() -> repository.list(new WorkerInstanceListRequest(1, 20, null, null, null, null,
                    "pid", "asc"), 60)).isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Unsupported worker sort field");
            database.verifyComplete();
        }
    }

    @Test
    void findsUpdatesConcurrencyAndHandlesMissingWorker() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            Field<Integer> limit = field("concurrency_limit", Integer.class);
            database.enqueueResult(workerResult(database, STALE, 2, 0, 0))
                    .enqueueResult(database.result(new Field<?>[]{limit}, new Object[]{2}))
                    .enqueueRows(1).enqueueResult(workerResult(database, RECENT, 8, 0, 0))
                    .enqueueRows(0).enqueueResult(database.result(workerFields()));
            assertThat(repository.findByInstanceId("worker-1", 60).orElseThrow().status()).isEqualTo(WorkerInstanceStatus.OFFLINE);
            assertThat(repository.findConcurrencyLimit("worker-1")).contains(2);
            assertThat(repository.updateConcurrencyLimit("worker-1", 8, 60).concurrencyLimit()).isEqualTo(8);
            assertThat(repository.updateConcurrencyLimit("missing", 8, 60)).isNull();
            database.verifyComplete();
        }
    }

    @Test
    void marksStaleWorkersOfflineAndShortCircuitsEmptySelection() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            Field<String> instanceId = field("instance_id", String.class);
            database.enqueueResult(database.result(new Field<?>[]{instanceId}));
            assertThat(repository.markOfflineBefore(STALE, 10)).isZero();
            assertThat(database.executions()).hasSize(1);
            database.enqueueResult(database.result(new Field<?>[]{instanceId}, new Object[]{"worker-1"}, new Object[]{"worker-2"}))
                    .enqueueRows(2);
            assertThat(repository.markOfflineBefore(STALE, 10)).isEqualTo(2);
            assertThat(database.lastExecution().normalizedSql()).contains("instance_id in", "last_heartbeat_at <");
            database.verifyComplete();
        }
    }

    @Test
    void findsLocksAndDeletesOnlyRetiredWorkers() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            Field<String> instanceId = field("instance_id", String.class);
            database.enqueueResult(database.result(new Field<?>[]{instanceId}, new Object[]{"worker-1"}))
                    .enqueueResult(database.result(new Field<?>[]{instanceId}, new Object[]{"worker-1"}))
                    .enqueueResult(database.result(new Field<?>[]{instanceId}))
                    .enqueueRows(1);
            assertThat(repository.findInstanceIdsBefore(STALE, 10)).containsExactly("worker-1");
            assertThat(repository.lockIfStillStale("worker-1", STALE)).isTrue();
            assertThat(repository.lockIfStillStale("worker-2", STALE)).isFalse();
            assertThat(repository.deleteIfRetired("worker-1", STALE)).isEqualTo(1);
            assertThat(database.executions().get(1).normalizedSql()).contains("for update skip locked");
            assertThat(database.lastExecution().normalizedSql()).contains("not exists", "task_runtime_handles");
            database.verifyComplete();
        }
    }

    @Test
    void mapsNullHeartbeatOfflineAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            WorkerInstanceRepository repository = new WorkerInstanceRepository(database.dsl());
            database.enqueueResult(workerResult(database, null, 1, 0, 0));
            assertThat(repository.findByInstanceId("worker-1", 60).orElseThrow().status()).isEqualTo(WorkerInstanceStatus.OFFLINE);
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findConcurrencyLimit("worker-1"))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class).hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static Result<org.jooq.Record> workerResult(JooqMockDatabase database, OffsetDateTime heartbeat,
                                                         Integer limit, Integer active, Integer taskCount) {
        return database.result(workerFields(), new Object[]{"worker-1", "host", 42L, "v1", WorkerInstanceStatus.ONLINE.name(),
                limit, active, taskCount, STALE, heartbeat, STALE, RECENT});
    }

    private static Field<?>[] workerFields() {
        return new Field<?>[]{field("instance_id", String.class), field("hostname", String.class), field("process_id", Long.class),
                field("app_version", String.class), field("status", String.class), field("concurrency_limit", Integer.class),
                field("active_concurrency", Integer.class), field("active_task_count", Integer.class),
                field("started_at", OffsetDateTime.class), field("last_heartbeat_at", OffsetDateTime.class),
                field("created_at", OffsetDateTime.class), field("updated_at", OffsetDateTime.class)};
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }
}
