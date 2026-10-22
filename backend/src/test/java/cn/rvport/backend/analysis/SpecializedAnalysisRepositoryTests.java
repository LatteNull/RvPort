package cn.rvport.backend.analysis;

import static cn.rvport.backend.jooq.tables.SpecializedAnalysisFindings.SPECIALIZED_ANALYSIS_FINDINGS;
import static cn.rvport.backend.jooq.tables.SpecializedAnalysisRuns.SPECIALIZED_ANALYSIS_RUNS;
import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.core.type.TypeReference;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Record1;
import org.jooq.Result;
import org.jooq.SQLDialect;
import org.jooq.impl.DSL;
import org.jooq.tools.jdbc.MockConnection;
import org.jooq.tools.jdbc.MockResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class SpecializedAnalysisRepositoryTests {

    private final List<String> sql = new ArrayList<>();
    private final DSLContext records = DSL.using(SQLDialect.POSTGRES);
    private SpecializedAnalysisRepository repository;
    private UUID runId;
    private UUID projectId;
    private UUID findingId;
    private final List<Object[]> findingInsertBindings = new ArrayList<>();
    private JSONB findingDetail = JSONB.valueOf("{\"key\":\"value\"}");

    @BeforeEach
    void setUp() {
        runId = UUID.randomUUID();
        projectId = UUID.randomUUID();
        findingId = UUID.randomUUID();
        MockConnection connection = new MockConnection(context -> {
            String statement = context.sql().toLowerCase();
            sql.add(statement);
            if (statement.startsWith("insert into") && statement.contains("specialized_analysis_findings")) {
                findingInsertBindings.add(context.bindings().clone());
            }
            if (statement.contains("count(*)")) return new MockResult[] { countResult(1) };
            if (statement.startsWith("select") && statement.contains("specialized_analysis_findings")) {
                return new MockResult[] { findingResult() };
            }
            if ((statement.startsWith("select") || statement.contains("returning"))
                    && statement.contains("specialized_analysis_runs")) {
                return new MockResult[] { runResult() };
            }
            return new MockResult[] { new MockResult(1) };
        });
        repository = new SpecializedAnalysisRepository(DSL.using(connection, SQLDialect.POSTGRES), new ObjectMapper());
    }

    @Test
    void coversRunLifecycleLatestFiltersAndEverySortField() {
        UUID taskId = UUID.randomUUID();
        UUID sourceId = UUID.randomUUID();
        UUID buildId = UUID.randomUUID();
        assertThat(repository.create(runId, projectId, taskId, SpecializedAnalyzerType.FLOATING_POINT,
                sourceId, buildId, "a".repeat(64), 3L, UUID.randomUUID()).id()).isEqualTo(runId);
        assertThat(repository.findById(runId)).isPresent();
        assertThat(repository.findByTaskId(taskId)).isPresent();
        assertThat(repository.latest(projectId, SpecializedAnalyzerType.FLOATING_POINT)).isPresent();
        assertThat(repository.latestPublished(projectId, sourceId, SpecializedAnalyzerType.FLOATING_POINT)).isPresent();
        repository.create(UUID.randomUUID(), projectId, taskId, SpecializedAnalyzerType.MEMORY_ORDER,
                sourceId, buildId, "b".repeat(64), null, UUID.randomUUID());

        SpecializedAnalysisListRequest unfiltered = new SpecializedAnalysisListRequest(0, 0, " ", " ", null, "asc");
        assertThat(repository.count(projectId, SpecializedAnalyzerType.FLOATING_POINT, unfiltered)).isEqualTo(1);
        assertThat(repository.list(projectId, SpecializedAnalyzerType.FLOATING_POINT, unfiltered)).hasSize(1);

        for (String sort : List.of("createdAt", "finishedAt", "status", "findingCount")) {
            SpecializedAnalysisListRequest request = new SpecializedAnalysisListRequest(2, 10, " running ",
                    " risk ", sort, sort.equals("status") ? "asc" : "desc");
            assertThat(repository.count(projectId, SpecializedAnalyzerType.FLOATING_POINT, request)).isEqualTo(1);
            assertThat(repository.list(projectId, SpecializedAnalyzerType.FLOATING_POINT, request)).hasSize(1);
        }
        repository.markRunning(runId, "0.5.0");
        repository.fail(runId, SpecializedAnalysisStatus.FAILED, null);
        repository.fail(runId, SpecializedAnalysisStatus.TIMEOUT, "timeout");
        assertThat(sql).anyMatch(value -> value.contains("order by") && value.contains("finding_count"));
    }

    @Test
    void coversFindingFiltersSortsImportAndCandidateCounts() {
        SpecializedFindingImport finding = imported("FINDING");
        SpecializedFindingImport candidate = imported("SOURCE_CANDIDATE");
        repository.complete(runId, SpecializedAnalysisStatus.COMPLETE_WITH_RISK, "risk", 3,
                Map.of("diagnosticCount", 2), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), List.of(finding, candidate));

        assertThat(repository.findFinding(findingId)).isPresent();
        assertThat(repository.listFindingIds(runId)).contains(findingId);
        SpecializedFindingListRequest unfiltered = new SpecializedFindingListRequest(0, 0, " ", " ", " ",
                " ", " ", " ", null, "asc");
        assertThat(repository.countFindings(runId, unfiltered)).isEqualTo(1);
        assertThat(repository.listFindings(runId, unfiltered)).hasSize(1);
        for (String sort : List.of("createdAt", "severity", "filePath", "startLine", "code")) {
            SpecializedFindingListRequest request = new SpecializedFindingListRequest(1, 50, " high ",
                    " confirmed ", "precision", "FP_TEST", "src/", "risk", sort,
                    sort.equals("severity") ? "asc" : "desc");
            assertThat(repository.countFindings(runId, request)).isEqualTo(1);
            assertThat(repository.listFindings(runId, request)).hasSize(1);
        }
        assertThat(sql.stream().filter(value -> value.startsWith("insert into \"public\".\"specialized_analysis_findings\"")).count())
                .isEqualTo(2);
        assertThat(sql).anyMatch(value -> value.startsWith("update \"public\".\"specialized_analysis_runs\""));
        repository.complete(runId, SpecializedAnalysisStatus.COMPLETE, "complete", 0, null,
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), null, List.of());
    }

    @ParameterizedTest
    @EnumSource(FloatingPointEvidenceFixture.class)
    void savesAndReadsEvidenceStepDescriptionsWithoutRewritingLegacyDetail(
            FloatingPointEvidenceFixture fixture) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        var expected = fixture.detail(mapper);
        Map<String, Object> detail = mapper.convertValue(expected, new TypeReference<>() { });
        repository.complete(runId, SpecializedAnalysisStatus.PARTIAL, "partial", 4, Map.of(),
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), null,
                List.of(imported("FINDING", detail)));

        assertThat(findingInsertBindings).hasSize(1);
        Object[] bindings = findingInsertBindings.getFirst();
        // detail 是 INSERT 最后一个字段；读取实际 JDBC 参数，避免仅验证预设返回值。
        findingDetail = JSONB.valueOf(bindings[bindings.length - 1].toString());
        assertThat(mapper.readTree(findingDetail.data())).isEqualTo(expected);
        var saved = repository.findFinding(findingId).orElseThrow();
        assertThat(mapper.<JsonNode>valueToTree(saved.detail())).isEqualTo(expected);
        assertThat(mapper.<JsonNode>valueToTree(detail)).isEqualTo(expected);
    }

    private SpecializedFindingImport imported(String kind) {
        return imported(kind, Map.of("key", "value"));
    }

    private SpecializedFindingImport imported(String kind, Map<String, Object> detail) {
        return new SpecializedFindingImport(kind + "-1", kind, "FP_TEST", "precision", "HIGH", "0.9",
                "CONFIRMED", "风险", "Risk", "详情", "Detail", "建议", "Suggestion", "测试", "Test",
                "src/main.c", 1, 2, 1, 4, kind.equals("SOURCE_CANDIDATE"), "digest", detail);
    }

    private MockResult runResult() {
        var record = records.newRecord(SPECIALIZED_ANALYSIS_RUNS);
        OffsetDateTime now = OffsetDateTime.now();
        record.setId(runId);
        record.setProjectId(projectId);
        record.setTaskId(UUID.randomUUID());
        record.setAnalyzerType("FLOATING_POINT");
        record.setSourceRevisionId(UUID.randomUUID());
        record.setBuildRunId(UUID.randomUUID());
        record.setArtifactSetId("a".repeat(64));
        record.setEnvironmentConfigVersion(3L);
        record.setRequestSchemaVersion("1.4");
        record.setResultSchemaVersion("2.0");
        record.setStatus("COMPLETE");
        record.setVerdict("complete");
        record.setSummary(JSONB.valueOf("{\"findingCount\":1}"));
        record.setFindingCount(1);
        record.setCandidateCount(0);
        record.setDiagnosticCount(0);
        record.setCreatedBy(UUID.randomUUID());
        record.setCreatedAt(now);
        record.setUpdatedAt(now);
        Result<cn.rvport.backend.jooq.tables.records.SpecializedAnalysisRunsRecord> result =
                records.newResult(SPECIALIZED_ANALYSIS_RUNS);
        result.add(record);
        return new MockResult(1, result);
    }

    private MockResult findingResult() {
        var record = records.newRecord(SPECIALIZED_ANALYSIS_FINDINGS);
        record.setId(findingId);
        record.setRunId(runId);
        record.setProjectId(projectId);
        record.setSourceRevisionId(UUID.randomUUID());
        record.setAnalyzerType("FLOATING_POINT");
        record.setExternalFindingId("fp-1");
        record.setFindingKind("FINDING");
        record.setFindingCode("FP_TEST");
        record.setCategory("precision");
        record.setSeverity("HIGH");
        record.setResultStatus("CONFIRMED");
        record.setTitle("风险");
        record.setMessage("详情");
        record.setRequiresHumanConfirmation(false);
        record.setDetail(findingDetail);
        record.setCreatedAt(OffsetDateTime.now());
        Result<cn.rvport.backend.jooq.tables.records.SpecializedAnalysisFindingsRecord> result =
                records.newResult(SPECIALIZED_ANALYSIS_FINDINGS);
        result.add(record);
        return new MockResult(1, result);
    }

    private MockResult countResult(int count) {
        Field<Integer> field = DSL.field("count", Integer.class);
        Result<Record1<Integer>> result = records.newResult(field);
        Record1<Integer> record = records.newRecord(field);
        record.set(field, count);
        result.add(record);
        return new MockResult(1, result);
    }
}
