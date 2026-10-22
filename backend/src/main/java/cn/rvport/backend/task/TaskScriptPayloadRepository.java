package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.TaskScriptPayloads.TASK_SCRIPT_PAYLOADS;

import cn.rvport.backend.jooq.tables.records.TaskScriptPayloadsRecord;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Repository;

@Repository
public class TaskScriptPayloadRepository {

    private final DSLContext dsl;

    public TaskScriptPayloadRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public TaskScriptPayloadView create(
            UUID id,
            UUID projectId,
            UUID taskId,
            String scriptSha256,
            int scriptLength,
            JSONB encryptedPayload,
            String keyId,
            UUID createdBy
    ) {
        TaskScriptPayloadsRecord record = dsl.insertInto(TASK_SCRIPT_PAYLOADS)
                .set(TASK_SCRIPT_PAYLOADS.ID, id)
                .set(TASK_SCRIPT_PAYLOADS.PROJECT_ID, projectId)
                .set(TASK_SCRIPT_PAYLOADS.TASK_ID, taskId)
                .set(TASK_SCRIPT_PAYLOADS.SCRIPT_SHA256, scriptSha256)
                .set(TASK_SCRIPT_PAYLOADS.SCRIPT_LENGTH, scriptLength)
                .set(TASK_SCRIPT_PAYLOADS.ENCRYPTED_PAYLOAD, encryptedPayload)
                .set(TASK_SCRIPT_PAYLOADS.KEY_ID, keyId)
                .set(TASK_SCRIPT_PAYLOADS.CREATED_BY, createdBy)
                .returning()
                .fetchOne();
        return TaskScriptPayloadView.from(record);
    }

    public Optional<TaskScriptPayloadView> findByIdAndTask(UUID id, UUID projectId, UUID taskId) {
        return dsl.selectFrom(TASK_SCRIPT_PAYLOADS)
                .where(TASK_SCRIPT_PAYLOADS.ID.eq(id)
                        .and(TASK_SCRIPT_PAYLOADS.PROJECT_ID.eq(projectId))
                        .and(TASK_SCRIPT_PAYLOADS.TASK_ID.eq(taskId)))
                .fetchOptional()
                .map(TaskScriptPayloadView::from);
    }
}
