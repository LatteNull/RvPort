package cn.rvport.backend.mail;

public record MailConfig(
        boolean enabled,
        boolean testMode,
        String host,
        int port,
        String username,
        String password,
        String fromAddress,
        boolean startTls,
        boolean ssl,
        int connectionTimeoutMillis,
        int readTimeoutMillis,
        String frontendBaseUrl
) {
}
