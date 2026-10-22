package cn.rvport.backend.project;

import static cn.rvport.backend.jooq.tables.BuildRuns.BUILD_RUNS;
import static cn.rvport.backend.jooq.tables.Findings.FINDINGS;
import static cn.rvport.backend.jooq.tables.KbScanRuns.KB_SCAN_RUNS;
import static cn.rvport.backend.jooq.tables.Projects.PROJECTS;
import static cn.rvport.backend.jooq.tables.TestRuns.TEST_RUNS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.ProjectsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class ProjectRepositoryTests {

    private static final UUID PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_PROJECT_ID = UUID.fromString("10000000-0000-0000-0000-000000000002");
    private static final UUID USER_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime CREATED_AT = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsFindsAndUpdatesProjects() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRepository repository = new ProjectRepository(database.dsl());
            ProjectsRecord created = projectRecord(PROJECT_ID, "demo", null);
            ProjectsRecord updated = projectRecord(PROJECT_ID, "renamed", ProjectSourceInputType.GIT.name());
            database.enqueueRecord(created).enqueueRecord(created).enqueueRecord(updated).enqueueRows(1).enqueueRows(1);

            ProjectView createdView = repository.create("demo", "description", "x86_64", "riscv64", USER_ID);
            ProjectView found = repository.findById(PROJECT_ID).orElseThrow();
            ProjectView updatedView = repository.update(
                    PROJECT_ID, "renamed", "new description", "x86_64", "riscv64", ProjectStatus.ARCHIVED);
            repository.updateStage(PROJECT_ID, ProjectStage.SOURCE_IMPORTED);
            repository.lockSourceInputTypeIfEmpty(PROJECT_ID, ProjectSourceInputType.GIT);

            assertThat(createdView.name()).isEqualTo("demo");
            assertThat(found.sourceInputType()).isNull();
            assertThat(updatedView.name()).isEqualTo("renamed");
            assertThat(updatedView.sourceInputType()).isEqualTo(ProjectSourceInputType.GIT);
            assertThat(database.executions()).hasSize(5);
            assertThat(database.executions().get(3).normalizedSql()).contains("update projects", "stage");
            assertThat(database.executions().get(4).normalizedSql()).contains("source_input_type is null");
            database.verifyComplete();
        }
    }

    @Test
    void returnsEmptyForMissingProjectAndNullForLostUpdateRace() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRepository repository = new ProjectRepository(database.dsl());
            database.enqueueResult(database.result(PROJECTS.fields())).enqueueResult(database.result(PROJECTS.fields()));

            assertThat(repository.findById(PROJECT_ID)).isEmpty();
            assertThat(repository.update(PROJECT_ID, "name", null, "x86_64", "riscv64", ProjectStatus.ACTIVE)).isNull();
            database.verifyComplete();
        }
    }

    @Test
    void appliesDynamicFiltersAccessControlAndPaging() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRepository repository = new ProjectRepository(database.dsl());
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{3L}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L}))
                    .enqueueRecord(projectRecord(PROJECT_ID, "demo", null))
                    .enqueueRecord(projectRecord(PROJECT_ID, "demo", null))
                    .enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{3L}));

            assertThat(repository.count(ProjectStatus.ACTIVE, ProjectStage.PROJECT_CREATED, " Demo ")).isEqualTo(3L);
            assertThat(repository.countAccessible(null, null, null, USER_ID, false)).isEqualTo(1L);
            assertThat(repository.list(ProjectStatus.ACTIVE, null, "demo", 2, 10)).hasSize(1);
            assertThat(repository.listAccessible(null, null, " ", 1, 20, USER_ID, true)).hasSize(1);
            assertThat(repository.countAccessible(null, null, null, USER_ID, true)).isEqualTo(3L);

            assertThat(database.executions().get(0).normalizedSql()).contains("status = ?", "stage = ?", "lower(projects.name)");
            assertThat(database.executions().get(1).normalizedSql()).contains("created_by = cast(? as uuid)");
            assertThat(database.executions().get(2).normalizedSql()).contains("offset ? rows");
            assertThat(database.executions().get(3).normalizedSql()).doesNotContain("created_by = ?");
            assertThat(database.executions().get(4).normalizedSql()).doesNotContain("created_by = ?");
            database.verifyComplete();
        }
    }

    @Test
    void aggregatesRiskScanAndLatestRunSummaries() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRepository repository = new ProjectRepository(database.dsl());
            OffsetDateTime kbTime = CREATED_AT.plusHours(1);
            database.enqueueResult(database.result(
                            new Field<?>[]{FINDINGS.PROJECT_ID, DSL.count()}, new Object[]{PROJECT_ID, 2}))
                    .enqueueResult(database.result(
                            new Field<?>[]{KB_SCAN_RUNS.PROJECT_ID, DSL.max(DSL.coalesce(KB_SCAN_RUNS.FINISHED_AT, KB_SCAN_RUNS.STARTED_AT))},
                            new Object[]{PROJECT_ID, kbTime}))
                    .enqueueResult(database.result(
                            new Field<?>[]{BUILD_RUNS.PROJECT_ID, BUILD_RUNS.STATUS},
                            new Object[]{PROJECT_ID, "SUCCEEDED"}, new Object[]{PROJECT_ID, "FAILED"}))
                    .enqueueResult(database.result(
                            new Field<?>[]{TEST_RUNS.PROJECT_ID, TEST_RUNS.STATUS},
                            new Object[]{PROJECT_ID, "RUNNING"}, new Object[]{PROJECT_ID, "SUCCEEDED"}));

            Map<UUID, ProjectSummaryView> summaries = repository.summaries(List.of(PROJECT_ID, OTHER_PROJECT_ID));

            assertThat(summaries.get(PROJECT_ID)).isEqualTo(
                    new ProjectSummaryView(2, kbTime, "SUCCEEDED", "RUNNING"));
            assertThat(summaries.get(OTHER_PROJECT_ID)).isEqualTo(
                    new ProjectSummaryView(0, null, null, null));
            assertThat(database.executions()).hasSize(4);
            database.verifyComplete();
        }
    }

    @Test
    void avoidsQueriesForEmptySummaryInputAndPropagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ProjectRepository repository = new ProjectRepository(database.dsl());
            assertThat(repository.summaries(List.of())).isEmpty();
            assertThat(database.executions()).isEmpty();

            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(PROJECT_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static ProjectsRecord projectRecord(UUID id, String name, String sourceInputType) {
        return new ProjectsRecord(
                id, name, "description", "x86_64", "riscv64", ProjectStage.PROJECT_CREATED.name(),
                ProjectStatus.ACTIVE.name(), USER_ID, CREATED_AT, CREATED_AT, null, sourceInputType);
    }
}
