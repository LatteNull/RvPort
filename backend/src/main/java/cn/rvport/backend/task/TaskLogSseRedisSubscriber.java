package cn.rvport.backend.task;

import cn.rvport.backend.config.TaskSseBroadcastProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;

public class TaskLogSseRedisSubscriber implements MessageListener {

    private static final Logger log = LoggerFactory.getLogger(TaskLogSseRedisSubscriber.class);

    private final ObjectMapper objectMapper;
    private final TaskSseBroadcastProperties properties;
    private final TaskSseBroadcastInstance instance;
    private final TaskLogEventRepository repository;
    private final TaskLogSseBroker broker;

    public TaskLogSseRedisSubscriber(
            ObjectMapper objectMapper,
            TaskSseBroadcastProperties properties,
            TaskSseBroadcastInstance instance,
            TaskLogEventRepository repository,
            TaskLogSseBroker broker
    ) {
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.instance = instance;
        this.repository = repository;
        this.broker = broker;
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        if (!properties.enabled()) {
            return;
        }
        try {
            TaskLogSseBroadcastMessage payload = objectMapper.readValue(body(message), TaskLogSseBroadcastMessage.class);
            if (payload.publisherId() != null && payload.publisherId().equals(instance.publisherId())) {
                return;
            }
            if (payload.taskId() == null || payload.eventId() <= 0) {
                log.warn("Invalid task log SSE broadcast payload eventId={} taskId={}",
                        payload.eventId(), payload.taskId());
                return;
            }
            repository.findByTaskIdAndId(payload.taskId(), payload.eventId())
                    .ifPresentOrElse(
                            broker::publish,
                            () -> log.warn("Task log SSE broadcast event not found eventId={} taskId={}",
                                    payload.eventId(), payload.taskId())
                    );
        } catch (JsonProcessingException | RuntimeException ex) {
            log.warn("Task log SSE broadcast payload dropped error={}", ex.toString());
        }
    }

    private String body(Message message) {
        return new String(message.getBody(), StandardCharsets.UTF_8);
    }
}
