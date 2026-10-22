package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Record;
import org.jooq.SortField;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class DependencyAutoFixRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private static final Table<?> RUNS = DSL.table(DSL.name("dependency_auto_fix_runs"));
    private static final Field<UUID> RUN_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "id"), UUID.class);
    private static final Field<UUID> RUN_PROJECT_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "project_id"), UUID.class);
    private static final Field<UUID> RUN_TASK_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "task_id"), UUID.class);
    private static final Field<UUID> RUN_ANALYSIS_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "dependency_analysis_run_id"), UUID.class);
    private static final Field<UUID> RUN_SOURCE_REVISION_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "source_revision_id"), UUID.class);
    private static final Field<UUID> RUN_TARGET_ENVIRONMENT_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "target_environment_id"), UUID.class);
    private static final Field<Long> RUN_ENV_VERSION = DSL.field(DSL.name("dependency_auto_fix_runs", "environment_config_version"), Long.class);
    private static final Field<UUID> RUN_RERUN_ANALYSIS_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "rerun_dependency_analysis_run_id"), UUID.class);
    private static final Field<UUID> RUN_RERUN_TASK_ID = DSL.field(DSL.name("dependency_auto_fix_runs", "rerun_dependency_analysis_task_id"), UUID.class);
    private static final Field<String> RUN_STATUS = DSL.field(DSL.name("dependency_auto_fix_runs", "status"), String.class);
    private static final Field<Integer> RUN_SELECTED_COUNT = DSL.field(DSL.name("dependency_auto_fix_runs", "selected_count"), Integer.class);
    private static final Field<Integer> RUN_SUCCEEDED_COUNT = DSL.field(DSL.name("dependency_auto_fix_runs", "succeeded_count"), Integer.class);
    private static final Field<Integer> RUN_FAILED_COUNT = DSL.field(DSL.name("dependency_auto_fix_runs", "failed_count"), Integer.class);
    private static final Field<Integer> RUN_SKIPPED_COUNT = DSL.field(DSL.name("dependency_auto_fix_runs", "skipped_count"), Integer.class);
    private static final Field<JSONB> RUN_SUMMARY = DSL.field(DSL.name("dependency_auto_fix_runs", "summary"), JSONB.class);
    private static final Field<String> RUN_ERROR_SUMMARY = DSL.field(DSL.name("dependency_auto_fix_runs", "error_summary"), String.class);
    private static final Field<OffsetDateTime> RUN_STARTED_AT = DSL.field(DSL.name("dependency_auto_fix_runs", "started_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_FINISHED_AT = DSL.field(DSL.name("dependency_auto_fix_runs", "finished_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_CREATED_AT = DSL.field(DSL.name("dependency_auto_fix_runs", "created_at"), OffsetDateTime.class);

    private static final Table<?> ITEMS = DSL.table(DSL.name("dependency_auto_fix_items"));
    private static final Field<UUID> ITEM_ID = DSL.field(DSL.name("dependency_auto_fix_items", "id"), UUID.class);
    private static final Field<UUID> ITEM_RUN_ID = DSL.field(DSL.name("dependency_auto_fix_items", "dependency_auto_fix_run_id"), UUID.class);
    private static final Field<UUID> ITEM_RESULT_ID = DSL.field(DSL.name("dependency_auto_fix_items", "dependency_result_item_id"), UUID.class);
    private static final Field<UUID> ITEM_PROJECT_ID = DSL.field(DSL.name("dependency_auto_fix_items", "project_id"), UUID.class);
    private static final Field<UUID> ITEM_SOURCE_REVISION_ID = DSL.field(DSL.name("dependency_auto_fix_items", "source_revision_id"), UUID.class);
    private static final Field<String> ITEM_RISK = DSL.field(DSL.name("dependency_auto_fix_items", "risk_level"), String.class);
    private static final Field<String> ITEM_TARGET_STATUS = DSL.field(DSL.name("dependency_auto_fix_items", "target_match_status"), String.class);
    private static final Field<String> ITEM_SOURCE_PROVIDER_PACKAGE = DSL.field(DSL.name("dependency_auto_fix_items", "source_provider_package"), String.class);
    private static final Field<String> ITEM_SOURCE_PROVIDER_VERSION = DSL.field(DSL.name("dependency_auto_fix_items", "source_provider_version"), String.class);
    private static final Field<String> ITEM_TARGET_PROVIDER_PACKAGE = DSL.field(DSL.name("dependency_auto_fix_items", "target_provider_package"), String.class);
    private static final Field<String> ITEM_TARGET_PROVIDER_VERSION = DSL.field(DSL.name("dependency_auto_fix_items", "target_provider_version"), String.class);
    private static final Field<String> ITEM_INSTALL_PACKAGE = DSL.field(DSL.name("dependency_auto_fix_items", "install_package_name"), String.class);
    private static final Field<String> ITEM_INSTALL_VERSION = DSL.field(DSL.name("dependency_auto_fix_items", "install_version_constraint"), String.class);
    private static final Field<Boolean> ITEM_DEFAULT_SELECTED = DSL.field(DSL.name("dependency_auto_fix_items", "default_selected"), Boolean.class);
    private static final Field<String> ITEM_STATUS = DSL.field(DSL.name("dependency_auto_fix_items", "status"), String.class);
    private static final Field<Integer> ITEM_EXIT_CODE = DSL.field(DSL.name("dependency_auto_fix_items", "exit_code"), Integer.class);
    private static final Field<String> ITEM_ERROR_SUMMARY = DSL.field(DSL.name("dependency_auto_fix_items", "error_summary"), String.class);
    private static final Field<JSONB> ITEM_EVIDENCE = DSL.field(DSL.name("dependency_auto_fix_items", "evidence"), JSONB.class);
    private static final Field<OffsetDateTime> ITEM_STARTED_AT = DSL.field(DSL.name("dependency_auto_fix_items", "started_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> ITEM_FINISHED_AT = DSL.field(DSL.name("dependency_auto_fix_items", "finished_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> ITEM_CREATED_AT = DSL.field(DSL.name("dependency_auto_fix_items", "created_at"), OffsetDateTime.class);

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public DependencyAutoFixRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public DependencyAutoFixRunView createRun(UUID id, UUID projectId, UUID taskId, UUID analysisId,
                                              UUID sourceRevisionId, UUID targetEnvironmentId,
                                              long environmentConfigVersion, int selectedCount) {
        Record record = dsl.insertInto(RUNS)
                .columns(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_ANALYSIS_ID, RUN_SOURCE_REVISION_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENV_VERSION, RUN_STATUS, RUN_SELECTED_COUNT)
                .values(id, projectId, taskId, analysisId, sourceRevisionId, targetEnvironmentId,
                        environmentConfigVersion, DependencyAutoFixRunStatus.PENDING.name(), selectedCount)
                .returningResult(runFields())
                .fetchOne();
        return mapRun(record);
    }

    public void createItems(UUID runId, List<DependencyAutoFixCandidateResponse> candidates, UUID projectId, UUID sourceRevisionId) {
        for (DependencyAutoFixCandidateResponse candidate : candidates) {
            dsl.insertInto(ITEMS)
                    .columns(ITEM_RUN_ID, ITEM_RESULT_ID, ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID, ITEM_RISK,
                            ITEM_TARGET_STATUS, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                            ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION, ITEM_INSTALL_PACKAGE,
                            ITEM_INSTALL_VERSION, ITEM_DEFAULT_SELECTED, ITEM_STATUS, ITEM_EVIDENCE)
                    .values(runId, candidate.resultItemId(), projectId, sourceRevisionId, candidate.riskLevel().name(),
                            candidate.targetMatchStatus().name(), blankToNull(candidate.sourceProviderPackage()),
                            blankToNull(candidate.sourceProviderVersion()), blankToNull(candidate.targetProviderPackage()),
                            blankToNull(candidate.targetProviderVersion()), candidate.installPackageName(),
                            blankToNull(candidate.installVersionConstraint()), candidate.defaultSelected(),
                            DependencyAutoFixItemStatus.PENDING.name(), toJsonb(Map.of("candidateReason", candidate.reason())))
                    .execute();
        }
    }

    public Optional<DependencyAutoFixRunView> findRun(UUID id) {
        return dsl.select(runFields()).from(RUNS).where(RUN_ID.eq(id)).fetchOptional(this::mapRun);
    }

    public long countRuns(UUID projectId, DependencyAutoFixRunListRequest request) {
        return dsl.selectCount().from(RUNS).where(runFilter(projectId, request)).fetchOne(0, long.class);
    }

    public List<DependencyAutoFixRunView> listRuns(UUID projectId, DependencyAutoFixRunListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.select(runFields())
                .from(RUNS)
                .where(runFilter(projectId, request))
                .orderBy(runSort(request), RUN_ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::mapRun);
    }

    public List<DependencyAutoFixItemView> listPendingItems(UUID runId) {
        return dsl.select(itemFields()).from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.PENDING.name())))
                .orderBy(ITEM_CREATED_AT.asc(), ITEM_ID.asc())
                .fetch(this::mapItem);
    }

    public long countItems(UUID runId, DependencyAutoFixItemListRequest request) {
        return dsl.selectCount().from(ITEMS).where(itemFilter(runId, request)).fetchOne(0, long.class);
    }

    public List<DependencyAutoFixItemView> listItems(UUID runId, DependencyAutoFixItemListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.select(itemFields())
                .from(ITEMS)
                .where(itemFilter(runId, request))
                .orderBy(itemSort(request), ITEM_ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::mapItem);
    }

    public Map<String, Object> summaryCounts(UUID runId) {
        int total = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId))
                .fetchOne(0, int.class);
        int succeeded = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.SUCCEEDED.name())))
                .fetchOne(0, int.class);
        int alreadySatisfied = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED.name())))
                .fetchOne(0, int.class);
        int skippedUnavailable = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE.name())))
                .fetchOne(0, int.class);
        int failed = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.FAILED.name())))
                .fetchOne(0, int.class);
        return Map.of(
                "total", total,
                "succeeded", succeeded,
                "alreadySatisfied", alreadySatisfied,
                "skippedUnavailable", skippedUnavailable,
                "failed", failed
        );
    }

    public void markRunRunning(UUID runId) {
        dsl.update(RUNS)
                .set(RUN_STATUS, DependencyAutoFixRunStatus.RUNNING.name())
                .set(RUN_STARTED_AT, OffsetDateTime.now())
                .where(RUN_ID.eq(runId))
                .execute();
    }

    public void markItemRunning(UUID itemId) {
        dsl.update(ITEMS)
                .set(ITEM_STATUS, DependencyAutoFixItemStatus.RUNNING.name())
                .set(ITEM_STARTED_AT, OffsetDateTime.now())
                .where(ITEM_ID.eq(itemId))
                .execute();
    }

    public void markItemFinished(UUID itemId, DependencyAutoFixItemStatus status, Integer exitCode,
                                 String errorSummary, Map<String, ?> evidence) {
        dsl.update(ITEMS)
                .set(ITEM_STATUS, status.name())
                .set(ITEM_EXIT_CODE, exitCode)
                .set(ITEM_ERROR_SUMMARY, blankToNull(errorSummary))
                .set(ITEM_EVIDENCE, toJsonb(evidence == null ? Map.of() : evidence))
                .set(ITEM_FINISHED_AT, OffsetDateTime.now())
                .where(ITEM_ID.eq(itemId))
                .execute();
    }

    public void markRunFinished(UUID runId, DependencyAutoFixRunStatus status, Map<String, ?> summary, String errorSummary) {
        Map<String, Integer> counts = counts(runId);
        dsl.update(RUNS)
                .set(RUN_STATUS, status.name())
                .set(RUN_SUCCEEDED_COUNT, counts.getOrDefault("succeeded", 0))
                .set(RUN_FAILED_COUNT, counts.getOrDefault("failed", 0))
                .set(RUN_SKIPPED_COUNT, counts.getOrDefault("skipped", 0))
                .set(RUN_SUMMARY, toJsonb(summary == null ? Map.of() : summary))
                .set(RUN_ERROR_SUMMARY, blankToNull(errorSummary))
                .set(RUN_FINISHED_AT, OffsetDateTime.now())
                .where(RUN_ID.eq(runId))
                .execute();
    }

    public void linkRerun(UUID runId, UUID analysisRunId, UUID taskId, Map<String, ?> summary,
                          DependencyAutoFixRunStatus status) {
        Map<String, Integer> counts = counts(runId);
        dsl.update(RUNS)
                .set(RUN_RERUN_ANALYSIS_ID, analysisRunId)
                .set(RUN_RERUN_TASK_ID, taskId)
                .set(RUN_STATUS, status.name())
                .set(RUN_SUCCEEDED_COUNT, counts.getOrDefault("succeeded", 0))
                .set(RUN_FAILED_COUNT, counts.getOrDefault("failed", 0))
                .set(RUN_SKIPPED_COUNT, counts.getOrDefault("skipped", 0))
                .set(RUN_SUMMARY, toJsonb(summary == null ? Map.of() : summary))
                .set(RUN_FINISHED_AT, OffsetDateTime.now())
                .where(RUN_ID.eq(runId))
                .execute();
    }

    public void cancelPendingItems(UUID runId) {
        dsl.update(ITEMS)
                .set(ITEM_STATUS, DependencyAutoFixItemStatus.CANCELLED.name())
                .set(ITEM_FINISHED_AT, OffsetDateTime.now())
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.in(
                        DependencyAutoFixItemStatus.PENDING.name(),
                        DependencyAutoFixItemStatus.RUNNING.name()
                )))
                .execute();
    }

    private Map<String, Integer> counts(UUID runId) {
        int succeeded = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.SUCCEEDED.name())))
                .fetchOne(0, int.class);
        int failed = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.eq(DependencyAutoFixItemStatus.FAILED.name())))
                .fetchOne(0, int.class);
        int skipped = dsl.selectCount().from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId).and(ITEM_STATUS.in(
                        DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED.name(),
                        DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE.name()
                )))
                .fetchOne(0, int.class);
        return Map.of("succeeded", succeeded, "failed", failed, "skipped", skipped);
    }

    private Condition runFilter(UUID projectId, DependencyAutoFixRunListRequest request) {
        Condition condition = RUN_PROJECT_ID.eq(projectId);
        if (request.sourceRevisionId() != null) {
            condition = condition.and(RUN_SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        if (request.environmentConfigVersion() != null) {
            condition = condition.and(RUN_ENV_VERSION.eq(request.environmentConfigVersion()));
        }
        if (request.status() != null) {
            condition = condition.and(RUN_STATUS.eq(request.status().name()));
        }
        return condition;
    }

    private Condition itemFilter(UUID runId, DependencyAutoFixItemListRequest request) {
        Condition condition = ITEM_RUN_ID.eq(runId);
        if (request.status() != null) {
            condition = condition.and(ITEM_STATUS.eq(request.status().name()));
        }
        if (request.riskLevel() != null) {
            condition = condition.and(ITEM_RISK.eq(request.riskLevel().name()));
        }
        if (request.targetMatchStatus() != null) {
            condition = condition.and(ITEM_TARGET_STATUS.eq(request.targetMatchStatus().name()));
        }
        if (request.installPackageName() != null && !request.installPackageName().isBlank()) {
            condition = condition.and(ITEM_INSTALL_PACKAGE.eq(request.installPackageName().trim()));
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String text = "%" + request.keyword().trim().toLowerCase() + "%";
            condition = condition.and(DSL.lower(ITEM_INSTALL_PACKAGE).like(text)
                    .or(DSL.lower(ITEM_ERROR_SUMMARY).like(text)));
        }
        return condition;
    }

    private SortField<?> runSort(DependencyAutoFixRunListRequest request) {
        Field<?> field = switch (normalize(request.sortBy())) {
            case "startedAt" -> RUN_STARTED_AT;
            case "finishedAt" -> RUN_FINISHED_AT;
            case "status" -> RUN_STATUS;
            default -> RUN_CREATED_AT;
        };
        return "asc".equalsIgnoreCase(request.sortDirection()) ? field.asc() : field.desc();
    }

    private SortField<?> itemSort(DependencyAutoFixItemListRequest request) {
        Field<?> field = switch (normalize(request.sortBy())) {
            case "status" -> ITEM_STATUS;
            case "riskLevel" -> ITEM_RISK;
            case "targetMatchStatus" -> ITEM_TARGET_STATUS;
            case "installPackageName" -> ITEM_INSTALL_PACKAGE;
            case "finishedAt" -> ITEM_FINISHED_AT;
            default -> ITEM_CREATED_AT;
        };
        return "asc".equalsIgnoreCase(request.sortDirection()) ? field.asc() : field.desc();
    }

    private Field<?>[] runFields() {
        return new Field<?>[]{RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_ANALYSIS_ID, RUN_SOURCE_REVISION_ID,
                RUN_TARGET_ENVIRONMENT_ID, RUN_ENV_VERSION, RUN_RERUN_ANALYSIS_ID, RUN_RERUN_TASK_ID, RUN_STATUS,
                RUN_SELECTED_COUNT, RUN_SUCCEEDED_COUNT, RUN_FAILED_COUNT, RUN_SKIPPED_COUNT, RUN_SUMMARY,
                RUN_ERROR_SUMMARY, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT};
    }

    private Field<?>[] itemFields() {
        return new Field<?>[]{ITEM_ID, ITEM_RUN_ID, ITEM_RESULT_ID, ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID,
                ITEM_RISK, ITEM_TARGET_STATUS, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION, ITEM_INSTALL_PACKAGE,
                ITEM_INSTALL_VERSION, ITEM_DEFAULT_SELECTED, ITEM_STATUS, ITEM_EXIT_CODE, ITEM_ERROR_SUMMARY,
                ITEM_EVIDENCE, ITEM_STARTED_AT, ITEM_FINISHED_AT, ITEM_CREATED_AT};
    }

    private DependencyAutoFixRunView mapRun(Record record) {
        return new DependencyAutoFixRunView(
                record.get(RUN_ID),
                record.get(RUN_PROJECT_ID),
                record.get(RUN_TASK_ID),
                record.get(RUN_ANALYSIS_ID),
                record.get(RUN_SOURCE_REVISION_ID),
                record.get(RUN_TARGET_ENVIRONMENT_ID),
                record.get(RUN_ENV_VERSION),
                record.get(RUN_RERUN_ANALYSIS_ID),
                record.get(RUN_RERUN_TASK_ID),
                DependencyAutoFixRunStatus.valueOf(record.get(RUN_STATUS)),
                safeInt(record.get(RUN_SELECTED_COUNT)),
                safeInt(record.get(RUN_SUCCEEDED_COUNT)),
                safeInt(record.get(RUN_FAILED_COUNT)),
                safeInt(record.get(RUN_SKIPPED_COUNT)),
                jsonbToMap(record.get(RUN_SUMMARY)),
                record.get(RUN_ERROR_SUMMARY),
                record.get(RUN_STARTED_AT),
                record.get(RUN_FINISHED_AT),
                record.get(RUN_CREATED_AT)
        );
    }

    private DependencyAutoFixItemView mapItem(Record record) {
        return new DependencyAutoFixItemView(
                record.get(ITEM_ID),
                record.get(ITEM_RUN_ID),
                record.get(ITEM_RESULT_ID),
                record.get(ITEM_PROJECT_ID),
                record.get(ITEM_SOURCE_REVISION_ID),
                DependencyRiskLevel.valueOf(record.get(ITEM_RISK)),
                DependencyTargetMatchStatus.valueOf(record.get(ITEM_TARGET_STATUS)),
                record.get(ITEM_SOURCE_PROVIDER_PACKAGE),
                record.get(ITEM_SOURCE_PROVIDER_VERSION),
                record.get(ITEM_TARGET_PROVIDER_PACKAGE),
                record.get(ITEM_TARGET_PROVIDER_VERSION),
                record.get(ITEM_INSTALL_PACKAGE),
                record.get(ITEM_INSTALL_VERSION),
                Boolean.TRUE.equals(record.get(ITEM_DEFAULT_SELECTED)),
                DependencyAutoFixItemStatus.valueOf(record.get(ITEM_STATUS)),
                record.get(ITEM_EXIT_CODE),
                record.get(ITEM_ERROR_SUMMARY),
                jsonbToMap(record.get(ITEM_EVIDENCE)),
                record.get(ITEM_STARTED_AT),
                record.get(ITEM_FINISHED_AT),
                record.get(ITEM_CREATED_AT)
        );
    }

    private JSONB toJsonb(Object value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            return JSONB.valueOf("{}");
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

    private int safeInt(Integer value) {
        return value == null ? 0 : value;
    }

    private String normalize(String value) {
        return value == null || value.isBlank() ? "" : value.trim();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
