package cn.rvport.backend.credential;

import java.util.UUID;

public record CredentialSummaryResponse(
        boolean configured,
        UUID id,
        CredentialKind kind,
        String name,
        String maskedSummary
) {
    public static CredentialSummaryResponse empty() {
        return new CredentialSummaryResponse(false, null, null, null, null);
    }
}
