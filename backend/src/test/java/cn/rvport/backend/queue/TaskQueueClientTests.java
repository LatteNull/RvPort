package cn.rvport.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.time.OffsetDateTime;
import java.util.UUID;

import cn.rvport.backend.config.TaskQueueProperties;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

class TaskQueueClientTests {

    @Test
    void publishesPersistentJsonMessageToConfiguredRoute() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        TaskQueueProperties properties = new TaskQueueProperties(
                "rvport.tasks",
                "rvport.tasks.default",
                "task.default",
                "rvport.tasks.dlx",
                "rvport.tasks.default.dlq",
                "task.default.dead",
                3);
        TaskQueueClient client = new TaskQueueClient(rabbitTemplate, properties);
        TaskQueueMessage message = new TaskQueueMessage(
                UUID.randomUUID(),
                "KB_SCAN",
                UUID.randomUUID(),
                OffsetDateTime.parse("2026-07-02T16:00:00+08:00"));

        client.publish(message);

        ArgumentCaptor<MessagePostProcessor> postProcessorCaptor = ArgumentCaptor.forClass(MessagePostProcessor.class);
        verify(rabbitTemplate).convertAndSend(
                eq("rvport.tasks"),
                eq("task.default"),
                eq(message),
                postProcessorCaptor.capture());

        Message rabbitMessage = new Message("{}".getBytes(), new MessageProperties());
        Message processed = postProcessorCaptor.getValue().postProcessMessage(rabbitMessage);

        assertThat(processed.getMessageProperties().getDeliveryMode())
                .isEqualTo(MessageDeliveryMode.PERSISTENT);
        assertThat(processed.getMessageProperties().getContentType())
                .isEqualTo(MessageProperties.CONTENT_TYPE_JSON);
    }
}
