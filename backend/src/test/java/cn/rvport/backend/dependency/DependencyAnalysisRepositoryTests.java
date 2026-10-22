package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.task.TaskStatus;
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

class DependencyAnalysisRepositoryTests {

    private static final UUID PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID RUN_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID BUILD_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID ENV_ID = UUID.fromString("60000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("70000000-0000-0000-0000-000000000001");
    private static final UUID SNAPSHOT_ID = UUID.fromString("80000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    private static final Field<UUID> RUN_ID_F = field("dependency_analysis_runs", "id", UUID.class);
    private static final Field<UUID> RUN_PROJECT = field("dependency_analysis_runs", "project_id", UUID.class);
    private static final Field<UUID> RUN_TASK = field("dependency_analysis_runs", "task_id", UUID.class);
    private static final Field<UUID> RUN_REVISION = field("dependency_analysis_runs", "source_revision_id", UUID.class);
    private static final Field<UUID> RUN_BUILD = field("dependency_analysis_runs", "source_build_run_id", UUID.class);
    private static final Field<UUID> RUN_ENV = field("dependency_analysis_runs", "target_environment_id", UUID.class);
    private static final Field<Long> RUN_VERSION = field("dependency_analysis_runs", "environment_config_version", Long.class);
    private static final Field<String> RUN_STATUS = field("dependency_analysis_runs", "status", String.class);
    private static final Field<JSONB> RUN_SUMMARY = field("dependency_analysis_runs", "summary", JSONB.class);
    private static final Field<JSONB> RUN_WARNINGS = field("dependency_analysis_runs", "warnings", JSONB.class);
    private static final Field<OffsetDateTime> RUN_STARTED = field("dependency_analysis_runs", "started_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_FINISHED = field("dependency_analysis_runs", "finished_at", OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_CREATED = field("dependency_analysis_runs", "created_at", OffsetDateTime.class);

    private static final String ITEM_TABLE = "dependency_analysis_result_items";
    private static final Field<UUID> ITEM_ID_F = field(ITEM_TABLE, "id", UUID.class);
    private static final Field<UUID> ITEM_PROJECT = field(ITEM_TABLE, "project_id", UUID.class);
    private static final Field<UUID> ITEM_REVISION = field(ITEM_TABLE, "source_revision_id", UUID.class);
    private static final Field<UUID> ITEM_TASK = field(ITEM_TABLE, "task_id", UUID.class);
    private static final Field<UUID> ITEM_RUN = field(ITEM_TABLE, "dependency_analysis_run_id", UUID.class);
    private static final Field<String> ITEM_TYPE = field(ITEM_TABLE, "dependency_type", String.class);
    private static final Field<String> ITEM_NAME = field(ITEM_TABLE, "dependency_name", String.class);
    private static final Field<String> ITEM_VERSION = field(ITEM_TABLE, "dependency_version", String.class);
    private static final Field<String> ITEM_SOURCE_PACKAGE = field(ITEM_TABLE, "source_provider_package", String.class);
    private static final Field<String> ITEM_SOURCE_PACKAGE_VERSION = field(ITEM_TABLE, "source_provider_version", String.class);
    private static final Field<String> ITEM_SOURCE_DETECTED_VERSION = field(ITEM_TABLE, "source_detected_version", String.class);
    private static final Field<String> ITEM_TARGET_PACKAGE = field(ITEM_TABLE, "target_provider_package", String.class);
    private static final Field<String> ITEM_TARGET_PACKAGE_VERSION = field(ITEM_TABLE, "target_provider_version", String.class);
    private static final Field<String> ITEM_TARGET_DETECTED_VERSION = field(ITEM_TABLE, "target_detected_version", String.class);
    private static final Field<String> ITEM_PROVIDER_STATUS = field(ITEM_TABLE, "provider_version_status", String.class);
    private static final Field<String> ITEM_VERSION_CONFIDENCE = field(ITEM_TABLE, "version_evidence_confidence", String.class);
    private static final Field<String> ITEM_TARGET_STATUS = field(ITEM_TABLE, "target_match_status", String.class);
    private static final Field<String> ITEM_RISK = field(ITEM_TABLE, "risk_level", String.class);
    private static final Field<String> ITEM_LOCATION = field(ITEM_TABLE, "location_label", String.class);
    private static final Field<String> ITEM_RECOMMENDATION = field(ITEM_TABLE, "recommendation", String.class);
    private static final Field<String> ITEM_CONFIDENCE = field(ITEM_TABLE, "confidence", String.class);
    private static final Field<JSONB> ITEM_EVIDENCE = field(ITEM_TABLE, "evidence", JSONB.class);
    private static final Field<OffsetDateTime> ITEM_CREATED = field(ITEM_TABLE, "created_at", OffsetDateTime.class);

    @Test
    void createsFindsAndSelectsLatestRuns() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            database.enqueueResult(runResult(database, TaskStatus.PENDING, JSONB.valueOf("{\"count\":1}"), JSONB.valueOf("{\"items\":[\"w\"]}")))
                    .enqueueResult(runResult(database, TaskStatus.PENDING, null, null))
                    .enqueueResult(runResult(database, TaskStatus.RUNNING, JSONB.valueOf("bad"), JSONB.valueOf("bad")))
                    .enqueueResult(runResult(database, TaskStatus.SUCCEEDED, null, null))
                    .enqueueResult(runResult(database, TaskStatus.RUNNING, null, null));
            assertThat(repository.createRun(RUN_ID, PROJECT_ID, TASK_ID, REVISION_ID, BUILD_ID, ENV_ID, 4).warnings()).isEqualTo(List.of("w"));
            assertThat(repository.findById(RUN_ID)).isPresent();
            assertThat(repository.findByTaskId(TASK_ID).orElseThrow().summary()).isEmpty();
            assertThat(repository.findLatestSucceededRun(PROJECT_ID, REVISION_ID)).isPresent();
            assertThat(repository.findLatestRun(PROJECT_ID, null, null)).isPresent();
            assertThat(database.executions().get(4).normalizedSql()).contains("case", "created_at desc");
            database.verifyComplete();
        }
    }

    @Test
    void filtersCountsAndSortsRunPages() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            DependencyAnalysisListRequest request = new DependencyAnalysisListRequest(2, 5, REVISION_ID, 4L, true, false,
                    TaskStatus.SUCCEEDED, "ignored", NOW.minusDays(1), NOW.plusDays(1), "startedAt", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(runResult(database, TaskStatus.SUCCEEDED, null, null));
            assertThat(repository.countRuns(PROJECT_ID, request)).isEqualTo(1);
            assertThat(repository.listRuns(PROJECT_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("source_revision_id =", "environment_config_version =", "created_at >=", "created_at <=");
            assertThat(database.executions().get(1).normalizedSql()).contains("started_at asc", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void coversAllRunSortSelectionsAndLifecycleJsonFallback() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            DependencyAnalysisRepository repository = new DependencyAnalysisRepository(database.dsl(), mapper);
            for (int index = 0; index < 4; index++) database.enqueueResult(database.result(runFields()));
            for (String sort : new String[]{"finishedAt", "status", "", "unknown"}) repository.listRuns(PROJECT_ID,
                    new DependencyAnalysisListRequest(null, null, null, null, null, null, null, sort, "desc"));
            database.enqueueRows(1).enqueueRows(1);
            repository.markRunning(RUN_ID);
            repository.markFinished(RUN_ID, TaskStatus.FAILED, Map.of("error", true), List.of("warning"));
            assertThat(database.executions().get(0).normalizedSql()).contains("finished_at desc");
            assertThat(database.executions().get(2).normalizedSql()).contains("created_at desc");
            assertThat(database.executions().get(5).bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            database.verifyComplete();
        }
    }

    @Test
    void replacesResultItemsNormalizesOptionalFieldsAndHandlesNullConfidence() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            database.enqueueRows(2).enqueueRows(1).enqueueRows(1);
            DependencyAnalysisResultItem full = item(DependencyConfidence.HIGH, Map.of("source", "trace"));
            DependencyAnalysisResultItem sparse = new DependencyAnalysisResultItem(PROJECT_ID, REVISION_ID, TASK_ID, RUN_ID,
                    DependencyType.TEST_TOOL, "pytest", " ", "", null, "", null, "", null, "", "",
                    DependencyTargetMatchStatus.MISSING, DependencyRiskLevel.HIGH, "", "", null, null);
            repository.replaceResultItems(RUN_ID, List.of(full, sparse));
            assertThat(database.executions().get(1).bindings()).contains("gcc", "12", "HIGH");
            assertThat(database.executions().get(2).bindings()).containsNull();
            database.verifyComplete();
        }
    }

    @Test
    void filtersSortsAndMapsResultItems() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            DependencyAnalysisResultListRequest request = new DependencyAnalysisResultListRequest(2, 5,
                    DependencyType.BUILD_TOOL, DependencyTargetMatchStatus.TARGET_NEWER, DependencyRiskLevel.INFO,
                    " gcc ", "riskLevel", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(itemResult(database, JSONB.valueOf("{\"source\":\"trace\"}"), "HIGH"))
                    .enqueueResult(itemResult(database, JSONB.valueOf("bad"), null))
                    .enqueueResult(itemResult(database, null, "LOW"))
                    .enqueueResult(database.result(new Field<?>[]{ITEM_ID_F}, new Object[]{ITEM_ID}));
            assertThat(repository.countResultItems(RUN_ID, request)).isEqualTo(1);
            assertThat(repository.listResultItems(RUN_ID, request).getFirst().evidence()).containsEntry("source", "trace");
            assertThat(repository.findResultItem(ITEM_ID).orElseThrow().confidence()).isNull();
            assertThat(repository.listResultItemViews(RUN_ID)).hasSize(1);
            assertThat(repository.listResultItemIds(RUN_ID)).containsExactly(ITEM_ID);
            assertThat(database.executions().getFirst().normalizedSql()).contains("dependency_type =", "target_match_status =", "risk_level =", "lower");
            assertThat(database.executions().get(1).normalizedSql()).contains("case", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void coversAllResultSortSelections() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            for (int index = 0; index < 5; index++) database.enqueueResult(database.result(itemFields()));
            for (String sort : new String[]{"dependencyType", "dependencyName", "targetMatchStatus", "", "unknown"}) {
                repository.listResultItems(RUN_ID, new DependencyAnalysisResultListRequest(null, null, null, null, null, null, sort, "desc"));
            }
            assertThat(database.executions().get(0).normalizedSql()).contains("dependency_type desc");
            assertThat(database.executions().get(2).normalizedSql()).contains("target_match_status desc");
            assertThat(database.executions().get(4).normalizedSql()).contains("created_at desc");
            database.verifyComplete();
        }
    }

    @Test
    void readsEnvironmentSnapshotAndComponentsAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            DependencyAnalysisRepository repository = repository(database);
            Field<UUID> snapshotId = field("environment_snapshots", "id", UUID.class);
            Field<OffsetDateTime> collectedAt = field("environment_snapshots", "collected_at", OffsetDateTime.class);
            Field<String> name = field("environment_components", "name", String.class);
            Field<String> version = field("environment_components", "version", String.class);
            Field<String> type = field("environment_components", "component_type", String.class);
            Field<String> path = field("environment_components", "path", String.class);
            Field<String> source = field("environment_components", "source", String.class);
            Field<JSONB> metadata = field("environment_components", "metadata", JSONB.class);
            database.enqueueResult(database.result(new Field<?>[]{snapshotId}, new Object[]{SNAPSHOT_ID}))
                    .enqueueResult(database.result(new Field<?>[]{collectedAt}, new Object[]{NOW}))
                    .enqueueResult(database.result(new Field<?>[]{name, version, type, path, source, metadata},
                            new Object[]{"gcc", "13", "PACKAGE", "/usr/bin/gcc", "rpm", JSONB.valueOf("{\"arch\":\"riscv64\"}")}));
            assertThat(repository.findLatestSucceededSnapshotId(PROJECT_ID, ENV_ID)).contains(SNAPSHOT_ID);
            assertThat(repository.findSnapshotCollectedAt(SNAPSHOT_ID)).contains(NOW);
            assertThat(repository.listTargetComponents(SNAPSHOT_ID).getFirst().metadata()).containsEntry("arch", "riscv64");
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(RUN_ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static DependencyAnalysisRepository repository(JooqMockDatabase database) {
        return new DependencyAnalysisRepository(database.dsl(), new ObjectMapper());
    }

    private static DependencyAnalysisResultItem item(DependencyConfidence confidence, Map<String, Object> evidence) {
        return new DependencyAnalysisResultItem(PROJECT_ID, REVISION_ID, TASK_ID, RUN_ID, DependencyType.BUILD_TOOL,
                "gcc", "12", "gcc", "12.2", "12", "gcc", "13.1", "13", "TARGET_NEWER", "HIGH",
                DependencyTargetMatchStatus.TARGET_NEWER, DependencyRiskLevel.INFO, "tool:gcc", "keep", confidence, evidence);
    }

    private static Result<org.jooq.Record> runResult(JooqMockDatabase database, TaskStatus status, JSONB summary, JSONB warnings) {
        return database.result(runFields(), new Object[]{RUN_ID, PROJECT_ID, TASK_ID, REVISION_ID, BUILD_ID, ENV_ID, 4L,
                status.name(), summary, warnings, NOW, NOW, NOW});
    }

    private static Field<?>[] runFields() {
        return new Field<?>[]{RUN_ID_F, RUN_PROJECT, RUN_TASK, RUN_REVISION, RUN_BUILD, RUN_ENV, RUN_VERSION, RUN_STATUS,
                RUN_SUMMARY, RUN_WARNINGS, RUN_STARTED, RUN_FINISHED, RUN_CREATED};
    }

    private static Result<org.jooq.Record> itemResult(JooqMockDatabase database, JSONB evidence, String confidence) {
        return database.result(itemFields(), new Object[]{ITEM_ID, PROJECT_ID, REVISION_ID, TASK_ID, RUN_ID,
                DependencyType.BUILD_TOOL.name(), "gcc", "12", "gcc", "12.2", "12", "gcc", "13.1", "13",
                "TARGET_NEWER", "HIGH", DependencyTargetMatchStatus.TARGET_NEWER.name(), DependencyRiskLevel.INFO.name(),
                "tool:gcc", "keep", confidence, evidence, NOW});
    }

    private static Field<?>[] itemFields() {
        return new Field<?>[]{ITEM_ID_F, ITEM_PROJECT, ITEM_REVISION, ITEM_TASK, ITEM_RUN, ITEM_TYPE, ITEM_NAME, ITEM_VERSION,
                ITEM_SOURCE_PACKAGE, ITEM_SOURCE_PACKAGE_VERSION, ITEM_SOURCE_DETECTED_VERSION, ITEM_TARGET_PACKAGE,
                ITEM_TARGET_PACKAGE_VERSION, ITEM_TARGET_DETECTED_VERSION, ITEM_PROVIDER_STATUS, ITEM_VERSION_CONFIDENCE,
                ITEM_TARGET_STATUS, ITEM_RISK, ITEM_LOCATION, ITEM_RECOMMENDATION, ITEM_CONFIDENCE, ITEM_EVIDENCE, ITEM_CREATED};
    }

    private static <T> Field<T> field(String table, String name, Class<T> type) {
        return DSL.field(DSL.name(table, name), type);
    }
}
