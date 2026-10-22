package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.worker")
public record WorkerProperties(
        boolean enabled,
        String instanceId,
        RvPortAppMode mode,
        int concurrencyLimit,
        int maxConcurrencyLimit,
        int heartbeatIntervalSeconds,
        int offlineTimeoutSeconds
) {
    public WorkerProperties {
        mode = mode == null ? RvPortAppMode.COMBINED : mode;
        concurrencyLimit = Math.max(0, concurrencyLimit);
        maxConcurrencyLimit = maxConcurrencyLimit <= 0 ? 8 : maxConcurrencyLimit;
        if (concurrencyLimit > maxConcurrencyLimit) {
            concurrencyLimit = maxConcurrencyLimit;
        }
        heartbeatIntervalSeconds = heartbeatIntervalSeconds <= 0 ? 10 : heartbeatIntervalSeconds;
        offlineTimeoutSeconds = offlineTimeoutSeconds <= 0 ? 60 : offlineTimeoutSeconds;
    }
}
