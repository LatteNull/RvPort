package cn.rvport.backend.kb.ai;

import static cn.rvport.backend.jooq.tables.KbAiExtensionResults.KB_AI_EXTENSION_RESULTS;
import static cn.rvport.backend.jooq.tables.KbAiExtensionRuns.KB_AI_EXTENSION_RUNS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.KbAiExtensionResultsRecord;
import cn.rvport.backend.jooq.tables.records.KbAiExtensionRunsRecord;
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

class KbAiExtensionRepositoryTests {

    private static final UUID PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID SCAN_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID RUN_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID FINDING_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("60000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsAttachesAndFindsRunsWithSummaryFallback() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            database.enqueueRecord(run(KbAiExtensionStatus.PENDING, JSONB.valueOf("{}")))
                    .enqueueRecord(run(KbAiExtensionStatus.QUEUED, JSONB.valueOf("{\"count\":2}")))
                    .enqueueRecord(run(KbAiExtensionStatus.SUCCEEDED, JSONB.valueOf("bad")))
                    .enqueueResult(database.result(KB_AI_EXTENSION_RUNS.fields()));
            assertThat(repository.createRun(PROJECT_ID, REVISION_ID, SCAN_ID, UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID()).status())
                    .isEqualTo(KbAiExtensionStatus.PENDING);
            assertThat(repository.attachTask(RUN_ID, TASK_ID).summary()).containsEntry("count", 2);
            assertThat(repository.findById(RUN_ID).orElseThrow().summary()).isEmpty();
            assertThat(repository.findByTaskId(UUID.randomUUID())).isEmpty();
            database.verifyComplete();
        }
    }

    @Test
    void findsLatestCompletedAndFiltersSortedLists() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            KbAiExtensionListRequest request = new KbAiExtensionListRequest(
                    2, 10, KbAiExtensionStatus.SUCCEEDED, REVISION_ID, SCAN_ID, "status", "asc");
            database.enqueueRecord(run(KbAiExtensionStatus.SUCCEEDED, null))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(run(KbAiExtensionStatus.SUCCEEDED, null));
            assertThat(repository.findLatestCompletedRun(SCAN_ID)).isPresent();
            assertThat(repository.countRuns(PROJECT_ID, request)).isEqualTo(1L);
            assertThat(repository.listRuns(PROJECT_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("status in", "finished_at desc nulls last");
            assertThat(database.executions().get(1).normalizedSql()).contains("status =", "source_revision_id =", "kb_scan_run_id =");
            assertThat(database.executions().get(2).normalizedSql()).contains("status asc nulls last", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void supportsAllRunSortsAndRejectsUnknownSort() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            String[] sorts = {"startedAt", "finishedAt", "createdAt", "", null};
            for (String ignored : sorts) database.enqueueResult(database.result(KB_AI_EXTENSION_RUNS.fields()));
            for (String sort : sorts) repository.listRuns(PROJECT_ID,
                    new KbAiExtensionListRequest(null, null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(0).normalizedSql()).contains("started_at desc nulls last");
            assertThat(database.executions().get(1).normalizedSql()).contains("finished_at desc nulls last");
            assertThat(database.executions().get(3).normalizedSql()).contains("created_at desc", "id desc");
            assertThatThrownBy(() -> repository.listRuns(PROJECT_ID,
                    new KbAiExtensionListRequest(1, 20, null, null, null, "updatedAt", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported KB AI extension sort field");
            database.verifyComplete();
        }
    }

    @Test
    void marksLifecycleWithOptionalArtifactIdsAndJsonFallback() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), mapper);
            database.enqueueRows(1).enqueueRows(1).enqueueRows(1);
            repository.markRunning(RUN_ID);
            repository.markFinished(RUN_ID, KbAiExtensionStatus.SUCCEEDED, Map.of("count", 1),
                    UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID());
            repository.markFinished(RUN_ID, KbAiExtensionStatus.FAILED, null, null, null, null);
            assertThat(database.executions().get(1).normalizedSql()).contains("input_artifact_id", "output_artifact_id", "agent_output_artifact_id");
            assertThat(database.executions().get(1).bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            assertThat(database.executions().get(2).normalizedSql()).doesNotContain("input_artifact_id", "output_artifact_id", "agent_output_artifact_id");
            database.verifyComplete();
        }
    }

    @Test
    void replacesResultsNormalizesTextAndCopiesPayload() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            database.enqueueRows(2).enqueueRows(1).enqueueRows(1);
            Map<String, Object> mutable = new java.util.HashMap<>();
            mutable.put("line", 3);
            KbAiExtensionRepository.KbAiExtensionResultInput input = new KbAiExtensionRepository.KbAiExtensionResultInput(
                    PROJECT_ID, REVISION_ID, SCAN_ID, FINDING_ID, " summary ", " ", new BigDecimal("0.8"), " FIX ", mutable);
            mutable.put("line", 9);
            repository.replaceResults(RUN_ID, List.of(input, new KbAiExtensionRepository.KbAiExtensionResultInput(
                    PROJECT_ID, REVISION_ID, SCAN_ID, UUID.randomUUID(), null, null, null, null, null)));
            assertThat(database.executions()).hasSize(3);
            assertThat(database.executions().get(1).bindings()).contains("summary", "FIX").containsNull();
            assertThat(database.executions().get(1).bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).contains("\"line\":3");
            });
            database.verifyComplete();
        }
    }

    @Test
    void returnsLatestSuggestionsAndShortCircuitsEmptyOrIncompleteData() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            assertThat(repository.latestSuggestions(SCAN_ID, null)).isEmpty();
            assertThat(repository.latestSuggestions(SCAN_ID, List.of())).isEmpty();
            assertThat(database.executions()).isEmpty();
            database.enqueueResult(database.result(KB_AI_EXTENSION_RUNS.fields()))
                    .enqueueRecord(run(KbAiExtensionStatus.SUCCEEDED, null))
                    .enqueueRecord(result(FINDING_ID, JSONB.valueOf("{\"reason\":\"portable\"}")))
                    .enqueueRecord(run(KbAiExtensionStatus.PARTIAL_SUCCESS, null))
                    .enqueueRecord(result(FINDING_ID, JSONB.valueOf("bad")));
            assertThat(repository.latestSuggestions(SCAN_ID, List.of(FINDING_ID))).isEmpty();
            assertThat(repository.latestSuggestions(SCAN_ID, List.of(FINDING_ID))).containsKey(FINDING_ID);
            assertThat(repository.latestSuggestion(SCAN_ID, FINDING_ID)).isPresent()
                    .get().satisfies(value -> assertThat(value.rawPayload()).isEmpty());
            database.verifyComplete();
        }
    }

    @Test
    void propagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            KbAiExtensionRepository repository = new KbAiExtensionRepository(database.dsl(), new ObjectMapper());
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(RUN_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class).hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static KbAiExtensionRunsRecord run(KbAiExtensionStatus status, JSONB summary) {
        KbAiExtensionRunsRecord record = new KbAiExtensionRunsRecord();
        record.setId(RUN_ID); record.setProjectId(PROJECT_ID); record.setSourceRevisionId(REVISION_ID); record.setKbScanRunId(SCAN_ID);
        record.setTaskId(TASK_ID); record.setStatus(status.name()); record.setSummary(summary); record.setCreatedAt(NOW); record.setUpdatedAt(NOW);
        return record;
    }

    private static KbAiExtensionResultsRecord result(UUID findingId, JSONB payload) {
        return new KbAiExtensionResultsRecord(UUID.randomUUID(), RUN_ID, PROJECT_ID, REVISION_ID, SCAN_ID, findingId,
                "summary", "suggestion", new BigDecimal("0.9"), "FIX", payload, NOW);
    }
}
