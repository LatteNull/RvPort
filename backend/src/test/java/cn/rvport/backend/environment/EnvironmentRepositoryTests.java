package cn.rvport.backend.environment;

import static cn.rvport.backend.jooq.tables.EnvironmentSnapshots.ENVIRONMENT_SNAPSHOTS;
import static cn.rvport.backend.jooq.tables.Environments.ENVIRONMENTS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.EnvironmentSnapshotsRecord;
import cn.rvport.backend.jooq.tables.records.EnvironmentsRecord;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class EnvironmentRepositoryTests {

    private static final UUID ENVIRONMENT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID CREDENTIAL_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID SNAPSHOT_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsFindsAndMapsEnvironmentDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            EnvironmentsRecord record = environmentRecord(null, "/tmp/work", false);
            database.enqueueRecord(record).enqueueRecord(record).enqueueResult(database.result(ENVIRONMENTS.fields()));

            EnvironmentView created = repository.create(
                    PROJECT_ID, "source", EnvironmentRole.SOURCE_X86, "x86_64", "host", 22, "root",
                    CREDENTIAL_ID, null, "  /tmp/work  ", USER_ID);

            assertThat(created.workingDirectory()).isEqualTo("/tmp/work");
            assertThat(created.configVersion()).isEqualTo(1L);
            assertThat(created.enabled()).isFalse();
            assertThat(repository.findById(ENVIRONMENT_ID)).isEmpty();
            assertThat(database.executions().getFirst().bindings()).contains("/tmp/work");
            database.verifyComplete();
        }
    }

    @Test
    void countsListsAndSummarizesWithFilters() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(environmentRecord(2L, "/work", true))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{3L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{2L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}));

            assertThat(repository.count(PROJECT_ID, EnvironmentRole.SOURCE_X86, EnvironmentStatus.AVAILABLE, true)).isEqualTo(1L);
            assertThat(repository.list(PROJECT_ID, null, null, null, 2, 10)).singleElement()
                    .satisfies(view -> assertThat(view.configVersion()).isEqualTo(2L));
            assertThat(repository.summary(PROJECT_ID)).isEqualTo(new EnvironmentSummaryResponse(3, 2, 1, 1, 1));
            assertThat(database.executions().getFirst().normalizedSql()).contains("role = ?", "status = ?", "enabled = ?");
            assertThat(database.executions().get(1).normalizedSql()).contains("offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void updatesAndInvalidatesEffectiveConfigurations() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            EnvironmentsRecord updated = environmentRecord(3L, "/new", true);
            database.enqueueRecord(updated).enqueueRecord(updated)
                    .enqueueRows(2).enqueueRecord(updated);

            EnvironmentView result = repository.update(
                    ENVIRONMENT_ID, "updated", EnvironmentRole.TARGET_RISCV, "riscv64", "target", 2222, "root",
                    CREDENTIAL_ID, null, "/new", true, true);
            List<EnvironmentView> invalidated = repository.invalidateConfigurations(List.of(ENVIRONMENT_ID, UUID.randomUUID()));

            assertThat(result.configVersion()).isEqualTo(3L);
            assertThat(invalidated).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql())
                    .contains("config_version + ?", "last_connected_at = cast(?", "last_collected_at = cast(?");
            assertThat(database.executions().get(2).normalizedSql()).contains("case when environments.enabled");
            database.verifyComplete();
        }
    }

    @Test
    void updateWithoutEffectiveChangeCanLoseRaceAndEmptyInvalidationDoesNoIo() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(database.result(ENVIRONMENTS.fields()));

            assertThat(repository.update(
                    ENVIRONMENT_ID, "updated", EnvironmentRole.SOURCE_X86, "x86_64", "host", 22, "root",
                    CREDENTIAL_ID, null, " ", false, false)).isNull();
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("config_version + ?", "last_connected_at = ?");
            assertThat(repository.invalidateConfigurations(null)).isEmpty();
            assertThat(repository.invalidateConfigurations(List.of())).isEmpty();
            assertThat(database.executions()).hasSize(1);
            database.verifyComplete();
        }
    }

    @Test
    void findsJumpDependentsReferencesAndUsesOptimisticConfigVersionUpdates() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            database.enqueueRecord(environmentRecord(1L, null, true)).enqueueRows(1)
                    .enqueueRows(1).enqueueRows(0).enqueueRows(1).enqueueRows(0);

            assertThat(repository.findDirectDependents(ENVIRONMENT_ID)).hasSize(1);
            assertThat(repository.isReferencedAsJumpHost(ENVIRONMENT_ID)).isTrue();
            assertThat(repository.updateConnectionStatus(ENVIRONMENT_ID, 1, EnvironmentStatus.AVAILABLE, true)).isTrue();
            assertThat(repository.updateConnectionStatus(ENVIRONMENT_ID, 2, EnvironmentStatus.UNAVAILABLE, false)).isFalse();
            assertThat(repository.updateLastCollectedAt(ENVIRONMENT_ID, 1)).isTrue();
            assertThat(repository.updateLastCollectedAt(ENVIRONMENT_ID, 2)).isFalse();
            assertThat(database.executions().get(2).normalizedSql()).contains("last_connected_at");
            assertThat(database.executions().get(3).normalizedSql()).doesNotContain("last_connected_at");
            database.verifyComplete();
        }
    }

    @Test
    void createsSnapshotsAndBatchesComponentsAtOneThousandRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            database.enqueueResult(database.result(new Field<?>[]{ENVIRONMENT_SNAPSHOTS.ID}, new Object[]{SNAPSHOT_ID}))
                    .enqueueRows(1000).enqueueRows(1).enqueueRows(1);

            UUID snapshotId = repository.createSnapshot(
                    ENVIRONMENT_ID, PROJECT_ID, UUID.randomUUID(), "openEuler", "24.03", "6.6", "riscv64", "dnf",
                    Map.of("enabled", 2), Map.of("gcc", "13"), Map.of("snapshotKind", "FULL_COLLECT"),
                    TaskStatus.SUCCEEDED, NOW, 4L);
            List<EnvironmentRepository.ComponentInput> components = new ArrayList<>();
            for (int index = 0; index < 1001; index++) {
                components.add(new EnvironmentRepository.ComponentInput(
                        "package-" + index, "1", "PACKAGE", "riscv64", null, "repo", Map.of("index", index)));
            }
            repository.createComponents(SNAPSHOT_ID, PROJECT_ID, components);
            repository.createComponent(SNAPSHOT_ID, PROJECT_ID, "gcc", "13", "TOOL", "riscv64", "/usr/bin/gcc", "rpm", null);
            repository.createComponents(SNAPSHOT_ID, PROJECT_ID, null);
            repository.createComponents(SNAPSHOT_ID, PROJECT_ID, List.of());

            assertThat(snapshotId).isEqualTo(SNAPSHOT_ID);
            assertThat(database.executions()).hasSize(4);
            assertThat(database.executions().get(1).batchBindings()).hasSize(1000);
            assertThat(database.executions().get(2).batchBindings()).hasSize(1);
            database.verifyComplete();
        }
    }

    @Test
    void listsSnapshotsAndBuildsBasicInfoWithFallbackFields() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            EnvironmentSnapshotsRecord snapshot = snapshot(JSONB.valueOf("""
                    {"snapshotKind":"CONNECTION_CHECK","checkResults":{"basicTools":{"make":"ok"},
                    "workingDirectory":{"writable":true},"permissions":{"sudo":false}},"remoteUser":"root"}
                    """), JSONB.valueOf("{\"gcc\":\"13\"}"));
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(snapshot).enqueueRecord(snapshot);

            assertThat(repository.countSnapshots(ENVIRONMENT_ID)).isEqualTo(1L);
            assertThat(repository.listSnapshots(ENVIRONMENT_ID, 1, 20)).singleElement()
                    .satisfies(view -> assertThat(view.snapshotKind()).isEqualTo("CONNECTION_CHECK"));
            EnvironmentBasicInfoView info = repository.findLatestBasicInfo(ENVIRONMENT_ID, 4).orElseThrow();
            assertThat(info.snapshotKind()).isEqualTo("CONNECTION_CHECK");
            assertThat(info.basicTools().get("make")).isEqualTo("ok");
            assertThat(info.toolVersions().get("gcc")).isEqualTo("13");
            assertThat(info.remoteUser()).isEqualTo("root");
            database.verifyComplete();
        }
    }

    @Test
    void toleratesMissingAndMalformedSnapshotJsonAndSerializationFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper failingMapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(failingMapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            Mockito.when(failingMapper.readValue(Mockito.anyString(), Mockito.<com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>>any()))
                    .thenThrow(new JsonProcessingException("cannot parse") { });
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), failingMapper);
            EnvironmentSnapshotsRecord malformed = snapshot(JSONB.valueOf("not-json"), null);
            database.enqueueResult(database.result(new Field<?>[]{ENVIRONMENT_SNAPSHOTS.ID}, new Object[]{SNAPSHOT_ID}))
                    .enqueueRecord(malformed).enqueueResult(database.result(ENVIRONMENT_SNAPSHOTS.fields()));

            assertThat(repository.createSnapshot(
                    ENVIRONMENT_ID, PROJECT_ID, null, "os", "1", "kernel", "arch", "pm",
                    Map.of("x", 1), null, null, TaskStatus.SUCCEEDED, NOW, 1)).isEqualTo(SNAPSHOT_ID);
            EnvironmentBasicInfoView info = repository.findLatestBasicInfo(ENVIRONMENT_ID, 1).orElseThrow();
            assertThat(info.snapshotKind()).isEqualTo("FULL_COLLECT");
            assertThat(info.basicTools()).isEmpty();
            assertThat(info.remoteUser()).isEmpty();
            assertThat(repository.findLatestBasicInfo(ENVIRONMENT_ID, 2)).isEmpty();
            assertThat(database.executions().getFirst().bindings()).anySatisfy(value -> {
                if (value instanceof JSONB jsonb) assertThat(jsonb.data()).isEqualTo("{}");
            });
            database.verifyComplete();
        }
    }

    @Test
    void propagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            EnvironmentRepository repository = new EnvironmentRepository(database.dsl(), new ObjectMapper());
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ENVIRONMENT_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static EnvironmentsRecord environmentRecord(Long configVersion, String workingDirectory, boolean enabled) {
        return new EnvironmentsRecord(
                ENVIRONMENT_ID, PROJECT_ID, "source", EnvironmentRole.SOURCE_X86.name(), "x86_64", "host", 22,
                "root", CREDENTIAL_ID, workingDirectory, EnvironmentStatus.UNKNOWN.name(), enabled, null, null,
                USER_ID, NOW, NOW, null, configVersion);
    }

    private static EnvironmentSnapshotsRecord snapshot(JSONB raw, JSONB tools) {
        return new EnvironmentSnapshotsRecord(
                SNAPSHOT_ID, ENVIRONMENT_ID, PROJECT_ID, UUID.randomUUID(), "openEuler", "24.03", "6.6",
                "riscv64", "dnf", JSONB.valueOf("{}"), tools, raw, TaskStatus.SUCCEEDED.name(), NOW, 4L);
    }
}
