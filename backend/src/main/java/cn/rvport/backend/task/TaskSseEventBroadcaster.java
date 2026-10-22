package cn.rvport.backend.task;

import cn.rvport.backend.config.TaskSseBroadcastProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class TaskSseEventBroadcaster {

    private static final Logger log = LoggerFactory.getLogger(TaskSseEventBroadcaster.class);

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final TaskSseBroadcastProperties properties;
    private final TaskSseBroadcastInstance instance;

    public TaskSseEventBroadcaster(
            StringRedisTemplate redisTemplate,
            ObjectMapper objectMapper,
            TaskSseBroadcastProperties properties,
            TaskSseBroadcastInstance instance
    ) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.instance = instance;
    }

    public void publishTaskEvent(TaskEventView event) {
        if (!properties.enabled()) {
            return;
        }
        publish(
                properties.taskEventsTopic(),
                new TaskSseBroadcastMessage(event.id(), event.projectId(), instance.publisherId()),
                "task-event",
                event.id()
        );
    }

    public void publishTaskLogEvent(TaskLogEventView event) {
        if (!properties.enabled()) {
            return;
        }
        publish(
                properties.taskLogEventsTopic(),
                new TaskLogSseBroadcastMessage(event.id(), event.taskId(), instance.publisherId()),
                "task-log-event",
                event.id()
        );
    }

    String publisherId() {
        return instance.publisherId();
    }

    private void publish(String channel, Object payload, String payloadType, long eventId) {
        try {
            redisTemplate.convertAndSend(channel, objectMapper.writeValueAsString(payload));
        } catch (JsonProcessingException | RuntimeException ex) {
            log.warn("SSE broadcast publish failed type={} eventId={} channel={} error={}",
                    payloadType, eventId, channel, ex.toString());
        }
    }
}
