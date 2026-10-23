package cn.rvport.backend.project.runtime;

import static cn.rvport.backend.jooq.tables.ProjectRuntimeEnvironments.PROJECT_RUNTIME_ENVIRONMENTS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.ProjectRuntimeEnvironmentsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ProjectRuntimeEnvironmentRepositoryTests {

    private static final UUID PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID SOURCE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID TARGET_ID = UUID.fromString("20000000-0000-0000-0000-000000000002");
    private static final UUID USER_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void findsUpsertsAndReadsCurrentVersion() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRuntimeEnvironmentRepository repository = new ProjectRuntimeEnvironmentRepository(database.dsl());
            ProjectRuntimeEnvironmentsRecord versionOne = record(1L);
            ProjectRuntimeEnvironmentsRecord versionTwo = record(2L);
            database.enqueueRecord(versionOne).enqueueRecord(versionTwo).enqueueRecord(versionTwo);

            assertThat(repository.find(PROJECT_ID).orElseThrow().version()).isEqualTo(1L);
            assertThat(repository.upsert(PROJECT_ID, SOURCE_ID, TARGET_ID, USER_ID, true).version()).isEqualTo(2L);
            assertThat(repository.currentVersion(PROJECT_ID)).isEqualTo(2L);

            String upsertSql = database.executions().get(1).normalizedSql();
            assertThat(upsertSql).contains("on conflict", "version + ?");
            database.verifyComplete();
        }
    }

    @Test
    void preservesVersionWhenSelectionDidNotChangeAndMapsNullVersionToZero() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRuntimeEnvironmentRepository repository = new ProjectRuntimeEnvironmentRepository(database.dsl());
            ProjectRuntimeEnvironmentsRecord nullVersion = record(null);
            database.enqueueRecord(nullVersion).enqueueResult(database.result(PROJECT_RUNTIME_ENVIRONMENTS.fields()));

            assertThat(repository.upsert(PROJECT_ID, SOURCE_ID, TARGET_ID, USER_ID, false).version()).isZero();
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("version + ?");
            assertThat(repository.currentVersion(PROJECT_ID)).isZero();
            database.verifyComplete();
        }
    }

    @Test
    void bumpsOnlySelectedEnvironmentsAndShortCircuitsEmptyCollections() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRuntimeEnvironmentRepository repository = new ProjectRuntimeEnvironmentRepository(database.dsl());

            assertThat(repository.bumpVersionIfAnySelected(PROJECT_ID, null, USER_ID)).isEmpty();
            assertThat(repository.bumpVersionIfAnySelected(PROJECT_ID, List.of(), USER_ID)).isEmpty();
            assertThat(database.executions()).isEmpty();

            database.enqueueRecord(record(3L)).enqueueResult(database.result(PROJECT_RUNTIME_ENVIRONMENTS.fields()));
            assertThat(repository.bumpVersionIfSelected(PROJECT_ID, SOURCE_ID, USER_ID).orElseThrow().version()).isEqualTo(3L);
            assertThat(repository.bumpVersionIfAnySelected(PROJECT_ID, List.of(UUID.randomUUID()), USER_ID)).isEmpty();
            assertThat(database.executions().get(0).normalizedSql()).contains("source_environment_id in", "target_environment_id in");
            database.verifyComplete();
        }
    }

    @Test
    void reportsSelectedEnvironmentAndPropagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRuntimeEnvironmentRepository repository = new ProjectRuntimeEnvironmentRepository(database.dsl());
            database.enqueueRows(1).enqueueRows(0).enqueueFailure(new SQLException("database unavailable"));

            assertThat(repository.isSelectedEnvironment(SOURCE_ID)).isTrue();
            assertThat(repository.isSelectedEnvironment(UUID.randomUUID())).isFalse();
            assertThatThrownBy(() -> repository.find(PROJECT_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static ProjectRuntimeEnvironmentsRecord record(Long version) {
        return new ProjectRuntimeEnvironmentsRecord(PROJECT_ID, SOURCE_ID, TARGET_ID, version, USER_ID, NOW, NOW);
    }
}
