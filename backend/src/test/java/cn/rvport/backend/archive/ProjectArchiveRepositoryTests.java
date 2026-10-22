package cn.rvport.backend.archive;

import static cn.rvport.backend.jooq.tables.Archives.ARCHIVES;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.ArchiveItemsRecord;
import cn.rvport.backend.jooq.tables.records.ArchivesRecord;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class ProjectArchiveRepositoryTests {

    private static final UUID ARCHIVE_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID REVISION_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID TASK_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("60000000-0000-0000-0000-000000000001");
    private static final UUID CANDIDATE_ID = UUID.fromString("70000000-0000-0000-0000-000000000001");
    private static final UUID RESOURCE_ID = UUID.fromString("80000000-0000-0000-0000-000000000001");
    private static final UUID ARTIFACT_ID = UUID.fromString("90000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsFindsAndSelectsLatestArchives() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            database.enqueueRecord(archive(TaskStatus.PENDING, JSONB.valueOf("{}")))
                    .enqueueRecord(archive(TaskStatus.PENDING, JSONB.valueOf("bad")))
                    .enqueueRecord(archive(TaskStatus.PENDING, null))
                    .enqueueRecord(archive(TaskStatus.RUNNING, null))
                    .enqueueRecord(archive(TaskStatus.RUNNING, null));
            assertThat(repository.create(PROJECT_ID, REVISION_ID, TASK_ID, "snapshot", USER_ID).status()).isEqualTo(TaskStatus.PENDING);
            assertThat(repository.findById(ARCHIVE_ID).orElseThrow().summary()).isEmpty();
            assertThat(repository.findByTaskId(TASK_ID)).isPresent();
            assertThat(repository.latest(PROJECT_ID)).isPresent();
            assertThat(repository.latest(PROJECT_ID, REVISION_ID)).isPresent();
            assertThat(database.executions().get(3).normalizedSql()).contains("case", "created_at desc");
            database.verifyComplete();
        }
    }

    @Test
    void filtersCountsPaginatesAndCapsPageSize() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            ProjectArchiveListRequest request = new ProjectArchiveListRequest(0, 500, REVISION_ID, TaskStatus.SUCCEEDED,
                    NOW.minusDays(1), NOW.plusDays(1), "status", "asc");
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L})).enqueueRecord(archive(TaskStatus.SUCCEEDED, null));
            assertThat(repository.count(PROJECT_ID, request)).isEqualTo(1);
            assertThat(repository.list(PROJECT_ID, request)).hasSize(1);
            assertThat(request.normalizedPage()).isEqualTo(1);
            assertThat(request.normalizedPageSize()).isEqualTo(100);
            assertThat(database.executions().getFirst().normalizedSql()).contains("source_revision_id =", "status =", "created_at >=", "created_at <=");
            assertThat(database.executions().get(1).normalizedSql()).contains("status asc nulls last", "fetch next ? rows only");
            database.verifyComplete();
        }
    }

    @Test
    void supportsAllSortsAndRejectsUnknown() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            for (int index = 0; index < 3; index++) database.enqueueResult(database.result(ARCHIVES.fields()));
            for (String sort : new String[]{"createdAt", "name", ""}) repository.list(PROJECT_ID,
                    new ProjectArchiveListRequest(null, null, null, null, null, null, sort, "desc"));
            assertThat(database.executions().get(1).normalizedSql()).contains("name desc nulls last");
            assertThat(database.executions().get(2).normalizedSql()).contains("created_at desc", "id desc");
            assertThatThrownBy(() -> repository.list(PROJECT_ID,
                    new ProjectArchiveListRequest(1, 20, null, null, null, null, "size", "asc")))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("Unsupported archive sort field");
            database.verifyComplete();
        }
    }

    @Test
    void createsListsAndFindsArchiveItems() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            ArchiveArtifactRef ref = new ArchiveArtifactRef("json", ARTIFACT_ID, "REPORT_JSON", "application/json", "report.json");
            ArchiveCandidateView candidate = new ArchiveCandidateView(CANDIDATE_ID, PROJECT_ID, REVISION_ID,
                    ArchiveNodeType.MIGRATION_REPORT, ArchiveCandidateType.REPORT, "latest", "REPORT", RESOURCE_ID,
                    "Evaluation", Map.of("risk", "LOW"), List.of(ref), ArchiveCandidateStatus.ACTIVE, NOW, NOW);
            database.enqueueRecord(item(refsJson(), JSONB.valueOf("{\"risk\":\"LOW\"}")))
                    .enqueueRecord(item(refsJson(), JSONB.valueOf("bad")))
                    .enqueueRecord(item(null, null));
            assertThat(repository.createItem(ARCHIVE_ID, candidate).artifactRefs()).containsExactly(ref);
            assertThat(repository.listItems(ARCHIVE_ID).getFirst().metadata()).isEmpty();
            assertThat(repository.findItem(ARCHIVE_ID, ITEM_ID).orElseThrow().artifactRefs()).isEmpty();
            assertThat(database.executions().get(1).normalizedSql()).contains("node_type asc nulls last", "candidate_type asc nulls last");
            database.verifyComplete();
        }
    }

    @Test
    void mapsLegacyArchiveItemWithNullNodeAndCandidateTypes() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            ArchiveItemsRecord legacy = new ArchiveItemsRecord(ITEM_ID, ARCHIVE_ID, "LEGACY", RESOURCE_ID, null,
                    null, NOW, null, null, null, null, null, RESOURCE_ID, "legacy", null);
            database.enqueueRecord(legacy);
            assertThat(repository.findItem(ARCHIVE_ID, ITEM_ID).orElseThrow())
                    .satisfies(view -> {
                        assertThat(view.nodeType()).isNull();
                        assertThat(view.candidateType()).isNull();
                    });
            database.verifyComplete();
        }
    }

    @Test
    void updatesLifecycleAndHandlesMissingRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectArchiveRepository repository = repository(database);
            database.enqueueRecord(archive(TaskStatus.RUNNING, null))
                    .enqueueRecord(archive(TaskStatus.SUCCEEDED, JSONB.valueOf("{\"items\":2}")))
                    .enqueueRecord(archive(TaskStatus.FAILED, null))
                    .enqueueResult(database.result(ARCHIVES.fields()));
            assertThat(repository.markRunning(ARCHIVE_ID).status()).isEqualTo(TaskStatus.RUNNING);
            assertThat(repository.markSucceeded(ARCHIVE_ID, ARTIFACT_ID, 42, "abc", Map.of("items", 2)).summary()).containsEntry("items", 2);
            assertThat(repository.markFailed(ARCHIVE_ID, Map.of("error", true)).status()).isEqualTo(TaskStatus.FAILED);
            assertThat(repository.markRunning(ARCHIVE_ID)).isNull();
            database.verifyComplete();
        }
    }

    @Test
    void rejectsNonSerializableJsonAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any())).thenThrow(new JsonProcessingException("bad") { });
            ProjectArchiveRepository repository = new ProjectArchiveRepository(database.dsl(), mapper);
            assertThatThrownBy(() -> repository.markFailed(ARCHIVE_ID, Map.of("bad", true)))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("not serializable");
            assertThat(database.executions()).isEmpty();
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ARCHIVE_ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static ProjectArchiveRepository repository(JooqMockDatabase database) {
        return new ProjectArchiveRepository(database.dsl(), new ObjectMapper());
    }

    private static ArchivesRecord archive(TaskStatus status, JSONB summary) {
        return new ArchivesRecord(ARCHIVE_ID, PROJECT_ID, TASK_ID, "snapshot", status.name(), summary, null, 42L,
                "abc", USER_ID, NOW, REVISION_ID, ARTIFACT_ID, NOW);
    }

    private static ArchiveItemsRecord item(JSONB refs, JSONB metadata) {
        return new ArchiveItemsRecord(ITEM_ID, ARCHIVE_ID, ArchiveNodeType.MIGRATION_REPORT.name(), RESOURCE_ID, null,
                metadata, NOW, CANDIDATE_ID, ArchiveNodeType.MIGRATION_REPORT.name(), ArchiveCandidateType.REPORT.name(),
                "latest", "REPORT", RESOURCE_ID, "Evaluation", refs);
    }

    private static JSONB refsJson() {
        return JSONB.valueOf("[{\"format\":\"json\",\"storedArtifactId\":\"" + ARTIFACT_ID
                + "\",\"artifactType\":\"REPORT_JSON\",\"contentType\":\"application/json\",\"filename\":\"report.json\"}]");
    }
}
