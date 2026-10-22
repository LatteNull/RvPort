package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class WorkerCleanupPropertiesTests {

    @Test
    void acceptsSafeLifecycleBoundaries() {
        WorkerCleanupProperties properties = new WorkerCleanupProperties(true, 300_000, 300, 24, 100);

        properties.validateAgainst(workerProperties(60));
    }

    @Test
    void rejectsLostTimeoutAtOrBelowOfflineTimeout() {
        WorkerCleanupProperties properties = new WorkerCleanupProperties(true, 300_000, 60, 24, 100);

        assertThatThrownBy(() -> properties.validateAgainst(workerProperties(60)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("lost-timeout-seconds");
    }

    @Test
    void rejectsRetentionAtOrBelowLostTimeout() {
        WorkerCleanupProperties properties = new WorkerCleanupProperties(true, 300_000, 3600, 1, 100);

        assertThatThrownBy(() -> properties.validateAgainst(workerProperties(60)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retention-hours");
    }

    @Test
    void rejectsNonPositiveBatchSize() {
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 300_000, 300, 24, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("batch-size");
    }

    private WorkerProperties workerProperties(int offlineTimeoutSeconds) {
        return new WorkerProperties(true, "worker", RvPortAppMode.API, 1, 8, 10, offlineTimeoutSeconds);
    }
}
