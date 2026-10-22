package cn.rvport.backend.report;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class ReportOrganizationRepositoryTests {

    private static final UUID REPORT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID INPUT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID SOURCE_INPUT_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID ARTIFACT_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-15T08:00:00Z");

    @Test
    void detectsOrganizationAndReadsStableCodeProjection() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportOrganizationRepository repository = repository(database);
            database.enqueueResult(database.result(
                            new Field<?>[]{DSL.field("exists", Boolean.class)}, new Object[]{true}))
                    .enqueueResult(database.result(inputFields(), inputValues(
                            JSONB.valueOf("{\"items\":[\"target-a\",\"target-b\"]}"),
                            JSONB.valueOf("{\"issueTitle\":\"SIMD\"}"))));

            assertThat(repository.organizationAvailable(REPORT_ID)).isTrue();
            assertThat(repository.listCodeInputs(REPORT_ID)).singleElement().satisfies(input -> {
                assertThat(input.id()).isEqualTo(INPUT_ID);
                assertThat(input.inputId()).isEqualTo(SOURCE_INPUT_ID);
                assertThat(input.relatedModuleKeys()).containsExactly("target-a", "target-b");
                assertThat(input.snapshot()).containsEntry("issueTitle", "SIMD");
                assertThat(input.locationAvailable()).isTrue();
            });
            assertThat(database.executions().get(1).normalizedSql())
                    .contains("source_type = ?", "module_name asc nulls last", "line_start asc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void fallsBackForInvalidJsonAndSupportsUnavailableLocation() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportOrganizationRepository repository = repository(database);
            database.enqueueResult(database.result(inputFields(), inputValues(JSONB.valueOf("bad"), JSONB.valueOf("bad"))));

            ReportOrganizedInput input = repository.listCodeInputs(REPORT_ID).getFirst();

            assertThat(input.relatedModuleKeys()).isEmpty();
            assertThat(input.snapshot()).isEmpty();
            assertThat(input.locationAvailable()).isTrue();
            database.verifyComplete();
        }
    }

    @Test
    void upsertsAndFindsImmutableFileContext() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportOrganizationRepository repository = repository(database);
            ReportFileContextView context = new ReportFileContextView(UUID.randomUUID(), REPORT_ID, REVISION_ID,
                    "file-key", "src/main.c", "sha256", 100, ARTIFACT_ID, true, null, NOW);
            Field<?>[] contextFields = {
                    field("id", UUID.class), field("report_id", UUID.class), field("source_revision_id", UUID.class),
                    field("file_key", String.class), field("relative_path", String.class), field("content_hash", String.class),
                    field("total_lines", Integer.class), field("artifact_id", UUID.class),
                    field("context_available", Boolean.class), field("unavailable_reason", String.class),
                    field("created_at", OffsetDateTime.class)
            };
            database.enqueueRows(1).enqueueResult(database.result(contextFields, new Object[]{
                    context.id(), REPORT_ID, REVISION_ID, "file-key", "src/main.c", "sha256", 100,
                    ARTIFACT_ID, true, null, NOW
            }));

            repository.upsertFileContext(context);
            ReportFileContextView loaded = repository.findFileContext(REPORT_ID, "file-key").orElseThrow();

            assertThat(loaded).isEqualTo(context);
            assertThat(database.executions().getFirst().normalizedSql()).contains("on conflict", "do update");
            assertThat(database.executions().get(1).normalizedSql()).contains("report_id = cast(? as uuid)", "file_key = ?");
            database.verifyComplete();
        }
    }

    @Test
    void returnsEmptyWhenContextDoesNotExist() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ReportOrganizationRepository repository = repository(database);
            database.enqueueResult(database.result(new Field<?>[]{
                    field("id", UUID.class), field("report_id", UUID.class), field("source_revision_id", UUID.class),
                    field("file_key", String.class), field("relative_path", String.class), field("content_hash", String.class),
                    field("total_lines", Integer.class), field("artifact_id", UUID.class),
                    field("context_available", Boolean.class), field("unavailable_reason", String.class),
                    field("created_at", OffsetDateTime.class)
            }));

            assertThat(repository.findFileContext(REPORT_ID, "missing")).isEmpty();
            database.verifyComplete();
        }
    }

    private static ReportOrganizationRepository repository(JooqMockDatabase database) {
        return new ReportOrganizationRepository(database.dsl(), new ObjectMapper());
    }

    private static Field<?>[] inputFields() {
        return new Field<?>[]{
                field("id", UUID.class), field("input_id", UUID.class), field("source_type", String.class),
                field("risk_level", String.class), field("module_key", String.class), field("module_name", String.class),
                field("module_basis", String.class), field("module_confidence", String.class),
                field("related_module_keys", JSONB.class), field("file_key", String.class),
                field("relative_path", String.class), field("finding_type", String.class),
                field("line_start", Integer.class), field("line_end", Integer.class),
                field("column_start", Integer.class), field("column_end", Integer.class), field("symbol", String.class),
                field("source_content_hash", String.class), field("location_available", Boolean.class),
                field("input_snapshot", JSONB.class)
        };
    }

    private static Object[] inputValues(JSONB related, JSONB snapshot) {
        return new Object[]{
                INPUT_ID, SOURCE_INPUT_ID, "KB_FINDING", "HIGH", "module-key", "module", "EXPLICIT_BUILD_TARGET",
                "HIGH", related, "file-key", "src/main.c", "INTRINSIC", 10, 12, 2, 8, "main", "sha256", true, snapshot
        };
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }
}
