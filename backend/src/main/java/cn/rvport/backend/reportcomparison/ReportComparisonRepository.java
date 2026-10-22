package cn.rvport.backend.reportcomparison;

import static cn.rvport.backend.jooq.tables.ReportComparisonDiffItems.REPORT_COMPARISON_DIFF_ITEMS;
import static cn.rvport.backend.jooq.tables.ReportComparisonRuns.REPORT_COMPARISON_RUNS;
import static cn.rvport.backend.jooq.tables.ReportInputs.REPORT_INPUTS;
import static cn.rvport.backend.jooq.tables.Reports.REPORTS;

import cn.rvport.backend.report.ReportInputView;
import cn.rvport.backend.report.ReportType;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.SortField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ReportComparisonRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ReportComparisonRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public Optional<ReportView> latestComparableBase(ReportView targetReport) {
        Condition condition = REPORTS.PROJECT_ID.eq(targetReport.projectId())
                .and(REPORTS.REPORT_TYPE.eq(targetReport.reportType().name()))
                .and(REPORTS.STATUS.eq(TaskStatus.SUCCEEDED.name()))
                .and(REPORTS.ID.ne(targetReport.id()));
        if (targetReport.generatedAt() != null) {
            condition = condition.and(REPORTS.GENERATED_AT.le(targetReport.generatedAt()));
        } else {
            condition = condition.and(REPORTS.CREATED_AT.lt(targetReport.createdAt()));
        }
        return dsl.selectFrom(REPORTS)
                .where(condition)
                .orderBy(REPORTS.GENERATED_AT.desc().nullsLast(), REPORTS.CREATED_AT.desc(), REPORTS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportComparisonRunView> latestForTargetReport(UUID targetReportId) {
        return dsl.selectFrom(REPORT_COMPARISON_RUNS)
                .where(REPORT_COMPARISON_RUNS.TARGET_REPORT_ID.eq(targetReportId))
                .orderBy(REPORT_COMPARISON_RUNS.CREATED_AT.desc(), REPORT_COMPARISON_RUNS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportComparisonRunView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportComparisonRunView> findReusable(UUID projectId, UUID baseReportId, UUID targetReportId) {
        return dsl.selectFrom(REPORT_COMPARISON_RUNS)
                .where(REPORT_COMPARISON_RUNS.PROJECT_ID.eq(projectId)
                        .and(REPORT_COMPARISON_RUNS.BASE_REPORT_ID.eq(baseReportId))
                        .and(REPORT_COMPARISON_RUNS.TARGET_REPORT_ID.eq(targetReportId))
                        .and(REPORT_COMPARISON_RUNS.STATUS.in(
                                TaskStatus.PENDING.name(),
                                TaskStatus.QUEUED.name(),
                                TaskStatus.RUNNING.name(),
                                TaskStatus.SUCCEEDED.name()
                        )))
                .orderBy(REPORT_COMPARISON_RUNS.CREATED_AT.desc(), REPORT_COMPARISON_RUNS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportComparisonRunView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportComparisonRunView> findRun(UUID comparisonRunId) {
        return dsl.selectFrom(REPORT_COMPARISON_RUNS)
                .where(REPORT_COMPARISON_RUNS.ID.eq(comparisonRunId))
                .fetchOptional(record -> ReportComparisonRunView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportComparisonRunView> findByTaskId(UUID taskId) {
        return dsl.selectFrom(REPORT_COMPARISON_RUNS)
                .where(REPORT_COMPARISON_RUNS.TASK_ID.eq(taskId))
                .fetchOptional(record -> ReportComparisonRunView.from(record, jsonbToMap(record.getSummary())));
    }

    public ReportComparisonRunView createRun(
            UUID id,
            UUID projectId,
            UUID taskId,
            UUID baseReportId,
            UUID targetReportId,
            TaskStatus status
    ) {
        var record = dsl.insertInto(REPORT_COMPARISON_RUNS)
                .set(REPORT_COMPARISON_RUNS.ID, id)
                .set(REPORT_COMPARISON_RUNS.PROJECT_ID, projectId)
                .set(REPORT_COMPARISON_RUNS.TASK_ID, taskId)
                .set(REPORT_COMPARISON_RUNS.BASE_REPORT_ID, baseReportId)
                .set(REPORT_COMPARISON_RUNS.TARGET_REPORT_ID, targetReportId)
                .set(REPORT_COMPARISON_RUNS.STATUS, status.name())
                .set(REPORT_COMPARISON_RUNS.SUMMARY, JSONB.valueOf("{}"))
                .returning()
                .fetchOne();
        return ReportComparisonRunView.from(record, Map.of());
    }

    public void markRunning(UUID comparisonRunId) {
        dsl.update(REPORT_COMPARISON_RUNS)
                .set(REPORT_COMPARISON_RUNS.STATUS, TaskStatus.RUNNING.name())
                .set(REPORT_COMPARISON_RUNS.STARTED_AT, OffsetDateTime.now())
                .set(REPORT_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(REPORT_COMPARISON_RUNS.ID.eq(comparisonRunId))
                .execute();
    }

    public void markSucceeded(UUID comparisonRunId, Map<String, Object> summary) {
        dsl.update(REPORT_COMPARISON_RUNS)
                .set(REPORT_COMPARISON_RUNS.STATUS, TaskStatus.SUCCEEDED.name())
                .set(REPORT_COMPARISON_RUNS.SUMMARY, jsonb(summary))
                .set(REPORT_COMPARISON_RUNS.ERROR_CODE, (String) null)
                .set(REPORT_COMPARISON_RUNS.ERROR_MESSAGE, (String) null)
                .set(REPORT_COMPARISON_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(REPORT_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(REPORT_COMPARISON_RUNS.ID.eq(comparisonRunId))
                .execute();
    }

    public void markFailed(UUID comparisonRunId, String errorCode, String errorMessage, Map<String, Object> summary) {
        dsl.update(REPORT_COMPARISON_RUNS)
                .set(REPORT_COMPARISON_RUNS.STATUS, TaskStatus.FAILED.name())
                .set(REPORT_COMPARISON_RUNS.SUMMARY, jsonb(summary))
                .set(REPORT_COMPARISON_RUNS.ERROR_CODE, errorCode)
                .set(REPORT_COMPARISON_RUNS.ERROR_MESSAGE, errorMessage)
                .set(REPORT_COMPARISON_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(REPORT_COMPARISON_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(REPORT_COMPARISON_RUNS.ID.eq(comparisonRunId))
                .execute();
    }

    public List<ReportInputView> listAllInputs(UUID reportId) {
        return dsl.selectFrom(REPORT_INPUTS)
                .where(REPORT_INPUTS.REPORT_ID.eq(reportId))
                .orderBy(REPORT_INPUTS.CREATED_AT.asc(), REPORT_INPUTS.ID.asc())
                .fetch(record -> ReportInputView.from(record, jsonbToMap(record.getInputSnapshot())));
    }

    public boolean hasInputs(UUID reportId) {
        return dsl.fetchExists(REPORT_INPUTS, REPORT_INPUTS.REPORT_ID.eq(reportId));
    }

    public ReportComparisonDiffSummaryResponse diffSummary(UUID projectId, UUID comparisonRunId) {
        long total = dsl.selectCount()
                .from(REPORT_COMPARISON_DIFF_ITEMS)
                .where(REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID.eq(projectId)
                        .and(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID.eq(comparisonRunId)))
                .fetchOne(0, long.class);
        return new ReportComparisonDiffSummaryResponse(
                total,
                grouped(REPORT_COMPARISON_DIFF_ITEMS.DIFF_STATUS, projectId, comparisonRunId),
                grouped(REPORT_COMPARISON_DIFF_ITEMS.SOURCE_TYPE, projectId, comparisonRunId),
                grouped(REPORT_COMPARISON_DIFF_ITEMS.SEVERITY, projectId, comparisonRunId),
                grouped(REPORT_COMPARISON_DIFF_ITEMS.MATCH_CONFIDENCE, projectId, comparisonRunId)
        );
    }

    public long countDiffItems(UUID projectId, UUID comparisonRunId, ReportComparisonDiffItemListRequest request) {
        return dsl.selectCount()
                .from(REPORT_COMPARISON_DIFF_ITEMS)
                .where(diffFilter(projectId, comparisonRunId, request))
                .fetchOne(0, long.class);
    }

    public List<ReportComparisonDiffItemView> listDiffItems(UUID projectId, UUID comparisonRunId, ReportComparisonDiffItemListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(REPORT_COMPARISON_DIFF_ITEMS)
                .where(diffFilter(projectId, comparisonRunId, request))
                .orderBy(diffSort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(record -> ReportComparisonDiffItemView.from(
                        record,
                        jsonbToMap(record.getOldSnapshot()),
                        jsonbToMap(record.getNewSnapshot())
                ));
    }

    public Optional<ReportComparisonDiffItemView> findDiffItem(UUID projectId, UUID comparisonRunId, UUID diffItemId) {
        return dsl.selectFrom(REPORT_COMPARISON_DIFF_ITEMS)
                .where(REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID.eq(projectId)
                        .and(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID.eq(comparisonRunId))
                        .and(REPORT_COMPARISON_DIFF_ITEMS.ID.eq(diffItemId)))
                .fetchOptional(record -> ReportComparisonDiffItemView.from(
                        record,
                        jsonbToMap(record.getOldSnapshot()),
                        jsonbToMap(record.getNewSnapshot())
                ));
    }

    public void replaceDiffItems(UUID projectId, UUID comparisonRunId, List<DiffItemCreateCommand> items) {
        dsl.deleteFrom(REPORT_COMPARISON_DIFF_ITEMS)
                .where(REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID.eq(projectId)
                        .and(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID.eq(comparisonRunId)))
                .execute();
        for (DiffItemCreateCommand item : items) {
            dsl.insertInto(REPORT_COMPARISON_DIFF_ITEMS)
                    .set(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID, comparisonRunId)
                    .set(REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID, projectId)
                    .set(REPORT_COMPARISON_DIFF_ITEMS.SOURCE_TYPE, item.sourceType())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.OLD_SOURCE_ID, item.oldSourceId())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.NEW_SOURCE_ID, item.newSourceId())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.DIFF_STATUS, item.diffStatus())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.SEVERITY, item.severity())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.TITLE, item.title())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.LOCATION_LABEL, item.locationLabel())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.RECOMMENDATION, item.recommendation())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.CONFIRMATION_STATUS, item.confirmationStatus())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.FINGERPRINT, item.fingerprint())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.MATCH_CONFIDENCE, item.matchConfidence())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.MATCH_REASON, item.matchReason())
                    .set(REPORT_COMPARISON_DIFF_ITEMS.OLD_SNAPSHOT, jsonb(item.oldSnapshot()))
                    .set(REPORT_COMPARISON_DIFF_ITEMS.NEW_SNAPSHOT, jsonb(item.newSnapshot()))
                    .execute();
        }
    }

    private Condition diffFilter(UUID projectId, UUID comparisonRunId, ReportComparisonDiffItemListRequest request) {
        Condition condition = REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID.eq(projectId)
                .and(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID.eq(comparisonRunId));
        if (request.diffStatus() != null && !request.diffStatus().isBlank()) {
            condition = condition.and(REPORT_COMPARISON_DIFF_ITEMS.DIFF_STATUS.eq(request.diffStatus().trim()));
        }
        if (request.sourceType() != null && !request.sourceType().isBlank()) {
            condition = condition.and(REPORT_COMPARISON_DIFF_ITEMS.SOURCE_TYPE.eq(request.sourceType().trim()));
        }
        if (request.severity() != null && !request.severity().isBlank()) {
            condition = condition.and(REPORT_COMPARISON_DIFF_ITEMS.SEVERITY.eq(request.severity().trim()));
        }
        if (request.matchConfidence() != null && !request.matchConfidence().isBlank()) {
            condition = condition.and(REPORT_COMPARISON_DIFF_ITEMS.MATCH_CONFIDENCE.eq(request.matchConfidence().trim()));
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String keyword = request.keyword().trim();
            condition = condition.and(REPORT_COMPARISON_DIFF_ITEMS.TITLE.containsIgnoreCase(keyword)
                    .or(REPORT_COMPARISON_DIFF_ITEMS.LOCATION_LABEL.containsIgnoreCase(keyword))
                    .or(REPORT_COMPARISON_DIFF_ITEMS.RECOMMENDATION.containsIgnoreCase(keyword)));
        }
        return condition;
    }

    private List<SortField<?>> diffSort(ReportComparisonDiffItemListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "diffStatus" -> REPORT_COMPARISON_DIFF_ITEMS.DIFF_STATUS;
            case "sourceType" -> REPORT_COMPARISON_DIFF_ITEMS.SOURCE_TYPE;
            case "severity" -> REPORT_COMPARISON_DIFF_ITEMS.SEVERITY;
            case "title" -> REPORT_COMPARISON_DIFF_ITEMS.TITLE;
            case "locationLabel" -> REPORT_COMPARISON_DIFF_ITEMS.LOCATION_LABEL;
            case "matchConfidence" -> REPORT_COMPARISON_DIFF_ITEMS.MATCH_CONFIDENCE;
            case "createdAt" -> REPORT_COMPARISON_DIFF_ITEMS.CREATED_AT;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported report comparison diff item sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(REPORT_COMPARISON_DIFF_ITEMS.DIFF_STATUS.asc(), REPORT_COMPARISON_DIFF_ITEMS.ID.asc());
        }
        return List.of("desc".equalsIgnoreCase(request.sortDirection()) ? field.desc().nullsLast() : field.asc().nullsLast(), REPORT_COMPARISON_DIFF_ITEMS.ID.asc());
    }

    private Map<String, Long> grouped(Field<String> field, UUID projectId, UUID comparisonRunId) {
        Map<String, Long> values = new LinkedHashMap<>();
        dsl.select(field, DSL.count())
                .from(REPORT_COMPARISON_DIFF_ITEMS)
                .where(REPORT_COMPARISON_DIFF_ITEMS.PROJECT_ID.eq(projectId)
                        .and(REPORT_COMPARISON_DIFF_ITEMS.COMPARISON_RUN_ID.eq(comparisonRunId)))
                .groupBy(field)
                .fetch()
                .forEach(record -> {
                    String key = record.value1();
                    values.put(key == null || key.isBlank() ? "UNKNOWN" : key, record.value2().longValue());
                });
        return values;
    }

    private JSONB jsonb(Map<String, Object> value) {
        return value == null ? null : JSONB.valueOf(toJson(value));
    }

    private String toJson(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value == null ? Map.of() : value);
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Unable to serialize report comparison JSON value", ex);
        }
    }

    private Map<String, Object> jsonbToMap(JSONB jsonb) {
        if (jsonb == null || jsonb.data() == null || jsonb.data().isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(jsonb.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    public record DiffItemCreateCommand(
            String sourceType,
            UUID oldSourceId,
            UUID newSourceId,
            String diffStatus,
            String severity,
            String title,
            String locationLabel,
            String recommendation,
            String confirmationStatus,
            String fingerprint,
            String matchConfidence,
            String matchReason,
            Map<String, Object> oldSnapshot,
            Map<String, Object> newSnapshot
    ) {
    }
}
