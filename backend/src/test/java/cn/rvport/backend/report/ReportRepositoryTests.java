package cn.rvport.backend.report;

import static cn.rvport.backend.jooq.tables.MigrationInputRefs.MIGRATION_INPUT_REFS;
import static cn.rvport.backend.jooq.tables.ReportInputs.REPORT_INPUTS;
import static cn.rvport.backend.jooq.tables.Reports.REPORTS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.MigrationInputRefsRecord;
import cn.rvport.backend.jooq.tables.records.ReportInputsRecord;
import cn.rvport.backend.jooq.tables.records.ReportsRecord;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
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
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class ReportRepositoryTests {

    private static final UUID REPORT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID INPUT_ID = UUID.fromString("60000000-0000-0000-0000-000000000001");
    private static final UUID SET_ID = UUID.fromString("70000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsFindsAndSelectsLatestReportsWithJsonFallbacks() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            database.enqueueRecord(report(TaskStatus.PENDING, JSONB.valueOf("{\"count\":1}")))
                    .enqueueRecord(report(TaskStatus.PENDING, JSONB.valueOf("bad")))
                    .enqueueRecord(report(TaskStatus.PENDING, null))
                    .enqueueRecord(report(TaskStatus.SUCCEEDED, null))
                    .enqueueRecord(report(TaskStatus.SUCCEEDED, null))
                    .enqueueRecord(report(TaskStatus.RUNNING, null));
            assertThat(repository.createEvaluation(REPORT_ID, PROJECT_ID, REVISION_ID, TASK_ID, "Evaluation", USER_ID).summary()).containsEntry("count", 1);
            assertThat(repository.findById(REPORT_ID).orElseThrow().summary()).isEmpty();
            assertThat(repository.findByTaskId(TASK_ID)).isPresent();
            assertThat(repository.latest(PROJECT_ID, null)).isPresent();
            assertThat(repository.latestSucceeded(PROJECT_ID, REVISION_ID)).isPresent();
            assertThat(repository.latestEvaluation(PROJECT_ID, null)).isPresent();
            assertThat(database.executions().get(4).normalizedSql()).contains("report_type =", "status =", "case");
            database.verifyComplete();
        }
    }

    @Test
    void filtersCountsSortsAndPaginatesReports() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            ReportListRequest request = new ReportListRequest(2, 5, REVISION_ID, TaskStatus.SUCCEEDED, " HIGH ",
                    NOW.minusDays(1), NOW.plusDays(1), "riskLevel", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L})).enqueueRecord(report(TaskStatus.SUCCEEDED, null));
            assertThat(repository.count(PROJECT_ID, request)).isEqualTo(1);
            assertThat(repository.list(PROJECT_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("source_revision_id =", "status =", "risk_level =", "created_at >=", "created_at <=");
            assertThat(database.executions().get(1).normalizedSql()).contains("risk_level asc nulls last", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void supportsAllReportSortsAndRejectsUnknown() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            String[] sorts = {"generatedAt", "createdAt", "status", ""};
            for (String ignored : sorts) database.enqueueResult(database.result(REPORTS.fields()));
            for (String sort : sorts) repository.list(PROJECT_ID,
                    new ReportListRequest(null, null, null, null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("generated_at desc nulls last");
            assertThat(database.executions().get(3).normalizedSql()).contains("generated_at desc nulls last", "created_at desc");
            assertThatThrownBy(() -> repository.list(PROJECT_ID,
                    new ReportListRequest(1, 20, null, null, null, null, null, "title", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported report sort field");
            database.verifyComplete();
        }
    }

    @Test
    void updatesLifecycleWithAndWithoutSummaryAndHandlesMissingRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            database.enqueueRecord(report(TaskStatus.RUNNING, null)).enqueueResult(database.result(REPORTS.fields()))
                    .enqueueRecord(report(TaskStatus.SUCCEEDED, JSONB.valueOf("{\"done\":true}")))
                    .enqueueResult(database.result(REPORTS.fields()));
            assertThat(repository.updateStatus(REPORT_ID, TaskStatus.RUNNING, null)).isNotNull();
            assertThat(repository.updateStatus(REPORT_ID, TaskStatus.FAILED, Map.of("error", true))).isNull();
            assertThat(repository.markSucceeded(REPORT_ID, Map.of("done", true), "LOW").summary()).containsEntry("done", true);
            assertThat(repository.markSucceeded(REPORT_ID, Map.of(), "INFO")).isNull();
            assertThat(database.executions().getFirst().normalizedSql()).doesNotContain("summary =");
            assertThat(database.executions().get(1).normalizedSql()).contains("summary =");
            database.verifyComplete();
        }
    }

    @Test
    void insertsReplacesAndListsInputSnapshots() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            ReportRepository.ReportInputSnapshot snapshot = new ReportRepository.ReportInputSnapshot(migrationView(), Map.of("title", "SIMD"));
            database.enqueueRows(1).enqueueRows(1).enqueueRows(1)
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(input(JSONB.valueOf("{\"title\":\"SIMD\"}")))
                    .enqueueRecord(input(JSONB.valueOf("bad")))
                    .enqueueResult(database.result(new Field<?>[]{REPORT_INPUTS.INPUT_ID}, new Object[]{INPUT_ID}));
            repository.insertInputs(REPORT_ID, List.of(snapshot));
            repository.replaceInputs(REPORT_ID, List.of(snapshot));
            ReportInputListRequest request = new ReportInputListRequest(2, 5, ReportInputType.MIGRATION_INPUT_REF, " SIMD ", "inputType", "desc");
            assertThat(repository.countInputs(REPORT_ID, request)).isEqualTo(1);
            assertThat(repository.listInputs(REPORT_ID, request).getFirst().inputSnapshot()).containsEntry("title", "SIMD");
            assertThat(repository.listAllInputs(REPORT_ID).getFirst().inputSnapshot()).isEmpty();
            assertThat(repository.listMigrationInputIds(REPORT_ID)).containsExactly(INPUT_ID);
            assertThat(database.executions().get(3).normalizedSql()).contains("input_type =", "cast", "lower");
            database.verifyComplete();
        }
    }

    @Test
    void supportsInputSortsAndRejectsUnknown() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            for (int index = 0; index < 2; index++) database.enqueueResult(database.result(REPORT_INPUTS.fields()));
            repository.listInputs(REPORT_ID, new ReportInputListRequest(null, null, null, null, "createdAt", "desc"));
            repository.listInputs(REPORT_ID, new ReportInputListRequest(null, null, null, null, "", "asc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("created_at desc nulls last");
            assertThat(database.executions().get(1).normalizedSql()).contains("created_at asc", "id asc");
            assertThatThrownBy(() -> repository.listInputs(REPORT_ID,
                    new ReportInputListRequest(1, 20, null, null, "snapshot", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported report input sort field");
            database.verifyComplete();
        }
    }

    @Test
    void summarizesAndPreviewsCurrentInputsWithRiskParsing() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            database.enqueueResult(database.result(new Field<?>[]{MIGRATION_INPUT_REFS.STATUS, MIGRATION_INPUT_REFS.SOURCE_TYPE,
                            MIGRATION_INPUT_REFS.DETECTED_LEVEL, DSL.count()},
                    new Object[]{MigrationInputStatus.CONFIRMED.name(), MigrationInputSourceType.KB_FINDING.name(), "HIGH", 2L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(migrationRecord());
            assertThat(repository.summarizeCurrentInputs(PROJECT_ID, REVISION_ID).getFirst().count()).isEqualTo(2);
            ReportInputPreviewListRequest request = new ReportInputPreviewListRequest(2, 5, REVISION_ID,
                    MigrationInputSourceType.KB_FINDING, MigrationInputStatus.CONFIRMED, " high ", " simd ", "locationLabel", "asc");
            assertThat(repository.countInputPreview(PROJECT_ID, REVISION_ID, request)).isEqualTo(1);
            assertThat(repository.listInputPreview(PROJECT_ID, REVISION_ID, request)).hasSize(1);
            assertThat(database.executions().get(1).normalizedSql()).contains("upper", "like", "source_type =", "status =", "lower");
            assertThat(database.executions().get(2).normalizedSql()).contains("location_label asc nulls last", "offset ? rows");
            assertThatThrownBy(() -> repository.countInputPreview(PROJECT_ID, REVISION_ID,
                    new ReportInputPreviewListRequest(1, 20, null, null, null, "severe", null, null, null)))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported report input preview risk level");
            database.verifyComplete();
        }
    }

    @Test
    void supportsEveryPreviewSortAndRejectsUnknown() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportRepository repository = repository(database);
            String[] sorts = {"createdAt", "updatedAt", "sourceType", "detectedLevel", "status", "issueTitle", ""};
            for (String ignored : sorts) database.enqueueResult(database.result(MIGRATION_INPUT_REFS.fields()));
            for (String sort : sorts) repository.listInputPreview(PROJECT_ID, REVISION_ID,
                    new ReportInputPreviewListRequest(null, null, null, null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("created_at desc nulls last");
            assertThat(database.executions().get(6).normalizedSql()).contains("updated_at desc nulls last", "created_at desc");
            assertThatThrownBy(() -> repository.listInputPreview(PROJECT_ID, REVISION_ID,
                    new ReportInputPreviewListRequest(1, 20, null, null, null, null, null, "note", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported report input preview sort field");
            database.verifyComplete();
        }
    }

    @Test
    void rejectsNonSerializableJsonAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            ReportRepository repository = new ReportRepository(database.dsl(), mapper);
            assertThatThrownBy(() -> repository.markSucceeded(REPORT_ID, Map.of("bad", true), "HIGH"))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("not serializable");
            assertThat(database.executions()).isEmpty();
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(REPORT_ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static ReportRepository repository(JooqMockDatabase database) {
        return new ReportRepository(database.dsl(), new ObjectMapper());
    }

    private static ReportsRecord report(TaskStatus status, JSONB summary) {
        return new ReportsRecord(REPORT_ID, PROJECT_ID, TASK_ID, ReportType.EVALUATION.name(), status.name(), "Evaluation",
                summary, "LOW", null, null, USER_ID, NOW, NOW, REVISION_ID);
    }

    private static ReportInputsRecord input(JSONB snapshot) {
        ReportInputsRecord record = new ReportInputsRecord();
        record.setId(UUID.randomUUID());
        record.setReportId(REPORT_ID);
        record.setInputType(ReportInputType.MIGRATION_INPUT_REF.name());
        record.setInputId(INPUT_ID);
        record.setInputSnapshot(snapshot);
        record.setCreatedAt(NOW);
        return record;
    }

    private static MigrationInputRefsRecord migrationRecord() {
        return new MigrationInputRefsRecord(INPUT_ID, SET_ID, PROJECT_ID, REVISION_ID, "SIMD issue",
                MigrationInputSourceType.KB_FINDING.name(), UUID.randomUUID(), "HIGH", "src/a.c:4", "fix",
                MigrationInputStatus.CONFIRMED.name(), null, NOW, NOW, "R1", "src/a.c", "fn", "anchor", "fp");
    }

    private static MigrationInputRefView migrationView() {
        return MigrationInputRefView.from(migrationRecord());
    }
}
