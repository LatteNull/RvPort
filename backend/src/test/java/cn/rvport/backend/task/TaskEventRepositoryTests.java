package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.TaskEventsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class TaskEventRepositoryTests {

    @Test
    void appendsTaskEventWithTaskMetadataAndParsedPayload() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskEventRepository repository = new TaskEventRepository(database.dsl(), new ObjectMapper());
            enqueueMetadata(database);
            database.enqueueRecord(eventRecord(JSONB.valueOf("{\"type\":\"BUILD\",\"id\":\""
                    + TestDataFixtures.TASK_ID + "\"}"), JSONB.valueOf("[\"status\"]")));
            enqueueMetadata(database);

            TaskEventView event = repository.append(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    TaskEventType.PROGRESS, TaskStatus.RUNNING, 50, "working", "INFO", "line");

            assertThat(event.taskType()).isEqualTo("KB_SCAN");
            assertThat(event.stageId()).isEqualTo("KB_SCAN");
            assertThat(event.resource().type()).isEqualTo("BUILD");
            assertThat(event.changedFields()).containsExactly("status");
            assertThat(database.executions()).hasSize(3);
            assertThat(database.executions().get(1).normalizedSql()).contains("insert into task_events");
        }
    }

    @Test
    void appendsProjectContextEventWithoutTaskLookupAndNormalizesBlankStage() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskEventResource resource = TaskEventResource.of("PROJECT", TestDataFixtures.PROJECT_ID);
            database.enqueueRecord(new TaskEventsRecord(2L, "evt-2", TestDataFixtures.PROJECT_ID, null,
                    TaskEventType.PROJECT_CONTEXT_CHANGED.value(), null, null, "changed", null, null,
                    TestDataFixtures.NOW, null, JSONB.valueOf("{}"), JSONB.valueOf("[]")));

            TaskEventView event = new TaskEventRepository(database.dsl(), new ObjectMapper())
                    .appendProjectContextChanged(TestDataFixtures.PROJECT_ID, " ", resource,
                            List.of("environment"), "changed");

            assertThat(event.taskId()).isNull();
            assertThat(database.executions()).hasSize(1);
            assertThat(database.lastExecution().bindings()).containsNull()
                    .anySatisfy(value -> assertThat(String.valueOf(value)).contains("environment"));
        }
    }

    @Test
    void listsAndFindsEventsWithFallbackForInvalidMetadata() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskEventRepository repository = new TaskEventRepository(database.dsl(), new ObjectMapper());
            TaskEventsRecord invalid = eventRecord(JSONB.valueOf("not-json"), JSONB.valueOf("not-json"));
            database.enqueueResult(joinedEvent(database, invalid));
            TaskEventView listed = repository.listAfter(TestDataFixtures.PROJECT_ID, 0, 10).getFirst();
            assertThat(listed.resource().type()).isEqualTo("KB_SCAN_RUN");
            assertThat(listed.changedFields()).isEmpty();

            TaskEventsRecord empty = eventRecord(null, null);
            database.enqueueResult(joinedEvent(database, empty));
            assertThat(repository.findByProjectIdAndId(TestDataFixtures.PROJECT_ID, 1))
                    .get().extracting(value -> value.resource().type()).isEqualTo("KB_SCAN_RUN");

            database.enqueueResult(database.result(new Field<?>[] {
                    cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.ID
            }, new Object[] {8L}));
            assertThat(repository.latestId(TestDataFixtures.PROJECT_ID)).isEqualTo(8);
            database.enqueueResult(database.result(new Field<?>[] {
                    cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.ID
            }));
            assertThat(repository.latestId(TestDataFixtures.PROJECT_ID)).isZero();
        }
    }

    @Test
    void toleratesMissingTaskAndJsonSerializationFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            ObjectMapper mapper = Mockito.mock(ObjectMapper.class);
            Mockito.when(mapper.writeValueAsString(Mockito.any()))
                    .thenThrow(new JsonProcessingException("cannot serialize") { });
            Mockito.when(mapper.readValue(Mockito.anyString(), Mockito.eq(TaskEventResource.class)))
                    .thenThrow(new JsonProcessingException("cannot parse") { });
            database.enqueueResult(database.result(metadataFields()));
            database.enqueueRecord(eventRecord(JSONB.valueOf("{}"), JSONB.valueOf("[]")));
            database.enqueueResult(database.result(metadataFields()));

            TaskEventView event = new TaskEventRepository(database.dsl(), mapper).append(
                    TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID, TaskEventType.STARTED,
                    TaskStatus.RUNNING, null, null, null, null);

            assertThat(event.taskType()).isNull();
            assertThat(event.resource()).isEqualTo(TaskEventResource.empty());
            assertThat(database.executions().get(1).bindings()).contains("{}", "[]");
        }
    }

    @Test
    void appendsTasklessEventAndFallsBackForEmptyResourcePayload() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            database.enqueueRecord(new TaskEventsRecord(3L, "evt-3", TestDataFixtures.PROJECT_ID, null,
                    TaskEventType.CREATED.value(), null, null, null, null, null, TestDataFixtures.NOW, null,
                    JSONB.valueOf("{}"), JSONB.valueOf(" ")));
            TaskEventView event = new TaskEventRepository(database.dsl(), new ObjectMapper()).append(
                    TestDataFixtures.PROJECT_ID, null, TaskEventType.CREATED, null, null, null, null, null);
            assertThat(event.taskType()).isNull();
            assertThat(event.resource()).isEqualTo(TaskEventResource.empty());
            assertThat(event.changedFields()).isEmpty();
            assertThat(database.executions()).hasSize(1);
            database.verifyComplete();
        }
    }

    @Test
    void mapsBlankJoinedMetadataAndUsesTaskIdWhenResourceIdIsMissing() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskEventsRecord event = eventRecord(JSONB.valueOf(" "), JSONB.valueOf(null));
            database.enqueueResult(joinedEvent(database, event,
                    new Object[]{"KB_SCAN", "KB_SCAN", " ", null, null, null}));
            TaskEventView view = new TaskEventRepository(database.dsl(), new ObjectMapper())
                    .listAfter(TestDataFixtures.PROJECT_ID, 0, 10).getFirst();
            assertThat(view.resource().type()).isEqualTo("KB_SCAN");
            assertThat(view.resource().id()).isEqualTo(TestDataFixtures.TASK_ID);
            assertThat(view.changedFields()).isEmpty();
            database.verifyComplete();
        }
    }

    @Test
    void keepsPartiallySpecifiedEventResourceInsteadOfReplacingIt() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskEventsRecord event = eventRecord(JSONB.valueOf("{\"id\":\"" + TestDataFixtures.TASK_ID + "\"}"),
                    JSONB.valueOf("[]"));
            database.enqueueResult(joinedEvent(database, event));
            TaskEventView view = new TaskEventRepository(database.dsl(), new ObjectMapper())
                    .listAfter(TestDataFixtures.PROJECT_ID, 0, 10).getFirst();
            assertThat(view.resource().type()).isNull();
            assertThat(view.resource().id()).isEqualTo(TestDataFixtures.TASK_ID);
            database.verifyComplete();
        }
    }

    @Test
    void appendsProjectContextWithNullOptionalPayloads() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            database.enqueueRecord(new TaskEventsRecord(4L, "evt-4", TestDataFixtures.PROJECT_ID, null,
                    TaskEventType.PROJECT_CONTEXT_CHANGED.value(), null, null, "changed", null, null,
                    TestDataFixtures.NOW, null, JSONB.valueOf("{}"), JSONB.valueOf("[]")));
            TaskEventView view = new TaskEventRepository(database.dsl(), new ObjectMapper())
                    .appendProjectContextChanged(TestDataFixtures.PROJECT_ID, null, null, null, "changed");
            assertThat(view.resource()).isEqualTo(TaskEventResource.empty());
            assertThat(view.changedFields()).isEmpty();
            assertThat(database.lastExecution().bindings()).anySatisfy(value -> assertThat(String.valueOf(value)).isEqualTo("{}"))
                    .anySatisfy(value -> assertThat(String.valueOf(value)).isEqualTo("[]"));
            database.verifyComplete();
        }
    }

    @Test
    void fallsBackToTaskTypeAndIdWhenTaskResourceMetadataIsMissing() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            Object[] metadata = {"KB_SCAN", "KB_SCAN", null, null, null, null};
            database.enqueueResult(database.result(metadataFields(), metadata))
                    .enqueueRecord(eventRecord(JSONB.valueOf("{}"), JSONB.valueOf("[]")))
                    .enqueueResult(database.result(metadataFields(), metadata));
            TaskEventView view = new TaskEventRepository(database.dsl(), new ObjectMapper()).append(
                    TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID, TaskEventType.STARTED,
                    TaskStatus.RUNNING, null, null, null, null);
            assertThat(view.resource().type()).isEqualTo("KB_SCAN");
            assertThat(view.resource().id()).isEqualTo(TestDataFixtures.TASK_ID);
            database.verifyComplete();
        }
    }

    private static void enqueueMetadata(JooqMockDatabase database) {
        database.enqueueResult(database.result(metadataFields(), new Object[] {
                "KB_SCAN", "KB_SCAN", "KB_SCAN_RUN", TestDataFixtures.TASK_ID, "ALL", "TARGET_RISCV"
        }));
    }

    private static Field<?>[] metadataFields() {
        var tasks = cn.rvport.backend.jooq.tables.Tasks.TASKS;
        return new Field<?>[] {tasks.TYPE, tasks.STAGE_ID, tasks.RESOURCE_TYPE, tasks.RESOURCE_ID,
                tasks.RESOURCE_MODE, tasks.ENVIRONMENT_ROLE};
    }

    private static org.jooq.Result<org.jooq.Record> joinedEvent(
            JooqMockDatabase database, TaskEventsRecord event) {
        return joinedEvent(database, event,
                new Object[]{"KB_SCAN", "KB_SCAN", "KB_SCAN_RUN", TestDataFixtures.TASK_ID, "ALL", "TARGET_RISCV"});
    }

    private static org.jooq.Result<org.jooq.Record> joinedEvent(
            JooqMockDatabase database, TaskEventsRecord event, Object[] taskValues) {
        Field<?>[] metadata = metadataFields();
        Field<?>[] fields = new Field<?>[cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.fields().length + metadata.length];
        System.arraycopy(cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.fields(), 0, fields, 0,
                cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.fields().length);
        System.arraycopy(metadata, 0, fields, cn.rvport.backend.jooq.tables.TaskEvents.TASK_EVENTS.fields().length,
                metadata.length);
        Object[] values = new Object[fields.length];
        System.arraycopy(event.intoArray(), 0, values, 0, event.size());
        System.arraycopy(taskValues, 0, values, event.size(), taskValues.length);
        return database.result(fields, values);
    }

    private static TaskEventsRecord eventRecord(JSONB resource, JSONB changedFields) {
        return new TaskEventsRecord(1L, "evt-1", TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                TaskEventType.PROGRESS.value(), TaskStatus.RUNNING.name(), 50, "working", "INFO", "line",
                TestDataFixtures.NOW, null, resource, changedFields);
    }
}
