package cn.rvport.backend.useraction;

import cn.rvport.backend.config.UserActionTokenCleanupProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class UserActionTokenCleanupScheduler {

    private static final Logger log = LoggerFactory.getLogger(UserActionTokenCleanupScheduler.class);

    private final UserActionTokenCleanupService cleanupService;
    private final UserActionTokenCleanupProperties properties;

    public UserActionTokenCleanupScheduler(UserActionTokenCleanupService cleanupService, UserActionTokenCleanupProperties properties) {
        this.cleanupService = cleanupService;
        this.properties = properties;
    }

    @Scheduled(cron = "${rvport.user-action-token.cleanup.cron:0 0 3 * * *}")
    public void cleanup() {
        if (!properties.enabled()) {
            return;
        }
        try {
            cleanupService.cleanup(properties.retentionDays());
        } catch (RuntimeException ex) {
            log.warn("Failed to clean user action tokens retentionDays={} error={}",
                    properties.retentionDays(), ex.toString());
            log.debug("User action token cleanup failure details", ex);
        }
    }
}
