package cn.rvport.backend.queue;

import cn.rvport.backend.config.TaskCancelQueueProperties;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class TaskCancelQueueClient {

    private static final Logger log = LoggerFactory.getLogger(TaskCancelQueueClient.class);

    private final RabbitTemplate rabbitTemplate;
    private final TaskCancelQueueProperties properties;
    private final TaskRuntimeHandleRepository runtimeHandleRepository;
    private final ObjectMapper objectMapper;

    public TaskCancelQueueClient(
            RabbitTemplate rabbitTemplate,
            TaskCancelQueueProperties properties,
            TaskRuntimeHandleRepository runtimeHandleRepository,
            ObjectMapper objectMapper
    ) {
        this.rabbitTemplate = rabbitTemplate;
        this.properties = properties;
        this.runtimeHandleRepository = runtimeHandleRepository;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    void configureReturns() {
        rabbitTemplate.setMandatory(true);
        rabbitTemplate.setReturnsCallback(returned -> {
            try {
                TaskCancelQueueMessage message = objectMapper.readValue(
                        returned.getMessage().getBody(),
                        TaskCancelQueueMessage.class
                );
                runtimeHandleRepository.markError(
                        message.runtimeHandleId(),
                        TaskRuntimeHandleStatus.CANCEL_ROUTE_UNAVAILABLE,
                        "CANCEL_ROUTE_UNAVAILABLE",
                        "取消消息无法路由到目标 worker"
                );
                log.warn("Task cancel message unroutable taskId={} runtimeHandleId={} replyCode={} replyText={} exchange={} routingKey={}",
                        message.taskId(),
                        message.runtimeHandleId(),
                        returned.getReplyCode(),
                        returned.getReplyText(),
                        returned.getExchange(),
                        returned.getRoutingKey());
            } catch (IOException ex) {
                log.warn("Unroutable cancel message could not be parsed", ex);
            }
        });
    }

    public void publish(TaskCancelQueueMessage message) {
        runtimeHandleRepository.markCancelRequested(message.runtimeHandleId());
        rabbitTemplate.convertAndSend(
                properties.exchange(),
                properties.routingKey(message.workerInstanceId()),
                message,
                rabbitMessage -> {
                    rabbitMessage.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    rabbitMessage.getMessageProperties().setContentType(MessageProperties.CONTENT_TYPE_JSON);
                    rabbitMessage.getMessageProperties().setHeader("runtimeHandleId", message.runtimeHandleId().toString());
                    rabbitMessage.getMessageProperties().setHeader("taskId", message.taskId().toString());
                    return rabbitMessage;
                });
    }

    public void markRouteUnavailable(UUID runtimeHandleId) {
        runtimeHandleRepository.markError(
                runtimeHandleId,
                TaskRuntimeHandleStatus.CANCEL_ROUTE_UNAVAILABLE,
                "CANCEL_ROUTE_UNAVAILABLE",
                "取消消息无法路由到目标 worker"
        );
    }
}
