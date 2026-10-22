package cn.rvport.backend.artifact;

import static cn.rvport.backend.jooq.tables.StoredArtifacts.STORED_ARTIFACTS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.StoredArtifactsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class StoredArtifactRepositoryTests {

    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID OWNER_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void findsByIdentityAndOwnerAndListsInStableOrder() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            StoredArtifactRepository repository = repository(database);
            database.enqueueRecord(record(JSONB.valueOf("{\"count\":2}")))
                    .enqueueRecord(record(JSONB.valueOf("bad")))
                    .enqueueRecord(record(null));
            assertThat(repository.findById(ID).orElseThrow().summary()).containsEntry("count", 2);
            assertThat(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, OWNER_ID, "SCAN_RESULT_JSON").orElseThrow().summary()).isEmpty();
            assertThat(repository.listByOwner(StoredArtifactOwnerType.KB_SCAN, OWNER_ID)).hasSize(1);
            assertThat(database.executions().get(1).normalizedSql()).contains("owner_type =", "owner_id =", "artifact_type =");
            assertThat(database.executions().get(2).normalizedSql()).contains("created_at desc", "artifact_type asc");
            database.verifyComplete();
        }
    }

    @Test
    void upsertsAndMapsReturnedArtifact() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            StoredArtifactRepository repository = repository(database);
            database.enqueueRecord(record(JSONB.valueOf("{\"count\":1}")));
            StoredArtifactView view = repository.upsert(ID, PROJECT_ID, TASK_ID, StoredArtifactOwnerType.KB_SCAN,
                    OWNER_ID, "SCAN_RESULT_JSON", "rvport", "kb/result.json", "application/json", 42, "abc", Map.of("count", 1));
            assertThat(view.id()).isEqualTo(ID);
            assertThat(view.summary()).containsEntry("count", 1);
            assertThat(database.lastExecution().normalizedSql()).contains("on conflict", "owner_type", "owner_id", "artifact_type", "do update");
            database.verifyComplete();
        }
    }

    @Test
    void rejectsNonSerializableSummaryWithoutTouchingDatabase() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            StoredArtifactRepository repository = new StoredArtifactRepository(database.dsl(), mapper);
            assertThatThrownBy(() -> repository.upsert(ID, PROJECT_ID, TASK_ID, StoredArtifactOwnerType.KB_SCAN,
                    OWNER_ID, "JSON", "bucket", "key", "application/json", 1, "sha", Map.of("bad", true)))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("not JSON serializable");
            assertThat(database.executions()).isEmpty();
        }
    }

    @Test
    void deletesByIdAndProjectAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            StoredArtifactRepository repository = repository(database);
            database.enqueueRows(1).enqueueRows(2);
            repository.delete(ID);
            repository.deleteByProject(PROJECT_ID);
            assertThat(database.executions().getFirst().normalizedSql()).contains("where stored_artifacts.id =");
            assertThat(database.executions().get(1).normalizedSql()).contains("where stored_artifacts.project_id =");
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static StoredArtifactRepository repository(JooqMockDatabase database) {
        return new StoredArtifactRepository(database.dsl(), new ObjectMapper());
    }

    private static StoredArtifactsRecord record(JSONB summary) {
        return new StoredArtifactsRecord(ID, PROJECT_ID, TASK_ID, StoredArtifactOwnerType.KB_SCAN.name(), OWNER_ID,
                "SCAN_RESULT_JSON", "rvport", "kb/result.json", "application/json", 42L, "abc", summary, NOW);
    }
}
