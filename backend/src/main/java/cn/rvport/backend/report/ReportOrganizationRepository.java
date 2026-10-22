package cn.rvport.backend.report;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ReportOrganizationRepository {

    private static final Table<?> INPUTS = DSL.table(DSL.name("report_inputs"));
    private static final Table<?> CONTEXTS = DSL.table(DSL.name("report_file_contexts"));
    private static final Field<UUID> INPUT_ID = field("id", UUID.class);
    private static final Field<UUID> SOURCE_INPUT_ID = field("input_id", UUID.class);
    private static final Field<UUID> REPORT_ID = field("report_id", UUID.class);
    private static final Field<String> SOURCE_TYPE = field("source_type", String.class);
    private static final Field<String> RISK_LEVEL = field("risk_level", String.class);
    private static final Field<String> MODULE_KEY = field("module_key", String.class);
    private static final Field<String> MODULE_NAME = field("module_name", String.class);
    private static final Field<String> MODULE_BASIS = field("module_basis", String.class);
    private static final Field<String> MODULE_CONFIDENCE = field("module_confidence", String.class);
    private static final Field<JSONB> RELATED_MODULE_KEYS = field("related_module_keys", JSONB.class);
    private static final Field<String> FILE_KEY = field("file_key", String.class);
    private static final Field<String> RELATIVE_PATH = field("relative_path", String.class);
    private static final Field<String> FINDING_TYPE = field("finding_type", String.class);
    private static final Field<Integer> LINE_START = field("line_start", Integer.class);
    private static final Field<Integer> LINE_END = field("line_end", Integer.class);
    private static final Field<Integer> COLUMN_START = field("column_start", Integer.class);
    private static final Field<Integer> COLUMN_END = field("column_end", Integer.class);
    private static final Field<String> SYMBOL = field("symbol", String.class);
    private static final Field<String> SOURCE_CONTENT_HASH = field("source_content_hash", String.class);
    private static final Field<Boolean> LOCATION_AVAILABLE = field("location_available", Boolean.class);
    private static final Field<JSONB> INPUT_SNAPSHOT = field("input_snapshot", JSONB.class);

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<Map<String, List<String>>> LIST_WRAPPER_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ReportOrganizationRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public boolean organizationAvailable(UUID reportId) {
        return dsl.fetchExists(dsl.selectOne().from(INPUTS)
                .where(REPORT_ID.eq(reportId).and(SOURCE_TYPE.isNotNull())));
    }

    public List<ReportOrganizedInput> listCodeInputs(UUID reportId) {
        return dsl.select(INPUT_ID, SOURCE_INPUT_ID, SOURCE_TYPE, RISK_LEVEL, MODULE_KEY, MODULE_NAME,
                        MODULE_BASIS, MODULE_CONFIDENCE, RELATED_MODULE_KEYS, FILE_KEY, RELATIVE_PATH,
                        FINDING_TYPE, LINE_START, LINE_END, COLUMN_START, COLUMN_END, SYMBOL,
                        SOURCE_CONTENT_HASH, LOCATION_AVAILABLE, INPUT_SNAPSHOT)
                .from(INPUTS)
                .where(REPORT_ID.eq(reportId).and(SOURCE_TYPE.eq("KB_FINDING")))
                .orderBy(MODULE_NAME.asc().nullsLast(), RELATIVE_PATH.asc().nullsLast(),
                        FINDING_TYPE.asc().nullsLast(), LINE_START.asc().nullsLast(), LINE_END.asc().nullsLast(), INPUT_ID.asc())
                .fetch(record -> new ReportOrganizedInput(
                        record.get(INPUT_ID), record.get(SOURCE_INPUT_ID), record.get(SOURCE_TYPE), record.get(RISK_LEVEL),
                        record.get(MODULE_KEY), record.get(MODULE_NAME), record.get(MODULE_BASIS), record.get(MODULE_CONFIDENCE),
                        list(record.get(RELATED_MODULE_KEYS)), record.get(FILE_KEY), record.get(RELATIVE_PATH),
                        record.get(FINDING_TYPE), record.get(LINE_START), record.get(LINE_END), record.get(COLUMN_START),
                        record.get(COLUMN_END), record.get(SYMBOL), record.get(SOURCE_CONTENT_HASH),
                        Boolean.TRUE.equals(record.get(LOCATION_AVAILABLE)), map(record.get(INPUT_SNAPSHOT))
                ));
    }

    public void upsertFileContext(ReportFileContextView context) {
        Field<UUID> id = field("id", UUID.class);
        Field<UUID> sourceRevisionId = field("source_revision_id", UUID.class);
        Field<String> contentHash = field("content_hash", String.class);
        Field<Integer> totalLines = field("total_lines", Integer.class);
        Field<UUID> artifactId = field("artifact_id", UUID.class);
        Field<Boolean> available = field("context_available", Boolean.class);
        Field<String> reason = field("unavailable_reason", String.class);
        dsl.insertInto(CONTEXTS)
                .columns(id, REPORT_ID, sourceRevisionId, FILE_KEY, RELATIVE_PATH, contentHash, totalLines, artifactId, available, reason)
                .values(context.id(), context.reportId(), context.sourceRevisionId(), context.fileKey(), context.relativePath(),
                        context.contentHash(), context.totalLines(), context.artifactId(), context.contextAvailable(), context.unavailableReason())
                .onConflict(REPORT_ID, FILE_KEY)
                .doUpdate()
                .set(contentHash, context.contentHash())
                .set(totalLines, context.totalLines())
                .set(artifactId, context.artifactId())
                .set(available, context.contextAvailable())
                .set(reason, context.unavailableReason())
                .execute();
    }

    public Optional<ReportFileContextView> findFileContext(UUID reportId, String fileKey) {
        Field<UUID> id = field("id", UUID.class);
        Field<UUID> sourceRevisionId = field("source_revision_id", UUID.class);
        Field<String> contentHash = field("content_hash", String.class);
        Field<Integer> totalLines = field("total_lines", Integer.class);
        Field<UUID> artifactId = field("artifact_id", UUID.class);
        Field<Boolean> available = field("context_available", Boolean.class);
        Field<String> reason = field("unavailable_reason", String.class);
        Field<OffsetDateTime> createdAt = field("created_at", OffsetDateTime.class);
        return dsl.select(id, REPORT_ID, sourceRevisionId, FILE_KEY, RELATIVE_PATH, contentHash, totalLines,
                        artifactId, available, reason, createdAt)
                .from(CONTEXTS)
                .where(REPORT_ID.eq(reportId).and(FILE_KEY.eq(fileKey)))
                .fetchOptional(record -> new ReportFileContextView(
                        record.get(id), record.get(REPORT_ID), record.get(sourceRevisionId), record.get(FILE_KEY),
                        record.get(RELATIVE_PATH), record.get(contentHash), record.get(totalLines), record.get(artifactId),
                        Boolean.TRUE.equals(record.get(available)), record.get(reason), record.get(createdAt)
                ));
    }

    private Map<String, Object> map(JSONB value) {
        if (value == null || value.data() == null) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(value.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private List<String> list(JSONB value) {
        if (value == null || value.data() == null) {
            return List.of();
        }
        try {
            return objectMapper.readValue(value.data(), LIST_WRAPPER_TYPE).getOrDefault("items", List.of());
        } catch (Exception ex) {
            return List.of();
        }
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }
}
