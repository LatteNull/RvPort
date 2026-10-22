package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

import java.time.OffsetDateTime;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;

class InfrastructureConfigurationTests {

    @Test
    void sseTopicsApplyDefaultsTrimWhitespaceAndNormalizeColons() {
        TaskSseBroadcastProperties defaults = new TaskSseBroadcastProperties(true, null, " ", null);
        TaskSseBroadcastProperties normalized = new TaskSseBroadcastProperties(true,
                " ::custom:: ", " ::events:: ", ":logs:");
        TaskSseBroadcastProperties emptyNamespace = new TaskSseBroadcastProperties(true,
                "::", "events", "logs");

        assertThat(defaults.taskEventsTopic()).isEqualTo("rvport:sse:task-events");
        assertThat(defaults.taskLogEventsTopic()).isEqualTo("rvport:sse:task-log-events");
        assertThat(normalized.taskEventsTopic()).isEqualTo("custom:events");
        assertThat(normalized.taskLogEventsTopic()).isEqualTo("custom:logs");
        assertThat(emptyNamespace.taskEventsTopic()).isEqualTo("events");
    }

    @Test
    void taskQueuePropertiesDeriveDeadLetterDefaultsAndKeepOverrides() {
        TaskQueueProperties defaults = new TaskQueueProperties("tasks", "queue", "route",
                null, " ", null, 0);
        TaskQueueProperties custom = new TaskQueueProperties("tasks", "queue", "route",
                "dlx", "dlq", "dead", 5);
        TaskCancelQueueProperties cancelDefaults = new TaskCancelQueueProperties(
                null, null, null, null, null, null, 0, -1);
        TaskCancelQueueProperties cancelCustom = new TaskCancelQueueProperties(
                "cancel", "prefix", "route", "dlx", "dlq", "dead", 4, 8);

        assertThat(defaults.deadLetterExchange()).isEqualTo("tasks.dlx");
        assertThat(defaults.deadLetterQueue()).isEqualTo("queue.dlq");
        assertThat(defaults.deadLetterRoutingKey()).isEqualTo("route.dead");
        assertThat(defaults.maxAttempts()).isEqualTo(3);
        assertThat(custom.maxAttempts()).isEqualTo(5);
        assertThat(cancelDefaults.queueName("worker-1")).isEqualTo("rvport.tasks.cancel.worker-1");
        assertThat(cancelDefaults.routingKey("worker-1")).isEqualTo("worker.cancel.worker-1");
        assertThat(cancelDefaults.maxAttempts()).isEqualTo(3);
        assertThat(cancelDefaults.gracePeriodSeconds()).isEqualTo(5);
        assertThat(cancelCustom.queueName("w")).isEqualTo("prefix.w");
    }

    @Test
    void workerPropertiesClampConcurrencyAndSupplyTimingDefaults() {
        WorkerProperties defaults = new WorkerProperties(true, null, null, -1, 0, 0, -1);
        WorkerProperties capped = new WorkerProperties(true, "worker", RvPortAppMode.WORKER, 20, 4, 2, 3);
        RvPortProperties.Worker nestedDefaults = new RvPortProperties.Worker(true, "worker", null,
                -2, 0, 0, 0);
        RvPortProperties.Worker nestedCapped = new RvPortProperties.Worker(true, "worker",
                RvPortAppMode.API, 9, 3, 2, 4);

        assertThat(defaults.mode()).isEqualTo(RvPortAppMode.COMBINED);
        assertThat(defaults.concurrencyLimit()).isZero();
        assertThat(defaults.maxConcurrencyLimit()).isEqualTo(8);
        assertThat(defaults.heartbeatIntervalSeconds()).isEqualTo(10);
        assertThat(defaults.offlineTimeoutSeconds()).isEqualTo(60);
        assertThat(capped.concurrencyLimit()).isEqualTo(4);
        assertThat(nestedDefaults.concurrencyLimit()).isZero();
        assertThat(nestedDefaults.mode()).isEqualTo(RvPortAppMode.COMBINED);
        assertThat(nestedCapped.concurrencyLimit()).isEqualTo(3);
        assertThat(new RvPortProperties(null, null, null).worker().enabled()).isFalse();
        assertThat(new RvPortProperties.Worker(true).concurrencyLimit()).isEqualTo(1);
        assertThat(new RvPortProperties.Worker(true, "id").instanceId()).isEqualTo("id");
    }

    @Test
    void cleanupPropertiesRejectEachInvalidBoundaryAndCrossPropertyConflict() {
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 0, 10, 1, 1))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("interval-ms");
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 1, 0, 1, 1))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("lost-timeout");
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 1, 10, 0, 1))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("retention-hours");
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 1, 10, 1, 0))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("batch-size");

        WorkerProperties worker = new WorkerProperties(true, null, null, 1, 8, 10, 60);
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 1, 60, 1, 1).validateAgainst(worker))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("offline-timeout");
        assertThatThrownBy(() -> new WorkerCleanupProperties(true, 1, 7200, 1, 1).validateAgainst(worker))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("retention-hours");
        new WorkerCleanupProperties(true, 1, 61, 1, 1).validateAgainst(worker);
    }

    @Test
    void configurationFactoriesBuildLocalBeansWithoutConnecting() throws Exception {
        DataSource dataSource = mock(DataSource.class);
        var liquibase = new LiquibaseConfiguration().springLiquibase(dataSource, "classpath:/db/changelog.xml");
        var mapper = new JacksonConfiguration().objectMapper();

        assertThat(liquibase.getDataSource()).isSameAs(dataSource);
        assertThat(liquibase.getChangeLog()).isEqualTo("classpath:/db/changelog.xml");
        assertThat(mapper.writeValueAsString(OffsetDateTime.parse("2026-01-02T03:04:05Z")))
                .isEqualTo("\"2026-01-02T03:04:05Z\"");
    }
}
