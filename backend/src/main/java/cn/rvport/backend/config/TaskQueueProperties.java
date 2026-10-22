package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.queue.task")
public record TaskQueueProperties(
        String exchange,
        String queue,
        String routingKey,
        String deadLetterExchange,
        String deadLetterQueue,
        String deadLetterRoutingKey,
        int maxAttempts
) {
    public TaskQueueProperties {
        deadLetterExchange = blankToDefault(deadLetterExchange, exchange + ".dlx");
        deadLetterQueue = blankToDefault(deadLetterQueue, queue + ".dlq");
        deadLetterRoutingKey = blankToDefault(deadLetterRoutingKey, routingKey + ".dead");
        maxAttempts = maxAttempts <= 0 ? 3 : maxAttempts;
    }

    private static String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
