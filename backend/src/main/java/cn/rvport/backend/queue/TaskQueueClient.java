package cn.rvport.backend.queue;

import cn.rvport.backend.config.TaskQueueProperties;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class TaskQueueClient {

    private final RabbitTemplate rabbitTemplate;
    private final TaskQueueProperties properties;

    public TaskQueueClient(RabbitTemplate rabbitTemplate, TaskQueueProperties properties) {
        this.rabbitTemplate = rabbitTemplate;
        this.properties = properties;
    }

    public void publish(TaskQueueMessage message) {
        rabbitTemplate.convertAndSend(
                properties.exchange(),
                properties.routingKey(),
                message,
                rabbitMessage -> {
                    rabbitMessage.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    rabbitMessage.getMessageProperties().setContentType(MessageProperties.CONTENT_TYPE_JSON);
                    return rabbitMessage;
                });
    }
}
