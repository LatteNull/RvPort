package cn.rvport.backend.report;

import static cn.rvport.backend.jooq.tables.MigrationInputRefs.MIGRATION_INPUT_REFS;
import static cn.rvport.backend.jooq.tables.ReportInputs.REPORT_INPUTS;
import static cn.rvport.backend.jooq.tables.Reports.REPORTS;
import static cn.rvport.backend.workflow.DomainLatestOrdering.activeFirst;

import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputRiskPolicy;
import cn.rvport.backend.task.TaskStatus;
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
import org.jooq.SortField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ReportRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ReportRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public ReportView createEvaluation(UUID reportId, UUID projectId, UUID sourceRevisionId, UUID taskId, String title, UUID generatedBy) {
        var record = dsl.insertInto(REPORTS)
                .set(REPORTS.ID, reportId)
                .set(REPORTS.PROJECT_ID, projectId)
                .set(REPORTS.SOURCE_REVISION_ID, sourceRevisionId)
                .set(REPORTS.TASK_ID, taskId)
                .set(REPORTS.REPORT_TYPE, ReportType.EVALUATION.name())
                .set(REPORTS.STATUS, TaskStatus.PENDING.name())
                .set(REPORTS.TITLE, title)
                .set(REPORTS.GENERATED_BY, generatedBy)
                .returning()
                .fetchOne();
        return ReportView.from(record, jsonbToMap(record.getSummary()));
    }

    public Optional<ReportView> findById(UUID reportId) {
        return dsl.selectFrom(REPORTS)
                .where(REPORTS.ID.eq(reportId))
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportView> findByTaskId(UUID taskId) {
        return dsl.selectFrom(REPORTS)
                .where(REPORTS.TASK_ID.eq(taskId))
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public long count(UUID projectId, ReportListRequest request) {
        return dsl.selectCount()
                .from(REPORTS)
                .where(filter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<ReportView> list(UUID projectId, ReportListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(REPORTS)
                .where(filter(projectId, request))
                .orderBy(sort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportView> latest(UUID projectId, UUID sourceRevisionId) {
        Condition condition = REPORTS.PROJECT_ID.eq(projectId);
        if (sourceRevisionId != null) {
            condition = condition.and(REPORTS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        return dsl.selectFrom(REPORTS)
                .where(condition)
                .orderBy(REPORTS.GENERATED_AT.desc().nullsLast(), REPORTS.CREATED_AT.desc(), REPORTS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportView> latestSucceeded(UUID projectId, UUID sourceRevisionId) {
        Condition condition = REPORTS.PROJECT_ID.eq(projectId)
                .and(REPORTS.REPORT_TYPE.eq(ReportType.EVALUATION.name()))
                .and(REPORTS.STATUS.eq(TaskStatus.SUCCEEDED.name()));
        if (sourceRevisionId != null) {
            condition = condition.and(REPORTS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        return dsl.selectFrom(REPORTS)
                .where(condition)
                .orderBy(activeFirst(REPORTS.STATUS), REPORTS.CREATED_AT.desc(), REPORTS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<ReportView> latestEvaluation(UUID projectId, UUID sourceRevisionId) {
        Condition condition = REPORTS.PROJECT_ID.eq(projectId)
                .and(REPORTS.REPORT_TYPE.eq(ReportType.EVALUATION.name()));
        if (sourceRevisionId != null) {
            condition = condition.and(REPORTS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        return dsl.selectFrom(REPORTS)
                .where(condition)
                .orderBy(activeFirst(REPORTS.STATUS), REPORTS.CREATED_AT.desc(), REPORTS.ID.desc())
                .limit(1)
                .fetchOptional(record -> ReportView.from(record, jsonbToMap(record.getSummary())));
    }

    public ReportView updateStatus(UUID reportId, TaskStatus status, Map<String, ?> summary) {
        var update = dsl.update(REPORTS)
                .set(REPORTS.STATUS, status.name());
        if (summary != null) {
            update = update.set(REPORTS.SUMMARY, toJsonb(summary));
        }
        var record = update.where(REPORTS.ID.eq(reportId))
                .returning()
                .fetchOne();
        return record == null ? null : ReportView.from(record, jsonbToMap(record.getSummary()));
    }

    public ReportView markSucceeded(UUID reportId, Map<String, ?> summary, String riskLevel) {
        var record = dsl.update(REPORTS)
                .set(REPORTS.STATUS, TaskStatus.SUCCEEDED.name())
                .set(REPORTS.SUMMARY, toJsonb(summary))
                .set(REPORTS.RISK_LEVEL, riskLevel)
                .set(REPORTS.GENERATED_AT, OffsetDateTime.now())
                .where(REPORTS.ID.eq(reportId))
                .returning()
                .fetchOne();
        return record == null ? null : ReportView.from(record, jsonbToMap(record.getSummary()));
    }

    public void insertInputs(UUID reportId, List<ReportInputSnapshot> inputs) {
        for (ReportInputSnapshot input : inputs) {
            ReportInputProjection projection = input.projection();
            var insert = dsl.insertInto(REPORT_INPUTS)
                    .set(REPORT_INPUTS.REPORT_ID, reportId)
                    .set(REPORT_INPUTS.INPUT_TYPE, ReportInputType.MIGRATION_INPUT_REF.name())
                    .set(REPORT_INPUTS.INPUT_ID, input.ref().id())
                    .set(REPORT_INPUTS.INPUT_SNAPSHOT, toJsonb(input.snapshot()));
            if (projection != null) {
                insert.set(DSL.field(DSL.name("source_type"), String.class), projection.sourceType())
                        .set(DSL.field(DSL.name("risk_level"), String.class), projection.riskLevel())
                        .set(DSL.field(DSL.name("module_key"), String.class), projection.moduleKey())
                        .set(DSL.field(DSL.name("module_name"), String.class), projection.moduleName())
                        .set(DSL.field(DSL.name("module_basis"), String.class), projection.moduleBasis())
                        .set(DSL.field(DSL.name("module_confidence"), String.class), projection.moduleConfidence())
                        .set(DSL.field(DSL.name("related_module_keys"), JSONB.class), toJsonb(Map.of("items", projection.relatedModuleKeys())))
                        .set(DSL.field(DSL.name("file_key"), String.class), projection.fileKey())
                        .set(DSL.field(DSL.name("relative_path"), String.class), projection.relativePath())
                        .set(DSL.field(DSL.name("finding_type"), String.class), projection.findingType())
                        .set(DSL.field(DSL.name("line_start"), Integer.class), projection.lineStart())
                        .set(DSL.field(DSL.name("line_end"), Integer.class), projection.lineEnd())
                        .set(DSL.field(DSL.name("column_start"), Integer.class), projection.columnStart())
                        .set(DSL.field(DSL.name("column_end"), Integer.class), projection.columnEnd())
                        .set(DSL.field(DSL.name("symbol"), String.class), projection.symbol())
                        .set(DSL.field(DSL.name("source_content_hash"), String.class), projection.sourceContentHash())
                        .set(DSL.field(DSL.name("location_available"), Boolean.class), projection.locationAvailable());
            }
            insert.execute();
        }
    }

    public void replaceInputs(UUID reportId, List<ReportInputSnapshot> inputs) {
        dsl.deleteFrom(REPORT_INPUTS)
                .where(REPORT_INPUTS.REPORT_ID.eq(reportId))
                .execute();
        insertInputs(reportId, inputs);
    }

    public long countInputs(UUID reportId, ReportInputListRequest request) {
        return dsl.selectCount()
                .from(REPORT_INPUTS)
                .where(inputFilter(reportId, request))
                .fetchOne(0, long.class);
    }

    public List<ReportInputView> listInputs(UUID reportId, ReportInputListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(REPORT_INPUTS)
                .where(inputFilter(reportId, request))
                .orderBy(inputSort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(record -> ReportInputView.from(record, jsonbToMap(record.getInputSnapshot())));
    }

    public List<ReportInputView> listAllInputs(UUID reportId) {
        return dsl.selectFrom(REPORT_INPUTS)
                .where(REPORT_INPUTS.REPORT_ID.eq(reportId))
                .orderBy(REPORT_INPUTS.CREATED_AT.asc(), REPORT_INPUTS.ID.asc())
                .fetch(record -> ReportInputView.from(record, jsonbToMap(record.getInputSnapshot())));
    }

    public List<UUID> listMigrationInputIds(UUID reportId) {
        return dsl.select(REPORT_INPUTS.INPUT_ID)
                .from(REPORT_INPUTS)
                .where(REPORT_INPUTS.REPORT_ID.eq(reportId)
                        .and(REPORT_INPUTS.INPUT_TYPE.eq(ReportInputType.MIGRATION_INPUT_REF.name())))
                .fetch(REPORT_INPUTS.INPUT_ID);
    }

    public List<InputSummaryRow> summarizeCurrentInputs(UUID projectId, UUID sourceRevisionId) {
        return dsl.select(
                        MIGRATION_INPUT_REFS.STATUS,
                        MIGRATION_INPUT_REFS.SOURCE_TYPE,
                        MIGRATION_INPUT_REFS.DETECTED_LEVEL,
                        DSL.count()
                )
                .from(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId)))
                .groupBy(MIGRATION_INPUT_REFS.STATUS, MIGRATION_INPUT_REFS.SOURCE_TYPE, MIGRATION_INPUT_REFS.DETECTED_LEVEL)
                .fetch(record -> new InputSummaryRow(
                        record.get(MIGRATION_INPUT_REFS.STATUS),
                        record.get(MIGRATION_INPUT_REFS.SOURCE_TYPE),
                        record.get(MIGRATION_INPUT_REFS.DETECTED_LEVEL),
                        record.get(DSL.count(), long.class)
                ));
    }

    public long countInputPreview(UUID projectId, UUID sourceRevisionId, ReportInputPreviewListRequest request) {
        return dsl.selectCount()
                .from(MIGRATION_INPUT_REFS)
                .where(inputPreviewFilter(projectId, sourceRevisionId, request))
                .fetchOne(0, long.class);
    }

    public List<MigrationInputRefView> listInputPreview(UUID projectId, UUID sourceRevisionId, ReportInputPreviewListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(inputPreviewFilter(projectId, sourceRevisionId, request))
                .orderBy(inputPreviewSort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(MigrationInputRefView::from);
    }

    private Condition filter(UUID projectId, ReportListRequest request) {
        Condition condition = REPORTS.PROJECT_ID.eq(projectId).and(REPORTS.REPORT_TYPE.eq(ReportType.EVALUATION.name()));
        if (request.sourceRevisionId() != null) {
            condition = condition.and(REPORTS.SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        if (request.status() != null) {
            condition = condition.and(REPORTS.STATUS.eq(request.status().name()));
        }
        if (request.riskLevel() != null && !request.riskLevel().isBlank()) {
            condition = condition.and(REPORTS.RISK_LEVEL.eq(request.riskLevel().trim()));
        }
        if (request.createdFrom() != null) {
            condition = condition.and(REPORTS.CREATED_AT.ge(request.createdFrom()));
        }
        if (request.createdTo() != null) {
            condition = condition.and(REPORTS.CREATED_AT.le(request.createdTo()));
        }
        return condition;
    }

    private List<SortField<?>> sort(ReportListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "generatedAt" -> REPORTS.GENERATED_AT;
            case "createdAt" -> REPORTS.CREATED_AT;
            case "status" -> REPORTS.STATUS;
            case "riskLevel" -> REPORTS.RISK_LEVEL;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported report sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(REPORTS.GENERATED_AT.desc().nullsLast(), REPORTS.CREATED_AT.desc(), REPORTS.ID.desc());
        }
        return List.of("asc".equalsIgnoreCase(request.sortDirection()) ? field.asc().nullsLast() : field.desc().nullsLast(), REPORTS.ID.desc());
    }

    private Condition inputFilter(UUID reportId, ReportInputListRequest request) {
        Condition condition = REPORT_INPUTS.REPORT_ID.eq(reportId);
        if (request.inputType() != null) {
            condition = condition.and(REPORT_INPUTS.INPUT_TYPE.eq(request.inputType().name()));
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            condition = condition.and(REPORT_INPUTS.INPUT_SNAPSHOT.cast(String.class).containsIgnoreCase(request.keyword().trim()));
        }
        return condition;
    }

    private Condition inputPreviewFilter(UUID projectId, UUID sourceRevisionId, ReportInputPreviewListRequest request) {
        Condition condition = MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        if (request.sourceType() != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.SOURCE_TYPE.eq(request.sourceType().name()));
        }
        if (request.status() != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.STATUS.eq(request.status().name()));
        }
        if (request.riskLevel() != null && !request.riskLevel().isBlank()) {
            if (!MigrationInputRiskPolicy.isKnownRiskToken(request.riskLevel())) {
                throw new IllegalArgumentException("Unsupported report input preview risk level: " + request.riskLevel());
            }
            String riskLevel = MigrationInputRiskPolicy.normalizeRiskToken(request.riskLevel());
            condition = condition.and(DSL.upper(MIGRATION_INPUT_REFS.DETECTED_LEVEL).eq(riskLevel)
                    .or(DSL.upper(MIGRATION_INPUT_REFS.DETECTED_LEVEL).like(riskLevel + "/%")));
        }
        String keyword = blankToNull(request.keyword());
        if (keyword != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.ISSUE_TITLE.containsIgnoreCase(keyword)
                    .or(MIGRATION_INPUT_REFS.LOCATION_LABEL.containsIgnoreCase(keyword))
                    .or(MIGRATION_INPUT_REFS.RECOMMENDATION_SUMMARY.containsIgnoreCase(keyword))
                    .or(MIGRATION_INPUT_REFS.NOTE.containsIgnoreCase(keyword)));
        }
        return condition;
    }

    private List<SortField<?>> inputSort(ReportInputListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "createdAt" -> REPORT_INPUTS.CREATED_AT;
            case "inputType" -> REPORT_INPUTS.INPUT_TYPE;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported report input sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(REPORT_INPUTS.CREATED_AT.asc(), REPORT_INPUTS.ID.asc());
        }
        return List.of("desc".equalsIgnoreCase(request.sortDirection()) ? field.desc().nullsLast() : field.asc().nullsLast(), REPORT_INPUTS.ID.asc());
    }

    private List<SortField<?>> inputPreviewSort(ReportInputPreviewListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "createdAt" -> MIGRATION_INPUT_REFS.CREATED_AT;
            case "updatedAt" -> MIGRATION_INPUT_REFS.UPDATED_AT;
            case "sourceType" -> MIGRATION_INPUT_REFS.SOURCE_TYPE;
            case "detectedLevel" -> MIGRATION_INPUT_REFS.DETECTED_LEVEL;
            case "status" -> MIGRATION_INPUT_REFS.STATUS;
            case "issueTitle" -> MIGRATION_INPUT_REFS.ISSUE_TITLE;
            case "locationLabel" -> MIGRATION_INPUT_REFS.LOCATION_LABEL;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported report input preview sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(MIGRATION_INPUT_REFS.UPDATED_AT.desc().nullsLast(), MIGRATION_INPUT_REFS.CREATED_AT.desc(), MIGRATION_INPUT_REFS.ID.desc());
        }
        return List.of("asc".equalsIgnoreCase(request.sortDirection()) ? field.asc().nullsLast() : field.desc().nullsLast(), MIGRATION_INPUT_REFS.ID.asc());
    }

    private JSONB toJsonb(Map<String, ?> value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Report JSON value is not serializable", ex);
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

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    public record ReportInputSnapshot(MigrationInputRefView ref, Map<String, Object> snapshot, ReportInputProjection projection) {
        public ReportInputSnapshot(MigrationInputRefView ref, Map<String, Object> snapshot) {
            this(ref, snapshot, null);
        }
    }

    public record InputSummaryRow(String status, String sourceType, String detectedLevel, long count) {
    }
}
