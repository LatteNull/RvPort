package cn.rvport.backend.migration;

import static cn.rvport.backend.jooq.tables.MigrationInputRefs.MIGRATION_INPUT_REFS;
import static cn.rvport.backend.jooq.tables.MigrationInputSets.MIGRATION_INPUT_SETS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.MigrationInputRefsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class MigrationInputRepositoryTests {

    private static final UUID SET_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID SOURCE_REF_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void ensuresSingleActiveSet() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            database.enqueueRows(0).enqueueResult(database.result(new Field<?>[]{MIGRATION_INPUT_SETS.ID}, new Object[]{SET_ID}));
            assertThat(repository.ensureActiveSet(PROJECT_ID, REVISION_ID)).isEqualTo(SET_ID);
            assertThat(database.executions().getFirst().normalizedSql()).contains("on conflict do nothing");
            assertThat(database.executions().get(1).normalizedSql()).contains("project_id =", "source_revision_id =", "status =");
            database.verifyComplete();
        }
    }

    @Test
    void countsFiltersAndPaginatesInputs() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            MigrationInputListRequest request = new MigrationInputListRequest(2, 5, MigrationInputSourceType.KB_FINDING,
                    " high ", MigrationInputStatus.CONFIRMED, " vector ", "detectedLevel", "desc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L})).enqueueRecord(record(MigrationInputStatus.CONFIRMED));
            assertThat(repository.count(PROJECT_ID, REVISION_ID, request)).isEqualTo(1);
            assertThat(repository.list(PROJECT_ID, REVISION_ID, request)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("source_type =", "detected_level =", "status =", "lower");
            assertThat(database.executions().get(1).normalizedSql()).contains("detected_level desc nulls last", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void supportsEverySortAndRejectsUnknownSort() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            String[] sorts = {"createdAt", "updatedAt", "sourceType", "status", "issueTitle", ""};
            for (String ignored : sorts) database.enqueueResult(database.result(MIGRATION_INPUT_REFS.fields()));
            for (String sort : sorts) repository.list(PROJECT_ID, REVISION_ID,
                    new MigrationInputListRequest(null, null, null, null, null, null, sort, "asc"));
            assertThat(database.executions().get(1).normalizedSql()).contains("updated_at asc nulls last");
            assertThat(database.executions().get(5).normalizedSql()).contains("created_at desc", "id desc");
            assertThatThrownBy(() -> repository.list(PROJECT_ID, REVISION_ID,
                    new MigrationInputListRequest(1, 20, null, null, null, null, "risk", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported migration input sort field");
            database.verifyComplete();
        }
    }

    @Test
    void insertsCandidatesWithDefaultsAndCountsConflicts() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            database.enqueueRecord(record(MigrationInputStatus.CANDIDATE)).enqueueResult(database.result(MIGRATION_INPUT_REFS.fields()));
            MigrationInputCandidate created = candidate(null, " src/a.c:4 ", " fix ");
            MigrationInputCandidate duplicate = candidate(MigrationInputStatus.CONFIRMED, "", "");
            MigrationInputRepository.InsertResult result = repository.insertCandidates(SET_ID, List.of(created, duplicate));
            assertThat(result.createdItems()).hasSize(1);
            assertThat(result.skipped()).isEqualTo(1);
            assertThat(database.executions().getFirst().bindings()).contains("src/a.c:4", "fix", MigrationInputStatus.CANDIDATE.name());
            assertThat(database.executions().get(1).bindings()).contains(MigrationInputStatus.CONFIRMED.name()).containsNull();
            database.verifyComplete();
        }
    }

    @Test
    void updatesOptionalFieldsAndHandlesMissingRow() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            database.enqueueRecord(record(MigrationInputStatus.EXCLUDED)).enqueueResult(database.result(MIGRATION_INPUT_REFS.fields()));
            assertThat(repository.update(ID, MigrationInputStatus.EXCLUDED, " ").status()).isEqualTo(MigrationInputStatus.EXCLUDED);
            assertThat(repository.update(ID, null, null)).isNull();
            assertThat(database.executions().getFirst().bindings()).contains(MigrationInputStatus.EXCLUDED.name()).containsNull();
            assertThat(database.executions().get(1).normalizedSql()).doesNotContain("status =").doesNotContain("note =");
            database.verifyComplete();
        }
    }

    @Test
    void deletesFindsAndListsStableViews() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            database.enqueueRows(2).enqueueRecord(record(MigrationInputStatus.CANDIDATE))
                    .enqueueRecord(record(MigrationInputStatus.CONFIRMED)).enqueueRecord(record(MigrationInputStatus.CANDIDATE));
            assertThat(repository.deleteBySourceType(PROJECT_ID, REVISION_ID, MigrationInputSourceType.KB_FINDING)).isEqualTo(2);
            assertThat(repository.findById(ID)).isPresent();
            assertThat(repository.confirmedRefs(PROJECT_ID, REVISION_ID)).hasSize(1);
            assertThat(repository.listAll(PROJECT_ID, REVISION_ID)).hasSize(1);
            assertThat(database.executions().get(2).normalizedSql()).contains("status =", "created_at asc", "id asc");
            assertThat(database.executions().get(3).normalizedSql()).contains("updated_at desc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void findsBySourceRefsShortCircuitsEmptyAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            MigrationInputRepository repository = new MigrationInputRepository(database.dsl());
            assertThat(repository.findBySourceRefs(PROJECT_ID, REVISION_ID, MigrationInputSourceType.KB_FINDING, null)).isEmpty();
            assertThat(repository.findBySourceRefs(PROJECT_ID, REVISION_ID, MigrationInputSourceType.KB_FINDING, List.of())).isEmpty();
            assertThat(database.executions()).isEmpty();
            database.enqueueRecord(record(MigrationInputStatus.CANDIDATE));
            assertThat(repository.findBySourceRefs(PROJECT_ID, REVISION_ID, MigrationInputSourceType.KB_FINDING, List.of(SOURCE_REF_ID)))
                    .containsKey(SOURCE_REF_ID);
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static MigrationInputCandidate candidate(MigrationInputStatus status, String location, String recommendation) {
        return new MigrationInputCandidate(PROJECT_ID, REVISION_ID, "SIMD issue", MigrationInputSourceType.KB_FINDING,
                SOURCE_REF_ID, "high", location, recommendation, "R1", "src/a.c", "fn", "anchor", "fp", status);
    }

    private static MigrationInputRefsRecord record(MigrationInputStatus status) {
        return new MigrationInputRefsRecord(ID, SET_ID, PROJECT_ID, REVISION_ID, "SIMD issue", MigrationInputSourceType.KB_FINDING.name(),
                SOURCE_REF_ID, "high", "src/a.c:4", "fix", status.name(), null, NOW, NOW, "R1", "src/a.c", "fn", "anchor", "fp");
    }
}
