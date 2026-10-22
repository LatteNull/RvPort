package cn.rvport.backend.buildvalidation;

import static cn.rvport.backend.jooq.tables.BuildRuns.BUILD_RUNS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.BuildRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Result;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class BuildValidationRepositoryTests {

    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID ENVIRONMENT_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsPendingRunsWithScopeAndLegacyDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            BuildRunsRecord legacyRecord = record(BuildValidationScope.BOTH.name(), JSONB.valueOf("{}"));
            legacyRecord.setEnvironmentConfigVersion(0L);
            database.enqueueRecord(record(BuildValidationScope.SOURCE_ONLY.name(), JSONB.valueOf("{}")))
                    .enqueueRecord(record(BuildValidationScope.BOTH.name(), JSONB.valueOf("{}")))
                    .enqueueRecord(legacyRecord);

            BuildValidationRunView scoped = repository.createPending(
                    ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID, BuildValidationScope.SOURCE_ONLY,
                    UUID.randomUUID(), 4L, UUID.randomUUID(), "hash", "make", "/work", 300, Map.of("TOKEN", "***"));
            BuildValidationRunView defaultScope = repository.createPending(
                    ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID, null,
                    null, 4L, null, "hash", "make", "/work", null, Map.of());
            BuildValidationRunView legacy = repository.createPending(
                    ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID,
                    null, null, "hash", "make", "/work", null, Map.of());

            assertThat(scoped.buildScope()).isEqualTo(BuildValidationScope.SOURCE_ONLY);
            assertThat(defaultScope.buildScope()).isEqualTo(BuildValidationScope.BOTH);
            assertThat(legacy.environmentConfigVersion()).isZero();
            assertThat(database.executions().get(2).bindings()).contains(0L);
            database.verifyComplete();
        }
    }

    @Test
    void mapsTaskEnvironmentVariablesScopeAndBuildFacts() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            BuildRunsRecord record = record(BuildValidationScope.SOURCE_ONLY.name(), JSONB.valueOf("{\"compiler\":\"gcc\"}"));
            JSONB input = JSONB.valueOf("{\"environmentVariablesMasked\":{\"TOKEN\":\"***\"}}");
            database.enqueueResult(joined(database, record, input)).enqueueResult(joined(database, record, input));

            BuildValidationRunView byId = repository.findById(ID).orElseThrow();
            BuildValidationRunView byTask = repository.findByTaskId(TASK_ID).orElseThrow();
            assertThat(byId.environmentVariables()).containsEntry("TOKEN", "***");
            assertThat(byId.buildFacts()).containsEntry("compiler", "gcc");
            assertThat(byId.buildScope()).isEqualTo(BuildValidationScope.SOURCE_ONLY);
            assertThat(byTask.id()).isEqualTo(ID);
            database.verifyComplete();
        }
    }

    @Test
    void fallsBackForBlankInvalidScopeAndMalformedJson() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(joined(database, record("INVALID", JSONB.valueOf("bad")), JSONB.valueOf("bad")))
                    .enqueueResult(joined(database, record(" ", null), null));

            BuildValidationRunView invalid = repository.findById(ID).orElseThrow();
            BuildValidationRunView blank = repository.findByTaskId(TASK_ID).orElseThrow();
            assertThat(invalid.buildScope()).isEqualTo(BuildValidationScope.BOTH);
            assertThat(invalid.environmentVariables()).isEmpty();
            assertThat(invalid.buildFacts()).isEmpty();
            assertThat(blank.buildScope()).isEqualTo(BuildValidationScope.BOTH);
            database.verifyComplete();
        }
    }

    @Test
    void appliesLatestLookupOptionalFiltersAndCompileDatabasePredicate() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            BuildRunsRecord record = record(BuildValidationScope.BOTH.name(), JSONB.valueOf("{}"));
            database.enqueueResult(joined(database, record, null)).enqueueResult(joined(database, record, null))
                    .enqueueResult(joined(database, record, null)).enqueueResult(joined(database, record, null));

            assertThat(repository.findLatestSucceededSourceBuild(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, 4L)).isPresent();
            assertThat(repository.findLatestSucceededSourceBuild(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, null)).isPresent();
            assertThat(repository.findLatest(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, 4L, BuildValidationScope.BOTH)).isPresent();
            assertThat(repository.findLatestSucceededSourceBuildWithCompileDatabase(PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, 4L)).isPresent();
            assertThat(database.executions().get(0).normalizedSql()).contains("environment_config_version = ?");
            assertThat(database.executions().get(1).normalizedSql()).doesNotContain("environment_config_version = ?");
            assertThat(database.executions().get(2).normalizedSql()).contains("build_scope = ?", "case when build_runs.status in");
            assertThat(database.executions().get(3).normalizedSql()).contains("compileDatabase", "case when build_scope = ?");
            assertThat(database.executions().get(3).bindings()).contains(BuildValidationScope.SOURCE_ONLY.name());
            database.verifyComplete();
        }
    }

    @Test
    void filtersListsSortsAndUsesPagingDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            BuildValidationListRequest filtered = new BuildValidationListRequest(
                    2, 5, REVISION_ID, ENVIRONMENT_ID, 4L, true, false, BuildValidationScope.SOURCE_ONLY,
                    TaskStatus.SUCCEEDED, NOW.minusHours(1), NOW.plusHours(1), "environmentId", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(joined(database, record(BuildValidationScope.SOURCE_ONLY.name(), JSONB.valueOf("{}")), null));

            assertThat(repository.count(PROJECT_ID, filtered)).isEqualTo(1L);
            assertThat(repository.list(PROJECT_ID, filtered)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql())
                    .contains("source_revision_id =", "environment_id =", "build_scope =", "created_at >=", "created_at <=");
            assertThat(database.executions().get(1).normalizedSql()).contains("environment_id asc", "offset ? rows");
            database.verifyComplete();
        }

        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            String[] sorts = {"startedAt", "finishedAt", "status", "unknown", " "};
            for (String ignored : sorts) database.enqueueResult(database.result(fieldsWithInputSnapshot()));
            for (String sort : sorts) {
                assertThat(repository.list(PROJECT_ID, new BuildValidationListRequest(
                        null, null, null, null, null, null, null, null, null, null, null, sort, "desc"))).isEmpty();
            }
            assertThat(database.executions().get(0).normalizedSql()).contains("started_at desc");
            assertThat(database.executions().get(1).normalizedSql()).contains("finished_at desc");
            assertThat(database.executions().get(2).normalizedSql()).contains("status desc");
            assertThat(database.executions().get(3).normalizedSql()).contains("created_at desc");
            database.verifyComplete();
        }
    }

    @Test
    void updatesLifecycleFactsDeploymentAndTaskStatusWithSerializationFallback() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), mapper);
            for (int i = 0; i < 5; i++) database.enqueueRows(1);

            repository.markRunning(ID);
            repository.markFinished(ID, TaskStatus.FAILED, 2, "COMPILE", UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID());
            repository.updateBuildFacts(ID, Map.of("compiler", "gcc"));
            repository.updateSourceDeployment(ID, UUID.randomUUID(), "/remote");
            repository.syncStatusByTask(TASK_ID, TaskStatus.CANCELLED);

            assertThat(database.executions().get(0).normalizedSql()).contains("started_at");
            assertThat(database.executions().get(1).normalizedSql()).contains("combined_log_id", "stderr_log_id");
            assertThat(database.executions().get(2).bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            assertThat(database.executions().get(4).normalizedSql()).contains("task_id =", "finished_at");
            database.verifyComplete();
        }
    }

    @Test
    void returnsEmptyRowsAndPropagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(database.result(fieldsWithInputSnapshot())).enqueueFailure(new SQLException("database unavailable"));
            assertThat(repository.findById(ID)).isEmpty();
            assertThatThrownBy(() -> repository.findByTaskId(TASK_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    @Test
    void handlesAbsentLatestFiltersNullScopeAndEmptyJsonShapes() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            BuildValidationRepository repository = new BuildValidationRepository(database.dsl(), new ObjectMapper());
            BuildRunsRecord nullScope = record(null, JSONB.valueOf(" "));
            BuildRunsRecord blankInput = record(BuildValidationScope.BOTH.name(), JSONB.valueOf("{}"));
            database.enqueueResult(joined(database, nullScope, null))
                    .enqueueResult(joined(database, nullScope, null))
                    .enqueueResult(joined(database, nullScope, JSONB.valueOf("{}")))
                    .enqueueResult(joined(database, blankInput, JSONB.valueOf(" ")))
                    .enqueueRecord(record(BuildValidationScope.BOTH.name(), JSONB.valueOf("{}")));

            assertThat(repository.findLatest(PROJECT_ID, null, null, null, null)).isPresent();
            assertThat(database.executions().getFirst().normalizedSql()).doesNotContain(
                    "source_revision_id =", "environment_id =", "environment_config_version =", "build_scope =");
            assertThat(repository.findLatestSucceededSourceBuildWithCompileDatabase(
                    PROJECT_ID, REVISION_ID, ENVIRONMENT_ID, null)).isPresent();
            assertThat(database.executions().get(1).normalizedSql()).doesNotContain("environment_config_version =");

            BuildValidationRunView missingEnvironmentVariables = repository.findById(ID).orElseThrow();
            assertThat(missingEnvironmentVariables.buildScope()).isEqualTo(BuildValidationScope.BOTH);
            assertThat(missingEnvironmentVariables.environmentVariables()).isEmpty();
            assertThat(missingEnvironmentVariables.buildFacts()).isEmpty();
            assertThat(repository.findByTaskId(TASK_ID).orElseThrow().environmentVariables()).isEmpty();

            repository.createPending(ID, PROJECT_ID, TASK_ID, REVISION_ID, ENVIRONMENT_ID,
                    BuildValidationScope.BOTH, null, 4L, null, "hash", "make", "/work", 300, null);
            assertThat(database.lastExecution().bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).contains("environmentVariablesMasked");
            });
            database.enqueueRows(1);
            repository.updateBuildFacts(ID, null);
            assertThat(database.lastExecution().bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            database.verifyComplete();
        }
    }

    private static BuildRunsRecord record(String scope, JSONB facts) {
        BuildRunsRecord record = new BuildRunsRecord();
        record.setId(ID);
        record.setProjectId(PROJECT_ID);
        record.setTaskId(TASK_ID);
        record.setSourceRevisionId(REVISION_ID);
        record.setEnvironmentId(ENVIRONMENT_ID);
        record.setBuildScope(scope);
        record.setBuildFacts(facts);
        record.setEnvironmentConfigVersion(4L);
        record.setCommand("make");
        record.setWorkingDirectory("/work");
        record.setTimeoutSeconds(300);
        record.setStatus(TaskStatus.SUCCEEDED.name());
        record.setCreatedAt(NOW);
        return record;
    }

    private static Result<?> joined(JooqMockDatabase database, BuildRunsRecord record, JSONB inputSnapshot) {
        Field<?>[] fields = fieldsWithInputSnapshot();
        Object[] values = new Object[fields.length];
        for (int index = 0; index < BUILD_RUNS.fields().length; index++) {
            values[index] = record.get(BUILD_RUNS.fields()[index]);
        }
        values[values.length - 1] = inputSnapshot;
        return database.result(fields, values);
    }

    private static Field<?>[] fieldsWithInputSnapshot() {
        Field<?>[] fields = Arrays.copyOf(BUILD_RUNS.fields(), BUILD_RUNS.fields().length + 1);
        fields[fields.length - 1] = TASKS.INPUT_SNAPSHOT;
        return fields;
    }
}
