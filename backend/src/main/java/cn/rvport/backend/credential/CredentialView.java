package cn.rvport.backend.credential;

import cn.rvport.backend.jooq.tables.records.CredentialsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record CredentialView(
        UUID id,
        UUID projectId,
        UUID ownerUserId,
        CredentialKind kind,
        String name,
        String maskedSummary,
        String kmsKeyVersion,
        CredentialStatus status,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static CredentialView from(CredentialsRecord record) {
        return new CredentialView(
                record.getId(),
                record.getProjectId(),
                record.getOwnerUserId(),
                CredentialKind.valueOf(record.getKind()),
                record.getName(),
                record.getMaskedSummary(),
                record.getKmsKeyVersion(),
                CredentialStatus.valueOf(record.getStatus()),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }

    public CredentialSummaryResponse toSummary() {
        return new CredentialSummaryResponse(true, id, kind, name, maskedSummary);
    }
}
