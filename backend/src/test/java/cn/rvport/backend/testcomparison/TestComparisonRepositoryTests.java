package cn.rvport.backend.testcomparison;

import static cn.rvport.backend.jooq.tables.TestComparisonFindings.TEST_COMPARISON_FINDINGS;
import static cn.rvport.backend.jooq.tables.TestComparisonRuns.TEST_COMPARISON_RUNS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.TestComparisonFindingsRecord;
import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
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

class TestComparisonRepositoryTests {

    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID BATCH_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID SOURCE_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID TARGET_ID = UUID.fromString("50000000-0000-0000-0000-000000000002");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsAndFindsRunsWithJsonFallbacks() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            database.enqueueRecord(run(JSONB.valueOf("{\"truncated\":true}"), JSONB.valueOf("{\"total\":2}"), JSONB.valueOf("bad")))
                    .enqueueRecord(run(null, null, null)).enqueueRecord(run(null, null, null))
                    .enqueueResult(database.result(TEST_COMPARISON_RUNS.fields()));

            assertThat(repository.createIfAbsent(PROJECT_ID, BATCH_ID, SOURCE_ID, TARGET_ID).status())
                    .isEqualTo(TestComparisonStatus.PENDING);
            TestComparisonRunView byId = repository.findById(ID).orElseThrow();
            assertThat(byId.inputSummary()).isEmpty();
            assertThat(repository.findByTaskId(TASK_ID)).isPresent();
            assertThat(repository.findByTestRunId(UUID.randomUUID())).isEmpty();
            assertThat(database.executions().getFirst().normalizedSql()).contains("on conflict", "updated_at");
            database.verifyComplete();
        }
    }

    @Test
    void filtersListsAndSupportsAllRunSorts() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            TestComparisonListRequest request = new TestComparisonListRequest(
                    TestComparisonStatus.SUCCEEDED, TestComparisonRiskLevel.HIGH, BATCH_ID, SOURCE_ID, TARGET_ID,
                    2, 10, "riskLevel", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L})).enqueueRecord(run(null, null, null));
            assertThat(repository.count(PROJECT_ID, request)).isEqualTo(1L);
            assertThat(repository.list(PROJECT_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql())
                    .contains("status =", "risk_level =", "test_batch_id =", "source_test_run_id =", "target_test_run_id =");
            assertThat(database.executions().get(1).normalizedSql()).contains("risk_level asc nulls last", "offset ? rows");
            database.verifyComplete();
        }

        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            String[] sorts = {"status", "finishedAt", "updatedAt", "unknown"};
            for (String ignored : sorts) database.enqueueResult(database.result(TEST_COMPARISON_RUNS.fields()));
            for (String sort : sorts) repository.list(PROJECT_ID,
                    new TestComparisonListRequest(null, null, null, null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("status desc nulls last");
            assertThat(database.executions().get(1).normalizedSql()).contains("finished_at desc nulls last");
            assertThat(database.executions().get(2).normalizedSql()).contains("updated_at desc nulls last");
            assertThat(database.executions().get(3).normalizedSql()).contains("created_at desc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void advancesAllRunLifecycleStates() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            for (int index = 0; index < 5; index++) database.enqueueRows(1);
            repository.markQueued(ID, TASK_ID);
            repository.markRunning(ID);
            repository.markUnavailable(ID, "NO_MODEL", "missing model");
            repository.markFailed(ID, TestComparisonStatus.FAILED, "AGENT", "failed");
            repository.saveResult(ID, TestComparisonOverallStatus.EQUIVALENT, TestComparisonRiskLevel.LOW,
                    new BigDecimal("0.95"), " ok ", " retry ", Map.of("total", 2), null, false, null, UUID.randomUUID());
            assertThat(database.executions().get(0).normalizedSql()).contains("status in");
            assertThat(database.executions().get(1).normalizedSql()).contains("started_at");
            assertThat(database.executions().get(2).normalizedSql()).contains("unavailable_code", "unavailable_message");
            assertThat(database.executions().get(3).normalizedSql()).contains("error_code", "error_message");
            assertThat(database.executions().get(4).bindings()).contains("ok", "retry");
            database.verifyComplete();
        }
    }

    @Test
    void replacesFindingsWithDefaultsNullInputAndSequentialNumbers() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            database.enqueueRows(1).enqueueRows(1).enqueueRows(1).enqueueRows(2);
            TestComparisonParsedFinding finding = new TestComparisonParsedFinding(
                    null, null, new BigDecimal("0.5"), null, "  detail  ", " ", null, " fix ", Map.of("line", 1));
            repository.replaceFindings(ID, List.of(finding, finding));
            repository.replaceFindings(ID, null);
            assertThat(database.executions()).hasSize(4);
            assertThat(database.executions().get(1).bindings()).contains(1, "OTHER", TestComparisonRiskLevel.INFO.name(), "未命名差异", "detail", "fix").containsNull();
            assertThat(database.executions().get(2).bindings()).contains(2);
            database.verifyComplete();
        }
    }

    @Test
    void filtersAndSortsFindingLists() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            TestComparisonFindingListRequest request = new TestComparisonFindingListRequest(
                    TestComparisonRiskLevel.HIGH, " REGRESSION ", 2, 25, "differenceType", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(finding(JSONB.valueOf("{\"test\":\"failed\"}")));
            assertThat(repository.countFindings(ID, request)).isEqualTo(1L);
            assertThat(repository.listFindings(ID, request)).singleElement()
                    .satisfies(value -> assertThat(value.rawPayload()).containsEntry("test", "failed"));
            assertThat(database.executions().getFirst().normalizedSql()).contains("severity =", "difference_type =");
            assertThat(database.executions().get(1).normalizedSql()).contains("difference_type asc nulls last", "offset ? rows");
            database.verifyComplete();
        }

        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            String[] sorts = {"severity", "createdAt", "unknown"};
            for (String ignored : sorts) database.enqueueResult(database.result(TEST_COMPARISON_FINDINGS.fields()));
            for (String sort : sorts) repository.listFindings(ID,
                    new TestComparisonFindingListRequest(null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("severity desc nulls last");
            assertThat(database.executions().get(1).normalizedSql()).contains("created_at desc nulls last");
            assertThat(database.executions().get(2).normalizedSql()).contains("sequence_no desc nulls last");
            database.verifyComplete();
        }

        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{0L}));
            assertThat(repository.countFindings(ID,
                    new TestComparisonFindingListRequest(null, "  ", 1, 20, null, null))).isZero();
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("difference_type =");
            database.verifyComplete();
        }
    }

    @Test
    void fallsBackWhenJsonSerializationFailsAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), mapper);
            database.enqueueRows(1);
            repository.saveResult(ID, null, null, null, null, null, Map.of("x", 1), Map.of(), true, Map.of(), null);
            assertThat(database.lastExecution().bindings()).filteredOn(JSONB.class::isInstance)
                    .allSatisfy(value -> assertThat(((JSONB) value).data()).isEqualTo("{}"));
            database.verifyComplete();
        }
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TestComparisonRepository repository = new TestComparisonRepository(database.dsl(), new ObjectMapper());
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static TestComparisonRunsRecord run(JSONB input, JSONB source, JSONB target) {
        TestComparisonRunsRecord record = new TestComparisonRunsRecord();
        record.setId(ID); record.setProjectId(PROJECT_ID); record.setTaskId(TASK_ID); record.setTestBatchId(BATCH_ID);
        record.setSourceTestRunId(SOURCE_ID); record.setTargetTestRunId(TARGET_ID); record.setStatus(TestComparisonStatus.PENDING.name());
        record.setInputSummary(input); record.setSourceTestStats(source); record.setTargetTestStats(target); record.setCreatedAt(NOW); record.setUpdatedAt(NOW);
        return record;
    }

    private static TestComparisonFindingsRecord finding(JSONB raw) {
        TestComparisonFindingsRecord record = new TestComparisonFindingsRecord();
        record.setId(UUID.randomUUID()); record.setComparisonRunId(ID); record.setSequenceNo(1); record.setDifferenceType("REGRESSION");
        record.setSeverity(TestComparisonRiskLevel.HIGH.name()); record.setTitle("failure"); record.setRawPayload(raw); record.setCreatedAt(NOW);
        return record;
    }
}
