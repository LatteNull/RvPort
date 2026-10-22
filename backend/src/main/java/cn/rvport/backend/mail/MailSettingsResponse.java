package cn.rvport.backend.mail;

public record MailSettingsResponse(
        boolean enabled,
        boolean testMode,
        String host,
        Integer port,
        String username,
        boolean passwordConfigured,
        String fromAddress,
        boolean startTls,
        boolean ssl,
        int connectionTimeoutMillis,
        int readTimeoutMillis,
        String frontendBaseUrl
) {
}
