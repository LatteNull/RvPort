package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.queue.task-cancel")
public record TaskCancelQueueProperties(
        String exchange,
        String queuePrefix,
        String routingKeyPrefix,
        String deadLetterExchange,
        String deadLetterQueue,
        String deadLetterRoutingKey,
        int maxAttempts,
        int gracePeriodSeconds
) {
    public TaskCancelQueueProperties {
        exchange = blankToDefault(exchange, "rvport.tasks.cancel");
        queuePrefix = blankToDefault(queuePrefix, "rvport.tasks.cancel");
        routingKeyPrefix = blankToDefault(routingKeyPrefix, "worker.cancel");
        deadLetterExchange = blankToDefault(deadLetterExchange, exchange + ".dlx");
        deadLetterQueue = blankToDefault(deadLetterQueue, queuePrefix + ".dlq");
        deadLetterRoutingKey = blankToDefault(deadLetterRoutingKey, routingKeyPrefix + ".dead");
        maxAttempts = maxAttempts <= 0 ? 3 : maxAttempts;
        gracePeriodSeconds = gracePeriodSeconds <= 0 ? 5 : gracePeriodSeconds;
    }

    public String queueName(String workerInstanceId) {
        return queuePrefix + "." + workerInstanceId;
    }

    public String routingKey(String workerInstanceId) {
        return routingKeyPrefix + "." + workerInstanceId;
    }

    private static String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
