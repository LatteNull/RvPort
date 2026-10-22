package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.TaskLogsRecord;
import cn.rvport.backend.jooq.tables.records.TaskScriptPayloadsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import cn.rvport.backend.testfixture.TestDataFixtures;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.exception.DataAccessException;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class TaskPayloadAndLogRepositoryTests {

    @Test
    void taskLogRepositoryCoversCreateFindListCountAndOptionalFilter() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskLogRepository repository = new TaskLogRepository(database.dsl());
            TaskLogsRecord record = logRecord();

            database.enqueueResult(database.result(
                    new Field<?>[] {DSL.field("count", Integer.class)}, new Object[] {1}));
            assertThat(repository.count(TestDataFixtures.TASK_ID, null)).isEqualTo(1);
            assertThat(database.lastExecution().normalizedSql()).doesNotContain("log_type = ?");

            database.enqueueRecord(record);
            assertThat(repository.list(TestDataFixtures.TASK_ID, TaskLogType.COMBINED, 2, 25))
                    .extracting(TaskLogResponse::lineCount).containsExactly(12L);
            assertThat(database.lastExecution().normalizedSql()).contains("log_type = ?");
            assertThat(database.lastExecution().bindings()).endsWith(25L, 25L);

            database.enqueueRecord(record);
            assertThat(repository.findForTask(TestDataFixtures.TASK_ID, record.getId())).contains(record);
            database.enqueueRecord(record);
            assertThat(repository.findLatest(TestDataFixtures.TASK_ID, TaskLogType.COMBINED)).isPresent();
            database.enqueueRecord(record);
            assertThat(repository.findLatestRecord(TestDataFixtures.TASK_ID, null)).contains(record);

            database.enqueueRecord(record);
            TaskLogResponse created = repository.create(TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    TaskLogType.COMBINED, "/tmp/task.log", 128, 12, "sha", "tail");
            assertThat(created.logType()).isEqualTo(TaskLogType.COMBINED);
            assertThat(database.lastExecution().normalizedSql()).contains("insert into task_logs").contains("line_count");
        }
    }

    @Test
    void taskLogRepositoryReturnsEmptyAndPropagatesFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskLogRepository repository = new TaskLogRepository(database.dsl());
            database.enqueueResult(database.result(cn.rvport.backend.jooq.tables.TaskLogs.TASK_LOGS.fields()));
            assertThat(repository.findLatest(TestDataFixtures.TASK_ID, null)).isEmpty();

            database.enqueueFailure(new SQLException("log query failed"));
            assertThatThrownBy(() -> repository.count(TestDataFixtures.TASK_ID, TaskLogType.STDERR))
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("log query failed");
        }
    }

    @Test
    void scriptPayloadRepositoryCreatesFindsAndHandlesMissingRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskScriptPayloadRepository repository = new TaskScriptPayloadRepository(database.dsl());
            TaskScriptPayloadsRecord record = scriptRecord();
            JSONB encrypted = record.getEncryptedPayload();

            database.enqueueRecord(record);
            TaskScriptPayloadView created = repository.create(record.getId(), record.getProjectId(), record.getTaskId(),
                    record.getScriptSha256(), record.getScriptLength(), encrypted, record.getKeyId(), record.getCreatedBy());
            assertThat(created.encryptedPayload()).isEqualTo(encrypted);
            assertThat(database.lastExecution().bindings())
                    .contains(record.getId(), record.getScriptSha256(), encrypted.data());

            database.enqueueRecord(record);
            assertThat(repository.findByIdAndTask(record.getId(), record.getProjectId(), record.getTaskId()))
                    .contains(created);

            database.enqueueResult(database.result(
                    cn.rvport.backend.jooq.tables.TaskScriptPayloads.TASK_SCRIPT_PAYLOADS.fields()));
            assertThat(repository.findByIdAndTask(UUID.randomUUID(), record.getProjectId(), record.getTaskId())).isEmpty();
        }
    }

    @Test
    void secretPayloadRepositoryCreatesFindsDeletesAndPropagatesFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            TaskSecretPayloadRepository repository = new TaskSecretPayloadRepository(database.dsl());
            UUID id = UUID.randomUUID();
            JSONB encrypted = JSONB.valueOf("{\"ciphertext\":\"abc\"}");
            Field<?>[] fields = secretFields();
            Object[] values = {id, TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID, "SSH_PASSWORD", "hash",
                    encrypted, "key-v1", TestDataFixtures.USER_ID, TestDataFixtures.NOW};

            database.enqueueResult(database.result(fields, values));
            TaskSecretPayloadView created = repository.create(id, TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                    "SSH_PASSWORD", "hash", encrypted, "key-v1", TestDataFixtures.USER_ID);
            assertThat(created.secretType()).isEqualTo("SSH_PASSWORD");
            assertThat(created.encryptedPayload()).isEqualTo(encrypted);

            database.enqueueResult(database.result(fields, values));
            assertThat(repository.findByIdAndTask(id, TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID, "SSH_PASSWORD"))
                    .contains(created);

            database.enqueueResult(database.result(fields));
            assertThat(repository.findByIdAndTask(UUID.randomUUID(), TestDataFixtures.PROJECT_ID,
                    TestDataFixtures.TASK_ID, "SSH_PASSWORD")).isEmpty();

            database.enqueueRows(2);
            assertThat(repository.deleteByTaskId(TestDataFixtures.TASK_ID)).isEqualTo(2);
            assertThat(database.lastExecution().normalizedSql()).contains("delete from task_secret_payloads");

            database.enqueueFailure(new SQLException("delete failed"));
            assertThatThrownBy(() -> repository.deleteByTaskId(TestDataFixtures.TASK_ID))
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("delete failed");
        }
    }

    private static TaskLogsRecord logRecord() {
        return new TaskLogsRecord(UUID.randomUUID(), TestDataFixtures.TASK_ID, TestDataFixtures.PROJECT_ID,
                TaskLogType.COMBINED.name(), "/tmp/task.log", 128L, "sha", "tail", TestDataFixtures.NOW, 12L);
    }

    private static TaskScriptPayloadsRecord scriptRecord() {
        return new TaskScriptPayloadsRecord(UUID.randomUUID(), TestDataFixtures.PROJECT_ID, TestDataFixtures.TASK_ID,
                "script-sha", 12, JSONB.valueOf("{\"ciphertext\":\"abc\"}"), "key-v1",
                TestDataFixtures.USER_ID, TestDataFixtures.NOW);
    }

    private static Field<?>[] secretFields() {
        return new Field<?>[] {
                DSL.field("id", UUID.class), DSL.field("project_id", UUID.class), DSL.field("task_id", UUID.class),
                DSL.field("secret_type", String.class), DSL.field("secret_sha256", String.class),
                DSL.field("encrypted_payload", JSONB.class), DSL.field("key_id", String.class),
                DSL.field("created_by", UUID.class), DSL.field("created_at", OffsetDateTime.class)
        };
    }
}
