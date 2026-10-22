package cn.rvport.backend.testcomparison;

import static cn.rvport.backend.jooq.tables.TestComparisonFindings.TEST_COMPARISON_FINDINGS;
import static cn.rvport.backend.jooq.tables.TestComparisonRuns.TEST_COMPARISON_RUNS;

import cn.rvport.backend.jooq.tables.records.TestComparisonFindingsRecord;
import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.OrderField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class TestComparisonRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public TestComparisonRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public TestComparisonRunView createIfAbsent(UUID projectId, UUID testBatchId, UUID sourceTestRunId, UUID targetTestRunId) {
        TestComparisonRunsRecord record = dsl.insertInto(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.PROJECT_ID, projectId)
                .set(TEST_COMPARISON_RUNS.TEST_BATCH_ID, testBatchId)
                .set(TEST_COMPARISON_RUNS.SOURCE_TEST_RUN_ID, sourceTestRunId)
                .set(TEST_COMPARISON_RUNS.TARGET_TEST_RUN_ID, targetTestRunId)
                .set(TEST_COMPARISON_RUNS.STATUS, TestComparisonStatus.PENDING.name())
                .onConflict(TEST_COMPARISON_RUNS.PROJECT_ID, TEST_COMPARISON_RUNS.SOURCE_TEST_RUN_ID, TEST_COMPARISON_RUNS.TARGET_TEST_RUN_ID)
                .doUpdate()
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .returning()
                .fetchOne();
        return view(record);
    }

    public Optional<TestComparisonRunView> findById(UUID id) {
        return dsl.selectFrom(TEST_COMPARISON_RUNS)
                .where(TEST_COMPARISON_RUNS.ID.eq(id))
                .fetchOptional(this::view);
    }

    public Optional<TestComparisonRunView> findByTaskId(UUID taskId) {
        return dsl.selectFrom(TEST_COMPARISON_RUNS)
                .where(TEST_COMPARISON_RUNS.TASK_ID.eq(taskId))
                .fetchOptional(this::view);
    }

    public Optional<TestComparisonRunView> findByTestRunId(UUID testRunId) {
        return dsl.selectFrom(TEST_COMPARISON_RUNS)
                .where(TEST_COMPARISON_RUNS.SOURCE_TEST_RUN_ID.eq(testRunId)
                        .or(TEST_COMPARISON_RUNS.TARGET_TEST_RUN_ID.eq(testRunId)))
                .orderBy(TEST_COMPARISON_RUNS.CREATED_AT.desc(), TEST_COMPARISON_RUNS.ID.desc())
                .limit(1)
                .fetchOptional(this::view);
    }

    public long count(UUID projectId, TestComparisonListRequest request) {
        return dsl.selectCount()
                .from(TEST_COMPARISON_RUNS)
                .where(filter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<TestComparisonRunView> list(UUID projectId, TestComparisonListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(TEST_COMPARISON_RUNS)
                .where(filter(projectId, request))
                .orderBy(orderBy(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::view);
    }

    public void markQueued(UUID id, UUID taskId) {
        dsl.update(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.STATUS, TestComparisonStatus.QUEUED.name())
                .set(TEST_COMPARISON_RUNS.TASK_ID, taskId)
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(TEST_COMPARISON_RUNS.ID.eq(id)
                        .and(TEST_COMPARISON_RUNS.STATUS.in(TestComparisonStatus.PENDING.name(), TestComparisonStatus.UNAVAILABLE.name())))
                .execute();
    }

    public void markRunning(UUID id) {
        dsl.update(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.STATUS, TestComparisonStatus.RUNNING.name())
                .set(TEST_COMPARISON_RUNS.STARTED_AT, OffsetDateTime.now())
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(TEST_COMPARISON_RUNS.ID.eq(id))
                .execute();
    }

    public void markUnavailable(UUID id, String code, String message) {
        dsl.update(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.STATUS, TestComparisonStatus.UNAVAILABLE.name())
                .set(TEST_COMPARISON_RUNS.UNAVAILABLE_CODE, code)
                .set(TEST_COMPARISON_RUNS.UNAVAILABLE_MESSAGE, message)
                .set(TEST_COMPARISON_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(TEST_COMPARISON_RUNS.ID.eq(id))
                .execute();
    }

    public void markFailed(UUID id, TestComparisonStatus status, String code, String message) {
        dsl.update(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.STATUS, status.name())
                .set(TEST_COMPARISON_RUNS.ERROR_CODE, code)
                .set(TEST_COMPARISON_RUNS.ERROR_MESSAGE, message)
                .set(TEST_COMPARISON_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(TEST_COMPARISON_RUNS.ID.eq(id))
                .execute();
    }

    public void saveResult(
            UUID id,
            TestComparisonOverallStatus overallStatus,
            TestComparisonRiskLevel riskLevel,
            BigDecimal confidence,
            String summary,
            String recommendation,
            Map<String, Object> sourceStats,
            Map<String, Object> targetStats,
            boolean inputTruncated,
            Map<String, Object> inputSummary,
            UUID artifactId
    ) {
        dsl.update(TEST_COMPARISON_RUNS)
                .set(TEST_COMPARISON_RUNS.STATUS, TestComparisonStatus.SUCCEEDED.name())
                .set(TEST_COMPARISON_RUNS.OVERALL_STATUS, overallStatus == null ? null : overallStatus.name())
                .set(TEST_COMPARISON_RUNS.RISK_LEVEL, riskLevel == null ? null : riskLevel.name())
                .set(TEST_COMPARISON_RUNS.CONFIDENCE, confidence)
                .set(TEST_COMPARISON_RUNS.SUMMARY, blankToNull(summary))
                .set(TEST_COMPARISON_RUNS.RECOMMENDATION, blankToNull(recommendation))
                .set(TEST_COMPARISON_RUNS.SOURCE_TEST_STATS, toJsonb(sourceStats))
                .set(TEST_COMPARISON_RUNS.TARGET_TEST_STATS, toJsonb(targetStats))
                .set(TEST_COMPARISON_RUNS.INPUT_TRUNCATED, inputTruncated)
                .set(TEST_COMPARISON_RUNS.INPUT_SUMMARY, toJsonb(inputSummary))
                .set(TEST_COMPARISON_RUNS.AGENT_OUTPUT_ARTIFACT_ID, artifactId)
                .set(TEST_COMPARISON_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(TEST_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(TEST_COMPARISON_RUNS.ID.eq(id))
                .execute();
    }

    public void replaceFindings(UUID comparisonRunId, List<TestComparisonParsedFinding> findings) {
        dsl.deleteFrom(TEST_COMPARISON_FINDINGS)
                .where(TEST_COMPARISON_FINDINGS.COMPARISON_RUN_ID.eq(comparisonRunId))
                .execute();
        int sequence = 1;
        for (TestComparisonParsedFinding finding : findings == null ? List.<TestComparisonParsedFinding>of() : findings) {
            dsl.insertInto(TEST_COMPARISON_FINDINGS)
                    .set(TEST_COMPARISON_FINDINGS.COMPARISON_RUN_ID, comparisonRunId)
                    .set(TEST_COMPARISON_FINDINGS.SEQUENCE_NO, sequence++)
                    .set(TEST_COMPARISON_FINDINGS.DIFFERENCE_TYPE, defaultValue(finding.differenceType(), "OTHER"))
                    .set(TEST_COMPARISON_FINDINGS.SEVERITY, defaultValue(finding.severity(), TestComparisonRiskLevel.INFO).name())
                    .set(TEST_COMPARISON_FINDINGS.CONFIDENCE, finding.confidence())
                    .set(TEST_COMPARISON_FINDINGS.TITLE, defaultValue(finding.title(), "未命名差异"))
                    .set(TEST_COMPARISON_FINDINGS.DESCRIPTION, blankToNull(finding.description()))
                    .set(TEST_COMPARISON_FINDINGS.SOURCE_SUMMARY, blankToNull(finding.sourceSummary()))
                    .set(TEST_COMPARISON_FINDINGS.TARGET_SUMMARY, blankToNull(finding.targetSummary()))
                    .set(TEST_COMPARISON_FINDINGS.RECOMMENDATION, blankToNull(finding.recommendation()))
                    .set(TEST_COMPARISON_FINDINGS.RAW_PAYLOAD, toJsonb(finding.rawPayload()))
                    .execute();
        }
    }

    public long countFindings(UUID comparisonRunId, TestComparisonFindingListRequest request) {
        return dsl.selectCount()
                .from(TEST_COMPARISON_FINDINGS)
                .where(findingFilter(comparisonRunId, request))
                .fetchOne(0, long.class);
    }

    public List<TestComparisonFindingView> listFindings(UUID comparisonRunId, TestComparisonFindingListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(TEST_COMPARISON_FINDINGS)
                .where(findingFilter(comparisonRunId, request))
                .orderBy(findingOrderBy(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::findingView);
    }

    private TestComparisonRunView view(TestComparisonRunsRecord record) {
        return TestComparisonRunView.from(record,
                jsonbToMap(record.getInputSummary()),
                jsonbToMap(record.getSourceTestStats()),
                jsonbToMap(record.getTargetTestStats()));
    }

    private TestComparisonFindingView findingView(TestComparisonFindingsRecord record) {
        return TestComparisonFindingView.from(record, jsonbToMap(record.getRawPayload()));
    }

    private Condition filter(UUID projectId, TestComparisonListRequest request) {
        Condition condition = TEST_COMPARISON_RUNS.PROJECT_ID.eq(projectId);
        if (request.status() != null) {
            condition = condition.and(TEST_COMPARISON_RUNS.STATUS.eq(request.status().name()));
        }
        if (request.riskLevel() != null) {
            condition = condition.and(TEST_COMPARISON_RUNS.RISK_LEVEL.eq(request.riskLevel().name()));
        }
        if (request.testBatchId() != null) {
            condition = condition.and(TEST_COMPARISON_RUNS.TEST_BATCH_ID.eq(request.testBatchId()));
        }
        if (request.sourceTestRunId() != null) {
            condition = condition.and(TEST_COMPARISON_RUNS.SOURCE_TEST_RUN_ID.eq(request.sourceTestRunId()));
        }
        if (request.targetTestRunId() != null) {
            condition = condition.and(TEST_COMPARISON_RUNS.TARGET_TEST_RUN_ID.eq(request.targetTestRunId()));
        }
        return condition;
    }

    private Condition findingFilter(UUID comparisonRunId, TestComparisonFindingListRequest request) {
        Condition condition = TEST_COMPARISON_FINDINGS.COMPARISON_RUN_ID.eq(comparisonRunId);
        if (request.severity() != null) {
            condition = condition.and(TEST_COMPARISON_FINDINGS.SEVERITY.eq(request.severity().name()));
        }
        if (request.differenceType() != null && !request.differenceType().isBlank()) {
            condition = condition.and(TEST_COMPARISON_FINDINGS.DIFFERENCE_TYPE.eq(request.differenceType().trim()));
        }
        return condition;
    }

    private OrderField<?>[] orderBy(TestComparisonListRequest request) {
        boolean asc = "asc".equalsIgnoreCase(request.sortDirection());
        Field<?> field = switch (request.sortBy() == null ? "" : request.sortBy()) {
            case "status" -> TEST_COMPARISON_RUNS.STATUS;
            case "riskLevel" -> TEST_COMPARISON_RUNS.RISK_LEVEL;
            case "finishedAt" -> TEST_COMPARISON_RUNS.FINISHED_AT;
            case "updatedAt" -> TEST_COMPARISON_RUNS.UPDATED_AT;
            default -> TEST_COMPARISON_RUNS.CREATED_AT;
        };
        return new OrderField<?>[] { asc ? field.asc().nullsLast() : field.desc().nullsLast(), TEST_COMPARISON_RUNS.ID.desc() };
    }

    private OrderField<?>[] findingOrderBy(TestComparisonFindingListRequest request) {
        boolean asc = "asc".equalsIgnoreCase(request.sortDirection());
        Field<?> field = switch (request.sortBy() == null ? "" : request.sortBy()) {
            case "severity" -> TEST_COMPARISON_FINDINGS.SEVERITY;
            case "differenceType" -> TEST_COMPARISON_FINDINGS.DIFFERENCE_TYPE;
            case "createdAt" -> TEST_COMPARISON_FINDINGS.CREATED_AT;
            default -> TEST_COMPARISON_FINDINGS.SEQUENCE_NO;
        };
        return new OrderField<?>[] { asc ? field.asc().nullsLast() : field.desc().nullsLast(), TEST_COMPARISON_FINDINGS.ID.asc() };
    }

    private JSONB toJsonb(Map<String, ?> value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            return JSONB.valueOf("{}");
        }
    }

    private Map<String, Object> jsonbToMap(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(value.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private <T> T defaultValue(T value, T fallback) {
        return value == null ? fallback : value;
    }
}
