package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import java.util.List;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class ScriptExecutionRepositoryTests {

    @Test
    void countsWithStatusEnvironmentAndKeywordFilters() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ScriptExecutionRepository repository = new ScriptExecutionRepository(database.dsl());
            for (ScriptExecutionStatus status : ScriptExecutionStatus.values()) {
                database.enqueueResult(database.result(new Field<?>[] {DSL.field("count", Integer.class)},
                        new Object[] {1}));
                ScriptExecutionListRequest request = new ScriptExecutionListRequest(status,
                        TestDataFixtures.ENVIRONMENT_ID, " target ", null, null, null);
                assertThat(repository.count(TestDataFixtures.PROJECT_ID, request)).isEqualTo(1);
                assertThat(database.lastExecution().normalizedSql())
                        .contains("environmentId")
                        .contains("lower(environments.name) like ?");
                assertThat(database.lastExecution().bindings()).contains("%target%");
            }
            assertThat(database.executions().get(0).normalizedSql()).contains("tasks.status in (?, ?, ?)");
            assertThat(database.executions().get(1).normalizedSql()).contains("tasks.status = ?");
            assertThat(database.executions().get(2).normalizedSql()).contains("tasks.status in (?, ?, ?)");
        }
    }

    @Test
    void listsRowsForEverySupportedSortAndAppliesDefaults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ScriptExecutionRepository repository = new ScriptExecutionRepository(database.dsl());
            List<String> sorts = List.of("createdAt.asc", "status.asc", "status.desc",
                    "environmentName.asc", "environmentName.desc", "unknown");
            for (String sort : sorts) {
                database.enqueueResult(database.result(rowFields(), rowValues()));
                ScriptExecutionRepository.Row row = repository.list(TestDataFixtures.PROJECT_ID,
                        new ScriptExecutionListRequest(null, null, " ", sort, 2, 10)).getFirst();
                assertThat(row.environmentName()).isEqualTo("target");
                assertThat(row.taskStatus()).isEqualTo(TaskStatus.SUCCEEDED);
                assertThat(row.logEventCount()).isEqualTo(0);
                assertThat(database.lastExecution().bindings()).endsWith(10L, 10L);
            }
            assertThat(database.executions().get(0).normalizedSql()).contains("tasks.created_at asc");
            assertThat(database.executions().get(1).normalizedSql()).contains("tasks.status asc");
            assertThat(database.executions().get(2).normalizedSql()).contains("tasks.status desc");
            assertThat(database.executions().get(3).normalizedSql()).contains("environments.name asc nulls last");
            assertThat(database.executions().get(4).normalizedSql()).contains("environments.name desc nulls last");
            assertThat(database.executions().get(5).normalizedSql()).contains("tasks.created_at desc");

            ScriptExecutionListRequest defaults = new ScriptExecutionListRequest(null, null, null, " ", null, null);
            assertThat(defaults.normalizedPage()).isEqualTo(1);
            assertThat(defaults.normalizedPageSize()).isEqualTo(20);
            assertThat(defaults.normalizedSort()).isEqualTo("createdAt.desc");
        }
    }

    @Test
    void findsDetailAndMapsToolSummaryOrReturnsEmpty() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ScriptExecutionRepository repository = new ScriptExecutionRepository(database.dsl());
            Field<?>[] fields = detailFields();
            Object[] values = detailValues();
            database.enqueueResult(database.result(fields, values));

            ScriptExecutionRepository.DetailRow detail = repository.findDetail(TestDataFixtures.TASK_ID).orElseThrow();
            assertThat(detail.toolName()).isEqualTo("bash");
            assertThat(detail.summary().data()).contains("ok");
            assertThat(detail.row().logEventCount()).isEqualTo(4);

            database.enqueueResult(database.result(fields));
            assertThat(repository.findDetail(UUID.randomUUID())).isEmpty();
        }
    }

    @Test
    void mapsExecutionStatusFamilies() {
        assertThat(ScriptExecutionStatus.fromTaskStatus(TaskStatus.PENDING)).isEqualTo(ScriptExecutionStatus.RUNNING);
        assertThat(ScriptExecutionStatus.fromTaskStatus(TaskStatus.SUCCEEDED)).isEqualTo(ScriptExecutionStatus.SUCCEEDED);
        assertThat(ScriptExecutionStatus.fromTaskStatus(TaskStatus.FAILED)).isEqualTo(ScriptExecutionStatus.ERROR);
        assertThat(ScriptExecutionStatus.fromTaskStatus(TaskStatus.TIMEOUT)).isEqualTo(ScriptExecutionStatus.ERROR);
        assertThat(ScriptExecutionStatus.fromTaskStatus(TaskStatus.CANCELLED)).isEqualTo(ScriptExecutionStatus.ERROR);
    }

    private static Field<?>[] rowFields() {
        var tasks = cn.rvport.backend.jooq.tables.Tasks.TASKS;
        return new Field<?>[] {tasks.ID, tasks.PROJECT_ID, DSL.field("environment_id", UUID.class),
                DSL.field("environment_name", String.class), tasks.STATUS, tasks.PROGRESS, tasks.MESSAGE,
                DSL.field("script_sha256", String.class), DSL.field("script_length", Integer.class),
                DSL.field("exit_code", Integer.class), DSL.field("log_event_count", Integer.class),
                tasks.CREATED_AT, tasks.STARTED_AT, tasks.FINISHED_AT};
    }

    private static Object[] rowValues() {
        return new Object[] {TestDataFixtures.TASK_ID, TestDataFixtures.PROJECT_ID, TestDataFixtures.ENVIRONMENT_ID,
                "target", TaskStatus.SUCCEEDED.name(), 100, "done", "sha", 42, 0, null,
                TestDataFixtures.NOW, TestDataFixtures.NOW, TestDataFixtures.NOW};
    }

    private static Field<?>[] detailFields() {
        var tasks = cn.rvport.backend.jooq.tables.Tasks.TASKS;
        var tools = cn.rvport.backend.jooq.tables.ToolRuns.TOOL_RUNS;
        return new Field<?>[] {tasks.ID, tasks.PROJECT_ID, DSL.field("environment_id", UUID.class),
                DSL.field("environment_name", String.class), tasks.STATUS, tasks.PROGRESS, tasks.MESSAGE,
                DSL.field("script_sha256", String.class), DSL.field("script_length", Integer.class),
                DSL.field("tool_run_id", UUID.class), tools.TOOL_NAME, tools.EXIT_CODE, tools.SUMMARY,
                DSL.field("log_event_count", Integer.class), tasks.CREATED_AT, tasks.STARTED_AT, tasks.FINISHED_AT};
    }

    private static Object[] detailValues() {
        return new Object[] {TestDataFixtures.TASK_ID, TestDataFixtures.PROJECT_ID,
                TestDataFixtures.ENVIRONMENT_ID, "target", TaskStatus.SUCCEEDED.name(), 100, "done", "sha", 42,
                UUID.randomUUID(), "bash", 0, JSONB.valueOf("{\"ok\":true}"), 4,
                TestDataFixtures.NOW, TestDataFixtures.NOW, TestDataFixtures.NOW};
    }
}
