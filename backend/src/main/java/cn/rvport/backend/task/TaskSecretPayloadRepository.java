package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class TaskSecretPayloadRepository {

    private static final Table<?> TABLE = DSL.table("task_secret_payloads");
    private static final Field<UUID> ID = DSL.field("id", UUID.class);
    private static final Field<UUID> PROJECT_ID = DSL.field("project_id", UUID.class);
    private static final Field<UUID> TASK_ID = DSL.field("task_id", UUID.class);
    private static final Field<String> SECRET_TYPE = DSL.field("secret_type", String.class);
    private static final Field<String> SECRET_SHA256 = DSL.field("secret_sha256", String.class);
    private static final Field<JSONB> ENCRYPTED_PAYLOAD = DSL.field("encrypted_payload", JSONB.class);
    private static final Field<String> KEY_ID = DSL.field("key_id", String.class);
    private static final Field<UUID> CREATED_BY = DSL.field("created_by", UUID.class);
    private static final Field<OffsetDateTime> CREATED_AT = DSL.field("created_at", OffsetDateTime.class);

    private final DSLContext dsl;

    public TaskSecretPayloadRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public TaskSecretPayloadView create(
            UUID id,
            UUID projectId,
            UUID taskId,
            String secretType,
            String secretSha256,
            JSONB encryptedPayload,
            String keyId,
            UUID createdBy
    ) {
        return dsl.insertInto(TABLE)
                .set(ID, id)
                .set(PROJECT_ID, projectId)
                .set(TASK_ID, taskId)
                .set(SECRET_TYPE, secretType)
                .set(SECRET_SHA256, secretSha256)
                .set(ENCRYPTED_PAYLOAD, encryptedPayload)
                .set(KEY_ID, keyId)
                .set(CREATED_BY, createdBy)
                .returning(ID, PROJECT_ID, TASK_ID, SECRET_TYPE, SECRET_SHA256, ENCRYPTED_PAYLOAD, KEY_ID, CREATED_BY, CREATED_AT)
                .fetchOne(this::map);
    }

    public Optional<TaskSecretPayloadView> findByIdAndTask(UUID id, UUID projectId, UUID taskId, String secretType) {
        return dsl.select(ID, PROJECT_ID, TASK_ID, SECRET_TYPE, SECRET_SHA256, ENCRYPTED_PAYLOAD, KEY_ID, CREATED_BY, CREATED_AT)
                .from(TABLE)
                .where(ID.eq(id)
                        .and(PROJECT_ID.eq(projectId))
                        .and(TASK_ID.eq(taskId))
                        .and(SECRET_TYPE.eq(secretType)))
                .fetchOptional(this::map);
    }

    public int deleteByTaskId(UUID taskId) {
        return dsl.deleteFrom(TABLE)
                .where(TASK_ID.eq(taskId))
                .execute();
    }

    private TaskSecretPayloadView map(org.jooq.Record record) {
        return new TaskSecretPayloadView(
                record.get(ID),
                record.get(PROJECT_ID),
                record.get(TASK_ID),
                record.get(SECRET_TYPE),
                record.get(SECRET_SHA256),
                record.get(ENCRYPTED_PAYLOAD),
                record.get(KEY_ID),
                record.get(CREATED_BY),
                record.get(CREATED_AT)
        );
    }
}
