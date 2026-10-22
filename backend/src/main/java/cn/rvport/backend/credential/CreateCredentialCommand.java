package cn.rvport.backend.credential;

import java.util.Map;
import java.util.UUID;

public record CreateCredentialCommand(
        UUID projectId,
        UUID ownerUserId,
        CredentialKind kind,
        String name,
        String maskedSummary,
        Map<String, ?> payload
) {
}
