package cn.rvport.backend.archive;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.ArchiveCandidatesRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class ArchiveCandidateRepositoryTests {

    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID RESOURCE_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID ARTIFACT_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void upsertsAndMapsSummaryAndArtifactReferences() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ArchiveCandidateRepository repository = repository(database);
            database.enqueueRecord(record(JSONB.valueOf("{\"count\":2}"), refsJson()));
            ArchiveArtifactRef ref = new ArchiveArtifactRef("json", ARTIFACT_ID, "SCAN_RESULT_JSON", "application/json", "result.json");
            ArchiveCandidateView view = repository.upsert(new ArchiveCandidateUpsertCommand(PROJECT_ID, REVISION_ID,
                    ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT, "latest", "KB_SCAN", RESOURCE_ID,
                    "KB report", Map.of("count", 2), List.of(ref)));
            assertThat(view.summary()).containsEntry("count", 2);
            assertThat(view.artifactRefs()).containsExactly(ref);
            assertThat(database.lastExecution().normalizedSql()).contains("on conflict", "candidate_key", "do update");
            database.verifyComplete();
        }
    }

    @Test
    void listsOnlyActiveCandidatesAndFallsBackForMalformedJson() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ArchiveCandidateRepository repository = repository(database);
            database.enqueueRecord(record(JSONB.valueOf("bad"), JSONB.valueOf("bad")));
            ArchiveCandidateView view = repository.listActive(PROJECT_ID, REVISION_ID).getFirst();
            assertThat(view.summary()).isEmpty();
            assertThat(view.artifactRefs()).isEmpty();
            assertThat(database.lastExecution().normalizedSql()).contains("status =", "node_type asc", "candidate_type asc", "updated_at desc");
            database.verifyComplete();
        }
    }

    @Test
    void mapsNullJsonAsEmptyCollections() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ArchiveCandidateRepository repository = repository(database);
            database.enqueueRecord(record(null, null));
            assertThat(repository.listActive(PROJECT_ID, REVISION_ID).getFirst())
                    .satisfies(view -> {
                        assertThat(view.summary()).isEmpty();
                        assertThat(view.artifactRefs()).isEmpty();
                    });
            database.verifyComplete();
        }
    }

    @Test
    void mapsBlankPayloadJsonAsEmptyCollections() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ArchiveCandidateRepository repository = repository(database);
            database.enqueueRecord(record(JSONB.valueOf(" "), JSONB.valueOf(" ")));
            assertThat(repository.listActive(PROJECT_ID, REVISION_ID).getFirst())
                    .satisfies(view -> {
                        assertThat(view.summary()).isEmpty();
                        assertThat(view.artifactRefs()).isEmpty();
                    });
            database.verifyComplete();
        }
    }

    @Test
    void rejectsNonSerializableValues() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            ArchiveCandidateRepository repository = new ArchiveCandidateRepository(database.dsl(), mapper);
            ArchiveCandidateUpsertCommand command = new ArchiveCandidateUpsertCommand(PROJECT_ID, REVISION_ID,
                    ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT, "latest", "KB_SCAN", RESOURCE_ID,
                    "KB report", Map.of("count", 2), List.of());
            assertThatThrownBy(() -> repository.upsert(command)).isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("not serializable");
            assertThat(database.executions()).isEmpty();
        }
    }

    private static ArchiveCandidateRepository repository(JooqMockDatabase database) {
        return new ArchiveCandidateRepository(database.dsl(), new ObjectMapper());
    }

    private static ArchiveCandidatesRecord record(JSONB summary, JSONB refs) {
        return new ArchiveCandidatesRecord(ID, PROJECT_ID, REVISION_ID, ArchiveNodeType.KB_SCAN.name(),
                ArchiveCandidateType.REPORT.name(), "latest", "KB_SCAN", RESOURCE_ID, "KB report", summary, refs,
                ArchiveCandidateStatus.ACTIVE.name(), NOW, NOW);
    }

    private static JSONB refsJson() {
        return JSONB.valueOf("[{\"format\":\"json\",\"storedArtifactId\":\"" + ARTIFACT_ID
                + "\",\"artifactType\":\"SCAN_RESULT_JSON\",\"contentType\":\"application/json\",\"filename\":\"result.json\"}]");
    }
}
