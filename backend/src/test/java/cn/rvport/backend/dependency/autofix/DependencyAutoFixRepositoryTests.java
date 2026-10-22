package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Result;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class DependencyAutoFixRepositoryTests {

    private static final UUID PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID RUN_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID ANALYSIS_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID ENV_ID = UUID.fromString("60000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("70000000-0000-0000-0000-000000000001");
    private static final UUID RESULT_ID = UUID.fromString("80000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    private static final String RUN_TABLE = "dependency_auto_fix_runs";
    private static final Field<UUID> RUN_ID_F = field(RUN_TABLE, "id", UUID.class);
    private static final Field<UUID> RUN_PROJECT = field(RUN_TABLE, "project_id", UUID.class);
    private static final Field<UUID> RUN_TASK = field(RUN_TABLE, "task_id", UUID.class);
    private static final Field<UUID> RUN_ANALYSIS = field(RUN_TABLE, "dependency_analysis_run_id", UUID.class);
    private static final Field<UUID> RUN_REVISION = field(RUN_TABLE, "source_revision_id", UUID.class);
    private static final Field<UUID> RUN_ENV = field(RUN_TABLE, "target_environment_id", UUID.class);
    private static final Field<Long> RUN_VERSION = field(RUN_TABLE, "environment_config_version", Long.class);
    private static final Field<UUID> RUN_RERUN = field(RUN_TABLE, "rerun_dependency_analysis_run_id", UUID.class);
    private static final Field<UUID> RUN_RERUN_TASK = field(RUN_TABLE, "rerun_dependency_analysis_task_id", UUID.class);
    private static final Field<String> RUN_STATUS = field(RUN_TABLE, "status", String.class);
    private static final Field<Integer> RUN_SELECTED = field(RUN_TABLE, "selected_count", Integer.class);
    private static final Field<Integer> RUN_SUCCEEDED = field(RUN_TABLE, "succeeded_count", Integer.class);
    private static final Field<Integer> RUN_FAILED = field(RUN_TABLE, "failed_count", Integer.class);
    private static final Field<Integer> RUN_SKIPPED = field(RUN_TABLE, "skipped_count", Integer.class);
    private static final Field<JSONB> RUN_SUMMARY = field(RUN_TABLE, "summary", JSONB.class);
    private static final Field<String> RUN_ERROR = field(RUN_TABLE, "error_summary", String.class);
    private static final Field<OffsetDateTime> RUN_STARTED = field(RUN_TABLE, "started_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_FINISHED = field(RUN_TABLE, "finished_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_CREATED = field(RUN_TABLE, "created_at", OffsetDateTime.class);

    private static final String ITEM_TABLE = "dependency_auto_fix_items";
    private static final Field<UUID> ITEM_ID_F = field(ITEM_TABLE, "id", UUID.class);
    private static final Field<UUID> ITEM_RUN = field(ITEM_TABLE, "dependency_auto_fix_run_id", UUID.class);
    private static final Field<UUID> ITEM_RESULT = field(ITEM_TABLE, "dependency_result_item_id", UUID.class);
    private static final Field<UUID> ITEM_PROJECT = field(ITEM_TABLE, "project_id", UUID.class);
    private static final Field<UUID> ITEM_REVISION = field(ITEM_TABLE, "source_revision_id", UUID.class);
    private static final Field<String> ITEM_RISK = field(ITEM_TABLE, "risk_level", String.class);
    private static final Field<String> ITEM_TARGET = field(ITEM_TABLE, "target_match_status", String.class);
    private static final Field<String> ITEM_SOURCE_PACKAGE = field(ITEM_TABLE, "source_provider_package", String.class);
    private static final Field<String> ITEM_SOURCE_VERSION = field(ITEM_TABLE, "source_provider_version", String.class);
    private static final Field<String> ITEM_TARGET_PACKAGE = field(ITEM_TABLE, "target_provider_package", String.class);
    private static final Field<String> ITEM_TARGET_VERSION = field(ITEM_TABLE, "target_provider_version", String.class);
    private static final Field<String> ITEM_INSTALL_PACKAGE = field(ITEM_TABLE, "install_package_name", String.class);
    private static final Field<String> ITEM_INSTALL_VERSION = field(ITEM_TABLE, "install_version_constraint", String.class);
    private static final Field<Boolean> ITEM_DEFAULT = field(ITEM_TABLE, "default_selected", Boolean.class);
    private static final Field<String> ITEM_STATUS = field(ITEM_TABLE, "status", String.class);
    private static final Field<Integer> ITEM_EXIT = field(ITEM_TABLE, "exit_code", Integer.class);
    private static final Field<String> ITEM_ERROR = field(ITEM_TABLE, "error_summary", String.class);
    private static final Field<JSONB> ITEM_EVIDENCE = field(ITEM_TABLE, "evidence", JSONB.class);
    private static final Field<OffsetDateTime> ITEM_STARTED = field(ITEM_TABLE, "started_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> ITEM_FINISHED = field(ITEM_TABLE, "finished_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> ITEM_CREATED = field(ITEM_TABLE, "created_at", OffsetDateTime.class);

    @Test
    void createsFindsAndMapsRunWithNullCountersAndBadJson() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            database.enqueueResult(runResult(database, DependencyAutoFixRunStatus.PENDING, null, null, null, null, JSONB.valueOf("bad")))
                    .enqueueResult(runResult(database, DependencyAutoFixRunStatus.RUNNING, 2, 1, 0, 1, JSONB.valueOf("{\"ok\":true}")));
            DependencyAutoFixRunView created = repository.createRun(RUN_ID, PROJECT_ID, TASK_ID, ANALYSIS_ID, REVISION_ID, ENV_ID, 4, 2);
            assertThat(created.selectedCount()).isZero();
            assertThat(created.summary()).isEmpty();
            assertThat(repository.findRun(RUN_ID).orElseThrow().summary()).containsEntry("ok", true);
            database.verifyComplete();
        }
    }

    @Test
    void createsCandidateItemsAndNormalizesOptionalValues() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            database.enqueueRows(1).enqueueRows(1);
            repository.createItems(RUN_ID, List.of(candidate(" gcc ", " 12 ", "repo"), candidate("glibc", "", "fallback")), PROJECT_ID, REVISION_ID);
            assertThat(database.executions()).hasSize(2);
            assertThat(database.executions().getFirst().bindings()).contains("gcc", "12", DependencyAutoFixItemStatus.PENDING.name())
                    .anySatisfy(value -> {
                        if (value instanceof JSONB jsonb) assertThat(jsonb.data()).contains("\"candidateReason\":\"repo\"");
                    });
            assertThat(database.executions().get(1).bindings()).containsNull();
            database.verifyComplete();
        }
    }

    @Test
    void filtersCountsAndSortsRunsAndItems() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            DependencyAutoFixRunListRequest runs = new DependencyAutoFixRunListRequest(2, 5, REVISION_ID, 4L, false,
                    DependencyAutoFixRunStatus.SUCCEEDED, "status", "asc");
            DependencyAutoFixItemListRequest items = new DependencyAutoFixItemListRequest(2, 5,
                    DependencyAutoFixItemStatus.FAILED, DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE,
                    " gcc ", " timeout ", "riskLevel", "desc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(runResult(database, DependencyAutoFixRunStatus.SUCCEEDED, 2, 1, 1, 0, null))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(itemResult(database, DependencyAutoFixItemStatus.FAILED, JSONB.valueOf("{\"attempt\":1}")));
            assertThat(repository.countRuns(PROJECT_ID, runs)).isEqualTo(1);
            assertThat(repository.listRuns(PROJECT_ID, runs)).hasSize(1);
            assertThat(repository.countItems(RUN_ID, items)).isEqualTo(1);
            assertThat(repository.listItems(RUN_ID, items).getFirst().evidence()).containsEntry("attempt", 1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("source_revision_id =", "environment_config_version =", "status =");
            assertThat(database.executions().get(2).normalizedSql()).contains("install_package_name =", "lower", "risk_level =");
            database.verifyComplete();
        }
    }

    @Test
    void coversAllRunAndItemSortSelectionsAndPendingItems() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            for (int index = 0; index < 4; index++) database.enqueueResult(database.result(runFields()));
            for (String sort : new String[]{"startedAt", "finishedAt", "status", "unknown"}) repository.listRuns(PROJECT_ID,
                    new DependencyAutoFixRunListRequest(null, null, null, null, true, null, sort, "desc"));
            for (int index = 0; index < 6; index++) database.enqueueResult(database.result(itemFields()));
            for (String sort : new String[]{"status", "targetMatchStatus", "installPackageName", "finishedAt", "", "unknown"}) repository.listItems(RUN_ID,
                    new DependencyAutoFixItemListRequest(null, null, null, null, null, null, null, sort, "asc"));
            database.enqueueResult(itemResult(database, DependencyAutoFixItemStatus.PENDING, null));
            assertThat(repository.listPendingItems(RUN_ID)).hasSize(1);
            assertThat(database.executions().get(0).normalizedSql()).contains("started_at desc");
            assertThat(database.executions().get(3).normalizedSql()).contains("created_at desc");
            assertThat(database.executions().get(4).normalizedSql()).contains("status asc");
            assertThat(database.executions().get(9).normalizedSql()).contains("created_at asc");
            database.verifyComplete();
        }
    }

    @Test
    void calculatesSummaryCountsIncludingSkippedVariants() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            for (int value : new int[]{5, 2, 1, 1, 1}) {
                database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{value}));
            }
            assertThat(repository.summaryCounts(RUN_ID)).containsEntry("total", 5).containsEntry("succeeded", 2)
                    .containsEntry("alreadySatisfied", 1).containsEntry("skippedUnavailable", 1).containsEntry("failed", 1);
            database.verifyComplete();
        }
    }

    @Test
    void updatesLifecycleCountsLinksRerunAndCancelsPendingItems() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAutoFixRepository repository = repository(database);
            database.enqueueRows(1).enqueueRows(1).enqueueRows(1);
            repository.markRunRunning(RUN_ID);
            repository.markItemRunning(ITEM_ID);
            repository.markItemFinished(ITEM_ID, DependencyAutoFixItemStatus.FAILED, 2, " error ", Map.of("stderr", "failed"));
            enqueueCounts(database, 2, 1, 1).enqueueRows(1);
            repository.markRunFinished(RUN_ID, DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED, Map.of("done", true), " partial ");
            enqueueCounts(database, 2, 1, 1).enqueueRows(1).enqueueRows(1);
            repository.linkRerun(RUN_ID, ANALYSIS_ID, TASK_ID, null, DependencyAutoFixRunStatus.SUCCEEDED);
            repository.cancelPendingItems(RUN_ID);
            assertThat(database.executions().get(2).bindings()).contains("error");
            assertThat(database.executions().get(6).bindings()).contains(2, 1, DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED.name());
            assertThat(database.lastExecution().normalizedSql()).contains("status in");
            database.verifyComplete();
        }
    }

    @Test
    void fallsBackOnJsonSerializationAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            DependencyAutoFixRepository repository = new DependencyAutoFixRepository(database.dsl(), mapper);
            database.enqueueRows(1);
            repository.markItemFinished(ITEM_ID, DependencyAutoFixItemStatus.SUCCEEDED, 0, "", Map.of("ok", true));
            assertThat(database.lastExecution().bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findRun(RUN_ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static DependencyAutoFixCandidateResponse candidate(String packageName, String version, String reason) {
        return new DependencyAutoFixCandidateResponse(RESULT_ID, DependencyType.BUILD_PACKAGE, "gcc", "12",
                DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.REPO_AVAILABLE, " gcc ", " 12.2 ",
                " gcc ", " 13.1 ", packageName, version, true, true, reason);
    }

    private static DependencyAutoFixRepository repository(JooqMockDatabase database) {
        return new DependencyAutoFixRepository(database.dsl(), new ObjectMapper());
    }

    private static JooqMockDatabase enqueueCounts(JooqMockDatabase database, int succeeded, int failed, int skipped) {
        return database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{succeeded}))
                .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{failed}))
                .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{skipped}));
    }

    private static Result<org.jooq.Record> runResult(JooqMockDatabase database, DependencyAutoFixRunStatus status,
                                                     Integer selected, Integer succeeded, Integer failed, Integer skipped, JSONB summary) {
        return database.result(runFields(), new Object[]{RUN_ID, PROJECT_ID, TASK_ID, ANALYSIS_ID, REVISION_ID, ENV_ID, 4L,
                null, null, status.name(), selected, succeeded, failed, skipped, summary, null, NOW, NOW, NOW});
    }

    private static Field<?>[] runFields() {
        return new Field<?>[]{RUN_ID_F, RUN_PROJECT, RUN_TASK, RUN_ANALYSIS, RUN_REVISION, RUN_ENV, RUN_VERSION, RUN_RERUN,
                RUN_RERUN_TASK, RUN_STATUS, RUN_SELECTED, RUN_SUCCEEDED, RUN_FAILED, RUN_SKIPPED, RUN_SUMMARY, RUN_ERROR,
                RUN_STARTED, RUN_FINISHED, RUN_CREATED};
    }

    private static Result<org.jooq.Record> itemResult(JooqMockDatabase database, DependencyAutoFixItemStatus status, JSONB evidence) {
        return database.result(itemFields(), new Object[]{ITEM_ID, RUN_ID, RESULT_ID, PROJECT_ID, REVISION_ID,
                DependencyRiskLevel.HIGH.name(), DependencyTargetMatchStatus.REPO_AVAILABLE.name(), "gcc", "12.2", "gcc",
                "13.1", "gcc", "12", true, status.name(), 0, null, evidence, NOW, NOW, NOW});
    }

    private static Field<?>[] itemFields() {
        return new Field<?>[]{ITEM_ID_F, ITEM_RUN, ITEM_RESULT, ITEM_PROJECT, ITEM_REVISION, ITEM_RISK, ITEM_TARGET,
                ITEM_SOURCE_PACKAGE, ITEM_SOURCE_VERSION, ITEM_TARGET_PACKAGE, ITEM_TARGET_VERSION, ITEM_INSTALL_PACKAGE,
                ITEM_INSTALL_VERSION, ITEM_DEFAULT, ITEM_STATUS, ITEM_EXIT, ITEM_ERROR, ITEM_EVIDENCE, ITEM_STARTED,
                ITEM_FINISHED, ITEM_CREATED};
    }

    private static <T> Field<T> field(String table, String name, Class<T> type) {
        return DSL.field(DSL.name(table, name), type);
    }
}
