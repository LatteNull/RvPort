package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.user-action-token.cleanup")
public record UserActionTokenCleanupProperties(
        boolean enabled,
        String cron,
        int retentionDays
) {
    public UserActionTokenCleanupProperties {
        cron = cron == null || cron.isBlank() ? "0 0 3 * * *" : cron;
        retentionDays = retentionDays <= 0 ? 30 : retentionDays;
    }
}
