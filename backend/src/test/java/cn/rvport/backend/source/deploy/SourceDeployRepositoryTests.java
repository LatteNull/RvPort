package cn.rvport.backend.source.deploy;

import static cn.rvport.backend.jooq.tables.SourceDeployRuns.SOURCE_DEPLOY_RUNS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.SourceDeployRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class SourceDeployRepositoryTests {

    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID ENVIRONMENT_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsPendingRunsWithExplicitAndLegacyConfigVersions() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), new ObjectMapper());
            database.enqueueRecord(record(4L, TaskStatus.PENDING)).enqueueRecord(record(0L, TaskStatus.PENDING));

            SourceDeployRunView explicit = repository.createPending(
                    ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID, 4L, "/remote", true);
            SourceDeployRunView legacy = repository.createPending(
                    ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID, "/remote", false);

            assertThat(explicit.environmentConfigVersion()).isEqualTo(4L);
            assertThat(explicit.deployStrategy()).isEqualTo(SourceDeployStrategy.TAR_OVER_SSH);
            assertThat(legacy.environmentConfigVersion()).isZero();
            assertThat(database.executions().get(1).bindings()).contains(0L, false);
            database.verifyComplete();
        }
    }

    @Test
    void findsReusableAndLatestSucceededIncludingMissingRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), new ObjectMapper());
            database.enqueueRecord(record(3L, TaskStatus.RUNNING)).enqueueRecord(record(0L, TaskStatus.SUCCEEDED))
                    .enqueueRecord(record(3L, TaskStatus.SUCCEEDED)).enqueueResult(database.result(SOURCE_DEPLOY_RUNS.fields()));

            assertThat(repository.findReusable(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, 3L)).isPresent();
            assertThat(repository.findReusable(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID)).isPresent();
            assertThat(repository.findLatestSucceeded(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, 3L)).isPresent();
            assertThat(repository.findById(UUID.randomUUID())).isEmpty();
            assertThat(database.executions().getFirst().normalizedSql()).contains("status in", "environment_config_version = ?");
            assertThat(database.executions().get(2).normalizedSql()).contains("status = ?", "finished_at desc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void countsAndListsUsingEveryFilterAndSortDirection() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), new ObjectMapper());
            SourceDeployListRequest request = new SourceDeployListRequest(
                    2, 5, REVISION_ID, ENVIRONMENT_ID, TaskStatus.SUCCEEDED, NOW.minusHours(1), NOW.plusHours(1),
                    "status", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(record(3L, TaskStatus.SUCCEEDED));

            assertThat(repository.count(PROJECT_ID, request)).isEqualTo(1L);
            assertThat(repository.list(PROJECT_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql())
                    .contains("source_revision_id =", "environment_id =", "created_at >=", "created_at <=");
            assertThat(database.executions().get(1).normalizedSql()).contains("status asc", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void supportsAllSortFieldsDefaultsAndPagingDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), new ObjectMapper());
            String[] sorts = {"startedAt", "finishedAt", "unknown", " "};
            for (String sort : sorts) database.enqueueResult(database.result(SOURCE_DEPLOY_RUNS.fields()));

            for (String sort : sorts) {
                assertThat(repository.list(PROJECT_ID, new SourceDeployListRequest(
                        null, null, null, null, null, null, null, sort, "desc"))).isEmpty();
            }
            assertThat(database.executions().get(0).normalizedSql()).contains("started_at desc");
            assertThat(database.executions().get(1).normalizedSql()).contains("finished_at desc");
            assertThat(database.executions().get(2).normalizedSql()).contains("created_at desc");
            assertThat(database.executions().get(3).normalizedSql()).contains("fetch next ? rows only");
            database.verifyComplete();
        }
    }

    @Test
    void updatesLifecycleAndFallsBackToEmptySummaryOnSerializationFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), mapper);
            database.enqueueRows(1).enqueueRows(1).enqueueRows(1);

            repository.markRunning(ID);
            repository.markFinished(ID, TaskStatus.SUCCEEDED, 10, 2048L, 0, Map.of("copied", true));
            repository.syncStatusByTask(TASK_ID, TaskStatus.FAILED);

            assertThat(database.executions().getFirst().normalizedSql()).contains("started_at");
            assertThat(database.executions().get(1).bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            assertThat(database.executions().get(2).normalizedSql()).contains("task_id =", "finished_at");
            database.verifyComplete();
        }
    }

    @Test
    void propagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SourceDeployRepository repository = new SourceDeployRepository(database.dsl(), new ObjectMapper());
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static SourceDeployRunsRecord record(Long configVersion, TaskStatus status) {
        return new SourceDeployRunsRecord(
                ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID, "/remote", SourceDeployStrategy.TAR_OVER_SSH.name(),
                true, status.name(), 10, 2048L, 0, JSONB.valueOf("{}"), NOW, NOW, NOW, configVersion);
    }
}
