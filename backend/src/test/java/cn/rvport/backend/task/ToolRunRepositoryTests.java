package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class ToolRunRepositoryTests {

    @Test
    void createsAndFinishesToolRunWithJsonSummary() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UUID id = UUID.randomUUID();
            database.enqueueResult(database.result(new Field<?>[] {
                    cn.rvport.backend.jooq.tables.ToolRuns.TOOL_RUNS.ID
            }, new Object[] {id}));
            ToolRunRepository repository = new ToolRunRepository(database.dsl(), new ObjectMapper());

            assertThat(repository.create(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    "make", "4.4", "make test", TaskStatus.RUNNING, TestDataFixtures.NOW)).isEqualTo(id);
            assertThat(database.lastExecution().bindings()).contains("make", "4.4", "make test", "RUNNING");

            database.enqueueRows(1);
            repository.finish(id, TaskStatus.SUCCEEDED, 0, Map.of("tests", 3));
            assertThat(database.lastExecution().bindings()).contains("SUCCEEDED", 0, "{\"tests\":3}");
        }
    }

    @Test
    void handlesNullAndSerializationFailureWithEmptySummary() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            database.enqueueRows(1);
            new ToolRunRepository(database.dsl(), new ObjectMapper())
                    .finish(UUID.randomUUID(), TaskStatus.FAILED, null, null);
            assertThat(database.lastExecution().bindings()).contains("{}");

            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("boom") { });
            database.enqueueRows(1);
            new ToolRunRepository(database.dsl(), mapper)
                    .finish(UUID.randomUUID(), TaskStatus.FAILED, 1, Map.of("bad", true));
            assertThat(database.lastExecution().bindings()).contains("{}");
        }
    }
}
