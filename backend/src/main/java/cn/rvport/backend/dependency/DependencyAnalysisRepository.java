package cn.rvport.backend.dependency;

import static cn.rvport.backend.workflow.DomainLatestOrdering.activeFirst;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import cn.rvport.backend.task.TaskStatus;
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
public class DependencyAnalysisRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final Table<?> RUNS = DSL.table(DSL.name("dependency_analysis_runs"));
    private static final Field<UUID> RUN_ID = DSL.field(DSL.name("dependency_analysis_runs", "id"), UUID.class);
    private static final Field<UUID> RUN_PROJECT_ID = DSL.field(DSL.name("dependency_analysis_runs", "project_id"), UUID.class);
    private static final Field<UUID> RUN_TASK_ID = DSL.field(DSL.name("dependency_analysis_runs", "task_id"), UUID.class);
    private static final Field<UUID> RUN_SOURCE_REVISION_ID = DSL.field(DSL.name("dependency_analysis_runs", "source_revision_id"), UUID.class);
    private static final Field<UUID> RUN_SOURCE_BUILD_RUN_ID = DSL.field(DSL.name("dependency_analysis_runs", "source_build_run_id"), UUID.class);
    private static final Field<UUID> RUN_TARGET_ENVIRONMENT_ID = DSL.field(DSL.name("dependency_analysis_runs", "target_environment_id"), UUID.class);
    private static final Field<Long> RUN_ENVIRONMENT_CONFIG_VERSION = DSL.field(DSL.name("dependency_analysis_runs", "environment_config_version"), Long.class);
    private static final Field<String> RUN_STATUS = DSL.field(DSL.name("dependency_analysis_runs", "status"), String.class);
    private static final Field<JSONB> RUN_SUMMARY = DSL.field(DSL.name("dependency_analysis_runs", "summary"), JSONB.class);
    private static final Field<JSONB> RUN_WARNINGS = DSL.field(DSL.name("dependency_analysis_runs", "warnings"), JSONB.class);
    private static final Field<OffsetDateTime> RUN_STARTED_AT = DSL.field(DSL.name("dependency_analysis_runs", "started_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_FINISHED_AT = DSL.field(DSL.name("dependency_analysis_runs", "finished_at"), OffsetDateTime.class);
    private static final Field<OffsetDateTime> RUN_CREATED_AT = DSL.field(DSL.name("dependency_analysis_runs", "created_at"), OffsetDateTime.class);

    private static final Table<?> ITEMS = DSL.table(DSL.name("dependency_analysis_result_items"));
    private static final Field<UUID> ITEM_ID = DSL.field(DSL.name("dependency_analysis_result_items", "id"), UUID.class);
    private static final Field<UUID> ITEM_PROJECT_ID = DSL.field(DSL.name("dependency_analysis_result_items", "project_id"), UUID.class);
    private static final Field<UUID> ITEM_SOURCE_REVISION_ID = DSL.field(DSL.name("dependency_analysis_result_items", "source_revision_id"), UUID.class);
    private static final Field<UUID> ITEM_TASK_ID = DSL.field(DSL.name("dependency_analysis_result_items", "task_id"), UUID.class);
    private static final Field<UUID> ITEM_RUN_ID = DSL.field(DSL.name("dependency_analysis_result_items", "dependency_analysis_run_id"), UUID.class);
    private static final Field<String> ITEM_TYPE = DSL.field(DSL.name("dependency_analysis_result_items", "dependency_type"), String.class);
    private static final Field<String> ITEM_NAME = DSL.field(DSL.name("dependency_analysis_result_items", "dependency_name"), String.class);
    private static final Field<String> ITEM_VERSION = DSL.field(DSL.name("dependency_analysis_result_items", "dependency_version"), String.class);
    private static final Field<String> ITEM_SOURCE_PROVIDER_PACKAGE = DSL.field(DSL.name("dependency_analysis_result_items", "source_provider_package"), String.class);
    private static final Field<String> ITEM_SOURCE_PROVIDER_VERSION = DSL.field(DSL.name("dependency_analysis_result_items", "source_provider_version"), String.class);
    private static final Field<String> ITEM_SOURCE_DETECTED_VERSION = DSL.field(DSL.name("dependency_analysis_result_items", "source_detected_version"), String.class);
    private static final Field<String> ITEM_TARGET_PROVIDER_PACKAGE = DSL.field(DSL.name("dependency_analysis_result_items", "target_provider_package"), String.class);
    private static final Field<String> ITEM_TARGET_PROVIDER_VERSION = DSL.field(DSL.name("dependency_analysis_result_items", "target_provider_version"), String.class);
    private static final Field<String> ITEM_TARGET_DETECTED_VERSION = DSL.field(DSL.name("dependency_analysis_result_items", "target_detected_version"), String.class);
    private static final Field<String> ITEM_PROVIDER_VERSION_STATUS = DSL.field(DSL.name("dependency_analysis_result_items", "provider_version_status"), String.class);
    private static final Field<String> ITEM_VERSION_EVIDENCE_CONFIDENCE = DSL.field(DSL.name("dependency_analysis_result_items", "version_evidence_confidence"), String.class);
    private static final Field<String> ITEM_TARGET_STATUS = DSL.field(DSL.name("dependency_analysis_result_items", "target_match_status"), String.class);
    private static final Field<String> ITEM_RISK = DSL.field(DSL.name("dependency_analysis_result_items", "risk_level"), String.class);
    private static final Field<String> ITEM_LOCATION = DSL.field(DSL.name("dependency_analysis_result_items", "location_label"), String.class);
    private static final Field<String> ITEM_RECOMMENDATION = DSL.field(DSL.name("dependency_analysis_result_items", "recommendation"), String.class);
    private static final Field<String> ITEM_CONFIDENCE = DSL.field(DSL.name("dependency_analysis_result_items", "confidence"), String.class);
    private static final Field<JSONB> ITEM_EVIDENCE = DSL.field(DSL.name("dependency_analysis_result_items", "evidence"), JSONB.class);
    private static final Field<OffsetDateTime> ITEM_CREATED_AT = DSL.field(DSL.name("dependency_analysis_result_items", "created_at"), OffsetDateTime.class);
    private static final Table<?> ENVIRONMENT_SNAPSHOTS = DSL.table(DSL.name("environment_snapshots"));
    private static final Field<UUID> SNAPSHOT_ID = DSL.field(DSL.name("environment_snapshots", "id"), UUID.class);
    private static final Field<UUID> SNAPSHOT_PROJECT_ID = DSL.field(DSL.name("environment_snapshots", "project_id"), UUID.class);
    private static final Field<UUID> SNAPSHOT_ENVIRONMENT_ID = DSL.field(DSL.name("environment_snapshots", "environment_id"), UUID.class);
    private static final Field<String> SNAPSHOT_STATUS = DSL.field(DSL.name("environment_snapshots", "status"), String.class);
    private static final Field<OffsetDateTime> SNAPSHOT_COLLECTED_AT = DSL.field(DSL.name("environment_snapshots", "collected_at"), OffsetDateTime.class);

    private static final Table<?> ENVIRONMENT_COMPONENTS = DSL.table(DSL.name("environment_components"));
    private static final Field<UUID> COMPONENT_SNAPSHOT_ID = DSL.field(DSL.name("environment_components", "snapshot_id"), UUID.class);
    private static final Field<String> COMPONENT_NAME = DSL.field(DSL.name("environment_components", "name"), String.class);
    private static final Field<String> COMPONENT_VERSION = DSL.field(DSL.name("environment_components", "version"), String.class);
    private static final Field<String> COMPONENT_TYPE = DSL.field(DSL.name("environment_components", "component_type"), String.class);
    private static final Field<String> COMPONENT_PATH = DSL.field(DSL.name("environment_components", "path"), String.class);
    private static final Field<String> COMPONENT_SOURCE = DSL.field(DSL.name("environment_components", "source"), String.class);
    private static final Field<JSONB> COMPONENT_METADATA = DSL.field(DSL.name("environment_components", "metadata"), JSONB.class);

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public DependencyAnalysisRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public DependencyAnalysisView createRun(UUID id, UUID projectId, UUID taskId, UUID sourceRevisionId,
                                            UUID sourceBuildRunId, UUID targetEnvironmentId, long environmentConfigVersion) {
        Record record = dsl.insertInto(RUNS)
                .columns(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS)
                .values(id, projectId, taskId, sourceRevisionId, sourceBuildRunId, targetEnvironmentId,
                        environmentConfigVersion, TaskStatus.PENDING.name())
                .returningResult(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .fetchOne();
        return mapRun(record);
    }

    public Optional<DependencyAnalysisView> findById(UUID runId) {
        return dsl.select(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .from(RUNS)
                .where(RUN_ID.eq(runId))
                .fetchOptional(this::mapRun);
    }

    public Optional<DependencyAnalysisView> findByTaskId(UUID taskId) {
        return dsl.select(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .from(RUNS)
                .where(RUN_TASK_ID.eq(taskId))
                .fetchOptional(this::mapRun);
    }

    public Optional<DependencyAnalysisView> findLatestSucceededRun(UUID projectId, UUID sourceRevisionId) {
        return dsl.select(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .from(RUNS)
                .where(RUN_PROJECT_ID.eq(projectId)
                        .and(RUN_SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(RUN_STATUS.eq(TaskStatus.SUCCEEDED.name())))
                .orderBy(RUN_FINISHED_AT.desc().nullsLast(), RUN_CREATED_AT.desc(), RUN_ID.desc())
                .limit(1)
                .fetchOptional(this::mapRun);
    }

    public Optional<DependencyAnalysisView> findLatestRun(UUID projectId, UUID sourceRevisionId, Long environmentConfigVersion) {
        Condition condition = RUN_PROJECT_ID.eq(projectId);
        if (sourceRevisionId != null) {
            condition = condition.and(RUN_SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        if (environmentConfigVersion != null) {
            condition = condition.and(RUN_ENVIRONMENT_CONFIG_VERSION.eq(environmentConfigVersion));
        }
        return dsl.select(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .from(RUNS)
                .where(condition)
                .orderBy(activeFirst(RUN_STATUS), RUN_CREATED_AT.desc(), RUN_ID.desc())
                .limit(1)
                .fetchOptional(this::mapRun);
    }

    public long countRuns(UUID projectId, DependencyAnalysisListRequest request) {
        return dsl.selectCount().from(RUNS).where(runFilter(projectId, request)).fetchOne(0, long.class);
    }

    public List<DependencyAnalysisView> listRuns(UUID projectId, DependencyAnalysisListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.select(RUN_ID, RUN_PROJECT_ID, RUN_TASK_ID, RUN_SOURCE_REVISION_ID, RUN_SOURCE_BUILD_RUN_ID,
                        RUN_TARGET_ENVIRONMENT_ID, RUN_ENVIRONMENT_CONFIG_VERSION, RUN_STATUS, RUN_SUMMARY,
                        RUN_WARNINGS, RUN_STARTED_AT, RUN_FINISHED_AT, RUN_CREATED_AT)
                .from(RUNS)
                .where(runFilter(projectId, request))
                .orderBy(runSort(request), RUN_ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::mapRun);
    }

    public void markRunning(UUID runId) {
        dsl.update(RUNS)
                .set(RUN_STATUS, TaskStatus.RUNNING.name())
                .set(RUN_STARTED_AT, OffsetDateTime.now())
                .where(RUN_ID.eq(runId))
                .execute();
    }

    public void markFinished(UUID runId, TaskStatus status, Map<String, ?> summary, Object warnings) {
        dsl.update(RUNS)
                .set(RUN_STATUS, status.name())
                .set(RUN_SUMMARY, toJsonb(summary))
                .set(RUN_WARNINGS, toJsonb(Map.of("items", warnings == null ? List.of() : warnings)))
                .set(RUN_FINISHED_AT, OffsetDateTime.now())
                .where(RUN_ID.eq(runId))
                .execute();
    }

    public void replaceResultItems(UUID runId, List<DependencyAnalysisResultItem> items) {
        dsl.deleteFrom(ITEMS).where(ITEM_RUN_ID.eq(runId)).execute();
        for (DependencyAnalysisResultItem item : items) {
            dsl.insertInto(ITEMS)
                    .columns(ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID, ITEM_TASK_ID, ITEM_RUN_ID, ITEM_TYPE, ITEM_NAME,
                            ITEM_VERSION, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                            ITEM_SOURCE_DETECTED_VERSION, ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION,
                            ITEM_TARGET_DETECTED_VERSION, ITEM_PROVIDER_VERSION_STATUS,
                            ITEM_VERSION_EVIDENCE_CONFIDENCE, ITEM_TARGET_STATUS, ITEM_RISK, ITEM_LOCATION, ITEM_RECOMMENDATION,
                            ITEM_CONFIDENCE, ITEM_EVIDENCE)
                    .values(item.projectId(), item.sourceRevisionId(), item.taskId(), item.dependencyAnalysisRunId(),
                            item.dependencyType().name(), item.dependencyName(), blankToNull(item.dependencyVersion()),
                            blankToNull(item.sourceProviderPackage()), blankToNull(item.sourceProviderVersion()),
                            blankToNull(item.sourceDetectedVersion()), blankToNull(item.targetProviderPackage()),
                            blankToNull(item.targetProviderVersion()), blankToNull(item.targetDetectedVersion()),
                            blankToNull(item.providerVersionStatus()), blankToNull(item.versionEvidenceConfidence()),
                            item.targetMatchStatus().name(), item.riskLevel().name(), blankToNull(item.locationLabel()),
                            blankToNull(item.recommendation()),
                            item.confidence() == null ? null : item.confidence().name(), toJsonb(item.evidence()))
                    .execute();
        }
    }

    public long countResultItems(UUID runId, DependencyAnalysisResultListRequest request) {
        return dsl.selectCount().from(ITEMS).where(resultFilter(runId, request)).fetchOne(0, long.class);
    }

    public List<DependencyAnalysisResultItemResponse> listResultItems(UUID runId, DependencyAnalysisResultListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.select(ITEM_ID, ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID, ITEM_TASK_ID, ITEM_RUN_ID, ITEM_TYPE,
                        ITEM_NAME, ITEM_VERSION, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                        ITEM_SOURCE_DETECTED_VERSION, ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION,
                        ITEM_TARGET_DETECTED_VERSION, ITEM_PROVIDER_VERSION_STATUS, ITEM_VERSION_EVIDENCE_CONFIDENCE,
                        ITEM_TARGET_STATUS, ITEM_RISK, ITEM_LOCATION, ITEM_RECOMMENDATION,
                        ITEM_CONFIDENCE, ITEM_EVIDENCE, ITEM_CREATED_AT)
                .from(ITEMS)
                .where(resultFilter(runId, request))
                .orderBy(resultSort(request), ITEM_ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::mapItemResponse);
    }

    public Optional<DependencyAnalysisResultItemView> findResultItem(UUID itemId) {
        return dsl.select(ITEM_ID, ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID, ITEM_TASK_ID, ITEM_RUN_ID, ITEM_TYPE,
                        ITEM_NAME, ITEM_VERSION, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                        ITEM_SOURCE_DETECTED_VERSION, ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION,
                        ITEM_TARGET_DETECTED_VERSION, ITEM_PROVIDER_VERSION_STATUS, ITEM_VERSION_EVIDENCE_CONFIDENCE,
                        ITEM_TARGET_STATUS, ITEM_RISK, ITEM_LOCATION, ITEM_RECOMMENDATION,
                        ITEM_CONFIDENCE, ITEM_EVIDENCE, ITEM_CREATED_AT)
                .from(ITEMS)
                .where(ITEM_ID.eq(itemId))
                .fetchOptional(this::mapItem);
    }

    public List<DependencyAnalysisResultItemView> listResultItemViews(UUID runId) {
        return dsl.select(ITEM_ID, ITEM_PROJECT_ID, ITEM_SOURCE_REVISION_ID, ITEM_TASK_ID, ITEM_RUN_ID, ITEM_TYPE,
                        ITEM_NAME, ITEM_VERSION, ITEM_SOURCE_PROVIDER_PACKAGE, ITEM_SOURCE_PROVIDER_VERSION,
                        ITEM_SOURCE_DETECTED_VERSION, ITEM_TARGET_PROVIDER_PACKAGE, ITEM_TARGET_PROVIDER_VERSION,
                        ITEM_TARGET_DETECTED_VERSION, ITEM_PROVIDER_VERSION_STATUS, ITEM_VERSION_EVIDENCE_CONFIDENCE,
                        ITEM_TARGET_STATUS, ITEM_RISK, ITEM_LOCATION, ITEM_RECOMMENDATION,
                        ITEM_CONFIDENCE, ITEM_EVIDENCE, ITEM_CREATED_AT)
                .from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId))
                .orderBy(riskRank().desc(), ITEM_TYPE.asc(), ITEM_NAME.asc(), ITEM_ID.asc())
                .fetch(this::mapItem);
    }

    public List<UUID> listResultItemIds(UUID runId) {
        return dsl.select(ITEM_ID)
                .from(ITEMS)
                .where(ITEM_RUN_ID.eq(runId))
                .orderBy(riskRank().desc(), ITEM_TYPE.asc(), ITEM_NAME.asc(), ITEM_ID.asc())
                .fetch(ITEM_ID);
    }

    public Optional<UUID> findLatestSucceededSnapshotId(UUID projectId, UUID environmentId) {
        return dsl.select(SNAPSHOT_ID)
                .from(ENVIRONMENT_SNAPSHOTS)
                .where(SNAPSHOT_PROJECT_ID.eq(projectId)
                        .and(SNAPSHOT_ENVIRONMENT_ID.eq(environmentId))
                        .and(SNAPSHOT_STATUS.eq(TaskStatus.SUCCEEDED.name())))
                .orderBy(SNAPSHOT_COLLECTED_AT.desc(), SNAPSHOT_ID.desc())
                .limit(1)
                .fetchOptional(SNAPSHOT_ID);
    }

    public Optional<OffsetDateTime> findSnapshotCollectedAt(UUID snapshotId) {
        return dsl.select(SNAPSHOT_COLLECTED_AT)
                .from(ENVIRONMENT_SNAPSHOTS)
                .where(SNAPSHOT_ID.eq(snapshotId))
                .fetchOptional(SNAPSHOT_COLLECTED_AT);
    }

    public List<TargetComponentView> listTargetComponents(UUID snapshotId) {
        return dsl.select(COMPONENT_NAME, COMPONENT_VERSION, COMPONENT_TYPE, COMPONENT_PATH, COMPONENT_SOURCE, COMPONENT_METADATA)
                .from(ENVIRONMENT_COMPONENTS)
                .where(COMPONENT_SNAPSHOT_ID.eq(snapshotId))
                .fetch(record -> new TargetComponentView(
                        record.get(COMPONENT_NAME),
                        record.get(COMPONENT_VERSION),
                        record.get(COMPONENT_TYPE),
                        record.get(COMPONENT_PATH),
                        record.get(COMPONENT_SOURCE),
                        jsonbToMap(record.get(COMPONENT_METADATA))
                ));
    }

    public record TargetComponentView(
            String name,
            String version,
            String componentType,
            String path,
            String source,
            Map<String, Object> metadata
    ) {
    }

    private Condition runFilter(UUID projectId, DependencyAnalysisListRequest request) {
        Condition condition = RUN_PROJECT_ID.eq(projectId);
        if (request.sourceRevisionId() != null) {
            condition = condition.and(RUN_SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        if (request.environmentConfigVersion() != null) {
            condition = condition.and(RUN_ENVIRONMENT_CONFIG_VERSION.eq(request.environmentConfigVersion()));
        }
        if (request.status() != null) {
            condition = condition.and(RUN_STATUS.eq(request.status().name()));
        }
        if (request.createdFrom() != null) {
            condition = condition.and(RUN_CREATED_AT.ge(request.createdFrom()));
        }
        if (request.createdTo() != null) {
            condition = condition.and(RUN_CREATED_AT.le(request.createdTo()));
        }
        return condition;
    }

    private Condition resultFilter(UUID runId, DependencyAnalysisResultListRequest request) {
        Condition condition = ITEM_RUN_ID.eq(runId);
        if (request.dependencyType() != null) {
            condition = condition.and(ITEM_TYPE.eq(request.dependencyType().name()));
        }
        if (request.targetMatchStatus() != null) {
            condition = condition.and(ITEM_TARGET_STATUS.eq(request.targetMatchStatus().name()));
        }
        if (request.riskLevel() != null) {
            condition = condition.and(ITEM_RISK.eq(request.riskLevel().name()));
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String text = "%" + request.keyword().trim().toLowerCase() + "%";
            condition = condition.and(DSL.lower(ITEM_NAME).like(text)
                    .or(DSL.lower(ITEM_LOCATION).like(text))
                    .or(DSL.lower(ITEM_RECOMMENDATION).like(text)));
        }
        return condition;
    }

    private SortField<?> runSort(DependencyAnalysisListRequest request) {
        Field<?> field = switch (normalize(request.sortBy())) {
            case "startedAt" -> RUN_STARTED_AT;
            case "finishedAt" -> RUN_FINISHED_AT;
            case "status" -> RUN_STATUS;
            default -> RUN_CREATED_AT;
        };
        return "asc".equalsIgnoreCase(request.sortDirection()) ? field.asc() : field.desc();
    }

    private SortField<?> resultSort(DependencyAnalysisResultListRequest request) {
        Field<?> field = switch (normalize(request.sortBy())) {
            case "dependencyType" -> ITEM_TYPE;
            case "dependencyName" -> ITEM_NAME;
            case "targetMatchStatus" -> ITEM_TARGET_STATUS;
            case "riskLevel" -> riskRank();
            default -> ITEM_CREATED_AT;
        };
        return "asc".equalsIgnoreCase(request.sortDirection()) ? field.asc() : field.desc();
    }

    private Field<Integer> riskRank() {
        return DSL.when(ITEM_RISK.eq("CRITICAL"), 6)
                .when(ITEM_RISK.eq("HIGH"), 5)
                .when(ITEM_RISK.eq("MEDIUM"), 4)
                .when(ITEM_RISK.eq("LOW"), 3)
                .when(ITEM_RISK.eq("INFO"), 2)
                .when(ITEM_RISK.eq("COMMENT"), 1)
                .otherwise(0);
    }

    private DependencyAnalysisView mapRun(Record record) {
        return new DependencyAnalysisView(
                record.get(RUN_ID),
                record.get(RUN_PROJECT_ID),
                record.get(RUN_TASK_ID),
                record.get(RUN_SOURCE_REVISION_ID),
                record.get(RUN_SOURCE_BUILD_RUN_ID),
                record.get(RUN_TARGET_ENVIRONMENT_ID),
                record.get(RUN_ENVIRONMENT_CONFIG_VERSION),
                TaskStatus.valueOf(record.get(RUN_STATUS)),
                jsonbToMap(record.get(RUN_SUMMARY)),
                jsonbToMap(record.get(RUN_WARNINGS)).getOrDefault("items", List.of()),
                record.get(RUN_STARTED_AT),
                record.get(RUN_FINISHED_AT),
                record.get(RUN_CREATED_AT)
        );
    }

    private DependencyAnalysisResultItemResponse mapItemResponse(Record record) {
        return DependencyAnalysisResultItemResponse.from(mapItem(record));
    }

    private DependencyAnalysisResultItemView mapItem(Record record) {
        String confidence = record.get(ITEM_CONFIDENCE);
        return new DependencyAnalysisResultItemView(
                record.get(ITEM_ID),
                record.get(ITEM_PROJECT_ID),
                record.get(ITEM_SOURCE_REVISION_ID),
                record.get(ITEM_TASK_ID),
                record.get(ITEM_RUN_ID),
                DependencyType.valueOf(record.get(ITEM_TYPE)),
                record.get(ITEM_NAME),
                record.get(ITEM_VERSION),
                record.get(ITEM_SOURCE_PROVIDER_PACKAGE),
                record.get(ITEM_SOURCE_PROVIDER_VERSION),
                record.get(ITEM_SOURCE_DETECTED_VERSION),
                record.get(ITEM_TARGET_PROVIDER_PACKAGE),
                record.get(ITEM_TARGET_PROVIDER_VERSION),
                record.get(ITEM_TARGET_DETECTED_VERSION),
                record.get(ITEM_PROVIDER_VERSION_STATUS),
                record.get(ITEM_VERSION_EVIDENCE_CONFIDENCE),
                DependencyTargetMatchStatus.valueOf(record.get(ITEM_TARGET_STATUS)),
                DependencyRiskLevel.valueOf(record.get(ITEM_RISK)),
                record.get(ITEM_LOCATION),
                record.get(ITEM_RECOMMENDATION),
                confidence == null ? null : DependencyConfidence.valueOf(confidence),
                jsonbToMap(record.get(ITEM_EVIDENCE)),
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

    private String normalize(String value) {
        return value == null || value.isBlank() ? "" : value.trim();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
