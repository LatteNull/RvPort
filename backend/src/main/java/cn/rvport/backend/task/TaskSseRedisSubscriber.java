package cn.rvport.backend.task;

import cn.rvport.backend.config.TaskSseBroadcastProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;

public class TaskSseRedisSubscriber implements MessageListener {

    private static final Logger log = LoggerFactory.getLogger(TaskSseRedisSubscriber.class);

    private final ObjectMapper objectMapper;
    private final TaskSseBroadcastProperties properties;
    private final TaskSseBroadcastInstance instance;
    private final TaskEventRepository repository;
    private final TaskSseBroker broker;

    public TaskSseRedisSubscriber(
            ObjectMapper objectMapper,
            TaskSseBroadcastProperties properties,
            TaskSseBroadcastInstance instance,
            TaskEventRepository repository,
            TaskSseBroker broker
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
            TaskSseBroadcastMessage payload = objectMapper.readValue(body(message), TaskSseBroadcastMessage.class);
            if (payload.publisherId() != null && payload.publisherId().equals(instance.publisherId())) {
                return;
            }
            if (payload.projectId() == null || payload.eventId() <= 0) {
                log.warn("Invalid task SSE broadcast payload eventId={} projectId={}",
                        payload.eventId(), payload.projectId());
                return;
            }
            repository.findByProjectIdAndId(payload.projectId(), payload.eventId())
                    .ifPresentOrElse(
                            broker::publish,
                            () -> log.warn("Task SSE broadcast event not found eventId={} projectId={}",
                                    payload.eventId(), payload.projectId())
                    );
        } catch (JsonProcessingException | RuntimeException ex) {
            log.warn("Task SSE broadcast payload dropped error={}", ex.toString());
        }
    }

    private String body(Message message) {
        return new String(message.getBody(), StandardCharsets.UTF_8);
    }
}
