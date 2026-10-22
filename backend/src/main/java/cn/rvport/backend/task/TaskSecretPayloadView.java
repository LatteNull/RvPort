package cn.rvport.backend.task;

import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.JSONB;

public record TaskSecretPayloadView(
        UUID id,
        UUID projectId,
        UUID taskId,
        String secretType,
        String secretSha256,
        JSONB encryptedPayload,
        String keyId,
        UUID createdBy,
        OffsetDateTime createdAt
) {
}
