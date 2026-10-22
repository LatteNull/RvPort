package cn.rvport.backend.task;

import cn.rvport.backend.jooq.tables.records.TaskScriptPayloadsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.JSONB;

public record TaskScriptPayloadView(
        UUID id,
        UUID projectId,
        UUID taskId,
        String scriptSha256,
        int scriptLength,
        JSONB encryptedPayload,
        String keyId,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static TaskScriptPayloadView from(TaskScriptPayloadsRecord record) {
        return new TaskScriptPayloadView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getScriptSha256(),
                record.getScriptLength(),
                record.getEncryptedPayload(),
                record.getKeyId(),
                record.getCreatedBy(),
                record.getCreatedAt()
        );
    }
}
