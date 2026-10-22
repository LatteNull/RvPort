package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.sse.broadcast")
public record TaskSseBroadcastProperties(
        boolean enabled,
        String namespace,
        String taskEventsChannel,
        String taskLogEventsChannel
) {
    public TaskSseBroadcastProperties {
        namespace = blankToDefault(namespace, "rvport:sse");
        taskEventsChannel = blankToDefault(taskEventsChannel, "task-events");
        taskLogEventsChannel = blankToDefault(taskLogEventsChannel, "task-log-events");
    }

    public String taskEventsTopic() {
        return topic(taskEventsChannel);
    }

    public String taskLogEventsTopic() {
        return topic(taskLogEventsChannel);
    }

    private String topic(String channel) {
        String normalizedNamespace = trimColons(namespace);
        String normalizedChannel = trimColons(channel);
        if (normalizedNamespace.isBlank()) {
            return normalizedChannel;
        }
        return normalizedNamespace + ":" + normalizedChannel;
    }

    private static String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private static String trimColons(String value) {
        String normalized = value == null ? "" : value.trim();
        while (normalized.startsWith(":")) {
            normalized = normalized.substring(1);
        }
        while (normalized.endsWith(":")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }
}
