package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.worker.cleanup")
public record WorkerCleanupProperties(
        boolean enabled,
        long intervalMs,
        int lostTimeoutSeconds,
        int retentionHours,
        int batchSize
) {
    public WorkerCleanupProperties {
        if (intervalMs <= 0) {
            throw new IllegalArgumentException("rvport.worker.cleanup.interval-ms must be greater than zero");
        }
        if (lostTimeoutSeconds <= 0) {
            throw new IllegalArgumentException("rvport.worker.cleanup.lost-timeout-seconds must be greater than zero");
        }
        if (retentionHours <= 0) {
            throw new IllegalArgumentException("rvport.worker.cleanup.retention-hours must be greater than zero");
        }
        if (batchSize <= 0) {
            throw new IllegalArgumentException("rvport.worker.cleanup.batch-size must be greater than zero");
        }
    }

    public void validateAgainst(WorkerProperties workerProperties) {
        if (lostTimeoutSeconds <= workerProperties.offlineTimeoutSeconds()) {
            throw new IllegalArgumentException(
                    "rvport.worker.cleanup.lost-timeout-seconds must be greater than rvport.worker.offline-timeout-seconds"
            );
        }
        long retentionSeconds = Math.multiplyExact((long) retentionHours, 3600L);
        if (retentionSeconds <= lostTimeoutSeconds) {
            throw new IllegalArgumentException(
                    "rvport.worker.cleanup.retention-hours must be greater than the lost timeout"
            );
        }
    }
}
