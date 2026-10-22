package cn.rvport.backend.credential;

import static cn.rvport.backend.jooq.tables.Credentials.CREDENTIALS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.CredentialsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CredentialRepositoryTests {

    private static final UUID CREDENTIAL_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID PROJECT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsAndFindsCredentialMetadataWithoutExposingPayload() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            CredentialRepository repository = new CredentialRepository(database.dsl());
            CredentialsRecord record = record(CredentialStatus.ACTIVE);
            byte[] encrypted = {1, 2, 3};
            database.enqueueRecord(record).enqueueRecord(record).enqueueRecord(record);

            CredentialView created = repository.create(new CreateCredentialCommand(
                    PROJECT_ID, USER_ID, CredentialKind.SSH_KEY, "deploy", "SHA256:masked", Map.of("privateKey", "secret")),
                    encrypted, "key-v1");

            assertThat(created.id()).isEqualTo(CREDENTIAL_ID);
            assertThat(repository.findById(CREDENTIAL_ID)).contains(created);
            assertThat(repository.findActiveById(CREDENTIAL_ID)).contains(created);
            assertThat(database.executions().getFirst().bindings()).contains(encrypted, "SHA256:masked", "key-v1");
            database.verifyComplete();
        }
    }

    @Test
    void returnsEncryptedActiveCredentialAndChecksProjectOwnership() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            CredentialRepository repository = new CredentialRepository(database.dsl());
            byte[] encrypted = {9, 8, 7};
            database.enqueueResult(database.result(
                            new org.jooq.Field<?>[]{CREDENTIALS.KIND, CREDENTIALS.ENCRYPTED_PAYLOAD},
                            new Object[]{CredentialKind.SSH_PASSWORD.name(), encrypted}))
                    .enqueueRows(1).enqueueRows(0);

            CredentialRepository.EncryptedCredentialRecord result =
                    repository.findActiveEncryptedById(CREDENTIAL_ID).orElseThrow();
            assertThat(result.kind()).isEqualTo(CredentialKind.SSH_PASSWORD);
            assertThat(result.encryptedPayload()).containsExactly(encrypted);
            assertThat(repository.belongsToProject(CREDENTIAL_ID, PROJECT_ID)).isTrue();
            assertThat(repository.belongsToProject(CREDENTIAL_ID, UUID.randomUUID())).isFalse();
            database.verifyComplete();
        }
    }

    @Test
    void handlesMissingDisabledAndInvalidCredentialRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            CredentialRepository repository = new CredentialRepository(database.dsl());
            database.enqueueResult(database.result(CREDENTIALS.fields()))
                    .enqueueResult(database.result(CREDENTIALS.fields()))
                    .enqueueResult(database.result(new org.jooq.Field<?>[]{CREDENTIALS.KIND, CREDENTIALS.ENCRYPTED_PAYLOAD}))
                    .enqueueRows(1);

            assertThat(repository.findById(CREDENTIAL_ID)).isEmpty();
            assertThat(repository.findActiveById(CREDENTIAL_ID)).isEmpty();
            assertThat(repository.findActiveEncryptedById(CREDENTIAL_ID)).isEmpty();
            repository.disable(CREDENTIAL_ID);

            assertThat(database.lastExecution().normalizedSql()).contains("status = ?", "updated_at");
            database.verifyComplete();
        }
    }

    @Test
    void propagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            CredentialRepository repository = new CredentialRepository(database.dsl());
            database.enqueueFailure(new SQLException("database unavailable"));

            assertThatThrownBy(() -> repository.findById(CREDENTIAL_ID))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static CredentialsRecord record(CredentialStatus status) {
        return new CredentialsRecord(
                CREDENTIAL_ID, PROJECT_ID, USER_ID, CredentialKind.SSH_KEY.name(), "deploy", new byte[]{1, 2, 3},
                "SHA256:masked", "key-v1", status.name(), NOW, NOW);
    }
}
