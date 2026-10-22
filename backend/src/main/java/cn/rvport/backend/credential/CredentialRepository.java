package cn.rvport.backend.credential;

import static cn.rvport.backend.jooq.tables.Credentials.CREDENTIALS;

import cn.rvport.backend.jooq.tables.records.CredentialsRecord;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.Record2;
import org.springframework.stereotype.Repository;

@Repository
public class CredentialRepository {

    private final DSLContext dsl;

    public CredentialRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public CredentialView create(CreateCredentialCommand command, byte[] encryptedPayload, String kmsKeyVersion) {
        CredentialsRecord record = dsl.insertInto(CREDENTIALS)
                .set(CREDENTIALS.PROJECT_ID, command.projectId())
                .set(CREDENTIALS.OWNER_USER_ID, command.ownerUserId())
                .set(CREDENTIALS.KIND, command.kind().name())
                .set(CREDENTIALS.NAME, command.name())
                .set(CREDENTIALS.ENCRYPTED_PAYLOAD, encryptedPayload)
                .set(CREDENTIALS.MASKED_SUMMARY, command.maskedSummary())
                .set(CREDENTIALS.KMS_KEY_VERSION, kmsKeyVersion)
                .set(CREDENTIALS.STATUS, CredentialStatus.ACTIVE.name())
                .returning()
                .fetchOne();
        return CredentialView.from(record);
    }

    public Optional<CredentialView> findById(UUID credentialId) {
        return dsl.selectFrom(CREDENTIALS)
                .where(CREDENTIALS.ID.eq(credentialId))
                .fetchOptional()
                .map(CredentialView::from);
    }

    public Optional<CredentialView> findActiveById(UUID credentialId) {
        return dsl.selectFrom(CREDENTIALS)
                .where(CREDENTIALS.ID.eq(credentialId)
                        .and(CREDENTIALS.STATUS.eq(CredentialStatus.ACTIVE.name())))
                .fetchOptional()
                .map(CredentialView::from);
    }

    public Optional<EncryptedCredentialRecord> findActiveEncryptedById(UUID credentialId) {
        return dsl.select(CREDENTIALS.KIND, CREDENTIALS.ENCRYPTED_PAYLOAD)
                .from(CREDENTIALS)
                .where(CREDENTIALS.ID.eq(credentialId)
                        .and(CREDENTIALS.STATUS.eq(CredentialStatus.ACTIVE.name())))
                .fetchOptional(this::mapEncrypted);
    }

    public boolean belongsToProject(UUID credentialId, UUID projectId) {
        return dsl.fetchExists(
                CREDENTIALS,
                CREDENTIALS.ID.eq(credentialId)
                        .and(CREDENTIALS.PROJECT_ID.eq(projectId))
                        .and(CREDENTIALS.STATUS.eq(CredentialStatus.ACTIVE.name()))
        );
    }

    public void disable(UUID credentialId) {
        dsl.update(CREDENTIALS)
                .set(CREDENTIALS.STATUS, CredentialStatus.DISABLED.name())
                .set(CREDENTIALS.UPDATED_AT, OffsetDateTime.now())
                .where(CREDENTIALS.ID.eq(credentialId))
                .execute();
    }

    private EncryptedCredentialRecord mapEncrypted(Record2<String, byte[]> record) {
        return new EncryptedCredentialRecord(
                CredentialKind.valueOf(record.value1()),
                record.value2()
        );
    }

    public record EncryptedCredentialRecord(CredentialKind kind, byte[] encryptedPayload) {
    }
}
