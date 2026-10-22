package cn.rvport.backend.kb.ai;

import static cn.rvport.backend.jooq.tables.KbAiExtensionResults.KB_AI_EXTENSION_RESULTS;
import static cn.rvport.backend.jooq.tables.KbAiExtensionRuns.KB_AI_EXTENSION_RUNS;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
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
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class KbAiExtensionRepository {

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public KbAiExtensionRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public KbAiExtensionRunView createRun(
            UUID projectId,
            UUID sourceRevisionId,
            UUID kbScanRunId,
            UUID modelProfileId,
            UUID agentRuntimeId,
            UUID createdBy
    ) {
        var record = dsl.insertInto(KB_AI_EXTENSION_RUNS)
                .set(KB_AI_EXTENSION_RUNS.PROJECT_ID, projectId)
                .set(KB_AI_EXTENSION_RUNS.SOURCE_REVISION_ID, sourceRevisionId)
                .set(KB_AI_EXTENSION_RUNS.KB_SCAN_RUN_ID, kbScanRunId)
                .set(KB_AI_EXTENSION_RUNS.MODEL_PROFILE_ID, modelProfileId)
                .set(KB_AI_EXTENSION_RUNS.AGENT_RUNTIME_ID, agentRuntimeId)
                .set(KB_AI_EXTENSION_RUNS.STATUS, KbAiExtensionStatus.PENDING.name())
                .set(KB_AI_EXTENSION_RUNS.CREATED_BY, createdBy)
                .returning()
                .fetchOne();
        return mapRun(record);
    }

    public KbAiExtensionRunView attachTask(UUID runId, UUID taskId) {
        var record = dsl.update(KB_AI_EXTENSION_RUNS)
                .set(KB_AI_EXTENSION_RUNS.TASK_ID, taskId)
                .set(KB_AI_EXTENSION_RUNS.STATUS, KbAiExtensionStatus.QUEUED.name())
                .set(KB_AI_EXTENSION_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(KB_AI_EXTENSION_RUNS.ID.eq(runId))
                .returning()
                .fetchOne();
        return mapRun(record);
    }

    public Optional<KbAiExtensionRunView> findById(UUID runId) {
        return dsl.selectFrom(KB_AI_EXTENSION_RUNS)
                .where(KB_AI_EXTENSION_RUNS.ID.eq(runId))
                .fetchOptional()
                .map(this::mapRun);
    }

    public Optional<KbAiExtensionRunView> findByTaskId(UUID taskId) {
        return dsl.selectFrom(KB_AI_EXTENSION_RUNS)
                .where(KB_AI_EXTENSION_RUNS.TASK_ID.eq(taskId))
                .fetchOptional()
                .map(this::mapRun);
    }

    public Optional<KbAiExtensionRunView> findLatestCompletedRun(UUID scanRunId) {
        return dsl.selectFrom(KB_AI_EXTENSION_RUNS)
                .where(KB_AI_EXTENSION_RUNS.KB_SCAN_RUN_ID.eq(scanRunId)
                        .and(KB_AI_EXTENSION_RUNS.STATUS.in(
                                KbAiExtensionStatus.SUCCEEDED.name(),
                                KbAiExtensionStatus.PARTIAL_SUCCESS.name())))
                .orderBy(KB_AI_EXTENSION_RUNS.FINISHED_AT.desc().nullsLast(), KB_AI_EXTENSION_RUNS.ID.desc())
                .limit(1)
                .fetchOptional()
                .map(this::mapRun);
    }

    public long countRuns(UUID projectId, KbAiExtensionListRequest request) {
        return dsl.selectCount()
                .from(KB_AI_EXTENSION_RUNS)
                .where(runFilter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<KbAiExtensionRunView> listRuns(UUID projectId, KbAiExtensionListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(KB_AI_EXTENSION_RUNS)
                .where(runFilter(projectId, request))
                .orderBy(runSort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::mapRun);
    }

    public void markRunning(UUID runId) {
        dsl.update(KB_AI_EXTENSION_RUNS)
                .set(KB_AI_EXTENSION_RUNS.STATUS, KbAiExtensionStatus.RUNNING.name())
                .set(KB_AI_EXTENSION_RUNS.STARTED_AT, OffsetDateTime.now())
                .set(KB_AI_EXTENSION_RUNS.UPDATED_AT, OffsetDateTime.now())
                .where(KB_AI_EXTENSION_RUNS.ID.eq(runId))
                .execute();
    }

    public void markFinished(
            UUID runId,
            KbAiExtensionStatus status,
            Map<String, ?> summary,
            UUID inputArtifactId,
            UUID outputArtifactId,
            UUID agentOutputArtifactId
    ) {
        var update = dsl.update(KB_AI_EXTENSION_RUNS)
                .set(KB_AI_EXTENSION_RUNS.STATUS, status.name())
                .set(KB_AI_EXTENSION_RUNS.SUMMARY, toJsonb(summary))
                .set(KB_AI_EXTENSION_RUNS.FINISHED_AT, OffsetDateTime.now())
                .set(KB_AI_EXTENSION_RUNS.UPDATED_AT, OffsetDateTime.now());
        if (inputArtifactId != null) {
            update.set(KB_AI_EXTENSION_RUNS.INPUT_ARTIFACT_ID, inputArtifactId);
        }
        if (outputArtifactId != null) {
            update.set(KB_AI_EXTENSION_RUNS.OUTPUT_ARTIFACT_ID, outputArtifactId);
        }
        if (agentOutputArtifactId != null) {
            update.set(KB_AI_EXTENSION_RUNS.AGENT_OUTPUT_ARTIFACT_ID, agentOutputArtifactId);
        }
        update.where(KB_AI_EXTENSION_RUNS.ID.eq(runId)).execute();
    }

    public void replaceResults(UUID runId, List<KbAiExtensionResultInput> results) {
        dsl.deleteFrom(KB_AI_EXTENSION_RESULTS)
                .where(KB_AI_EXTENSION_RESULTS.RUN_ID.eq(runId))
                .execute();
        for (KbAiExtensionResultInput input : results) {
            dsl.insertInto(KB_AI_EXTENSION_RESULTS)
                    .set(KB_AI_EXTENSION_RESULTS.RUN_ID, runId)
                    .set(KB_AI_EXTENSION_RESULTS.PROJECT_ID, input.projectId())
                    .set(KB_AI_EXTENSION_RESULTS.SOURCE_REVISION_ID, input.sourceRevisionId())
                    .set(KB_AI_EXTENSION_RESULTS.KB_SCAN_RUN_ID, input.kbScanRunId())
                    .set(KB_AI_EXTENSION_RESULTS.FINDING_ID, input.findingId())
                    .set(KB_AI_EXTENSION_RESULTS.AI_SUMMARY, blankToNull(input.aiSummary()))
                    .set(KB_AI_EXTENSION_RESULTS.AI_SUGGESTION, blankToNull(input.aiSuggestion()))
                    .set(KB_AI_EXTENSION_RESULTS.CONFIDENCE, input.confidence())
                    .set(KB_AI_EXTENSION_RESULTS.ACTION_TYPE, blankToNull(input.actionType()))
                    .set(KB_AI_EXTENSION_RESULTS.RAW_PAYLOAD, toJsonb(input.rawPayload()))
                    .execute();
        }
    }

    public Map<UUID, KbAiExtensionSuggestionResponse> latestSuggestions(UUID scanRunId, List<UUID> findingIds) {
        if (findingIds == null || findingIds.isEmpty()) {
            return Map.of();
        }
        KbAiExtensionRunView run = findLatestCompletedRun(scanRunId).orElse(null);
        if (run == null) {
            return Map.of();
        }
        Map<UUID, KbAiExtensionSuggestionResponse> mapped = new LinkedHashMap<>();
        dsl.selectFrom(KB_AI_EXTENSION_RESULTS)
                .where(KB_AI_EXTENSION_RESULTS.RUN_ID.eq(run.id())
                        .and(KB_AI_EXTENSION_RESULTS.FINDING_ID.in(findingIds)))
                .fetch(record -> mapSuggestion(record, jsonbToMap(record.getRawPayload())))
                .forEach(item -> mapped.put(item.findingId(), item));
        return mapped;
    }

    public Optional<KbAiExtensionSuggestionResponse> latestSuggestion(UUID scanRunId, UUID findingId) {
        return latestSuggestions(scanRunId, List.of(findingId)).values().stream().findFirst();
    }

    private KbAiExtensionRunView mapRun(cn.rvport.backend.jooq.tables.records.KbAiExtensionRunsRecord record) {
        return KbAiExtensionRunView.from(record, jsonbToMap(record.getSummary()));
    }

    private KbAiExtensionSuggestionResponse mapSuggestion(
            cn.rvport.backend.jooq.tables.records.KbAiExtensionResultsRecord record,
            Map<String, Object> rawPayload
    ) {
        return new KbAiExtensionSuggestionResponse(
                record.getId(),
                record.getRunId(),
                record.getFindingId(),
                record.getAiSummary(),
                record.getAiSuggestion(),
                record.getConfidence(),
                record.getActionType(),
                rawPayload,
                record.getCreatedAt()
        );
    }

    private Condition runFilter(UUID projectId, KbAiExtensionListRequest request) {
        Condition condition = KB_AI_EXTENSION_RUNS.PROJECT_ID.eq(projectId);
        if (request.status() != null) {
            condition = condition.and(KB_AI_EXTENSION_RUNS.STATUS.eq(request.status().name()));
        }
        if (request.sourceRevisionId() != null) {
            condition = condition.and(KB_AI_EXTENSION_RUNS.SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        if (request.kbScanRunId() != null) {
            condition = condition.and(KB_AI_EXTENSION_RUNS.KB_SCAN_RUN_ID.eq(request.kbScanRunId()));
        }
        return condition;
    }

    private List<SortField<?>> runSort(KbAiExtensionListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "status" -> KB_AI_EXTENSION_RUNS.STATUS;
            case "startedAt" -> KB_AI_EXTENSION_RUNS.STARTED_AT;
            case "finishedAt" -> KB_AI_EXTENSION_RUNS.FINISHED_AT;
            case "createdAt" -> KB_AI_EXTENSION_RUNS.CREATED_AT;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported KB AI extension sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(KB_AI_EXTENSION_RUNS.CREATED_AT.desc(), KB_AI_EXTENSION_RUNS.ID.desc());
        }
        return List.of(sort(field, request.sortDirection()), KB_AI_EXTENSION_RUNS.ID.asc());
    }

    private SortField<?> sort(Field<?> field, String direction) {
        return "asc".equalsIgnoreCase(direction) ? field.asc().nullsLast() : field.desc().nullsLast();
    }

    private String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private JSONB toJsonb(Map<String, ?> value) {
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
            return objectMapper.readValue(jsonb.data(), new TypeReference<>() {
            });
        } catch (Exception ex) {
            return Map.of();
        }
    }

    public record KbAiExtensionResultInput(
            UUID projectId,
            UUID sourceRevisionId,
            UUID kbScanRunId,
            UUID findingId,
            String aiSummary,
            String aiSuggestion,
            BigDecimal confidence,
            String actionType,
            Map<String, Object> rawPayload
    ) {
        public KbAiExtensionResultInput {
            rawPayload = rawPayload == null ? Map.of() : Map.copyOf(rawPayload);
        }
    }
}
