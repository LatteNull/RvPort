package cn.rvport.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.config.TaskCancelQueueProperties;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.core.ReturnedMessage;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

class TaskCancelQueueClientTests {

    @Test
    void publishesMandatoryPersistentJsonMessageToWorkerRoute() {
        RabbitTemplate rabbitTemplate = org.mockito.Mockito.mock(RabbitTemplate.class);
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        TaskCancelQueueProperties properties = properties();
        TaskCancelQueueClient client = new TaskCancelQueueClient(rabbitTemplate, properties, repository, new ObjectMapper());
        client.configureReturns();
        TaskCancelQueueMessage message = new TaskCancelQueueMessage(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "worker-1",
                OffsetDateTime.parse("2026-07-20T10:00:00+08:00"),
                "USER_REQUESTED");

        client.publish(message);

        ArgumentCaptor<MessagePostProcessor> postProcessorCaptor = ArgumentCaptor.forClass(MessagePostProcessor.class);
        verify(rabbitTemplate).setMandatory(true);
        verify(repository).markCancelRequested(message.runtimeHandleId());
        verify(rabbitTemplate).convertAndSend(
                eq("rvport.tasks.cancel"),
                eq("worker.cancel.worker-1"),
                eq(message),
                postProcessorCaptor.capture());

        Message rabbitMessage = new Message("{}".getBytes(StandardCharsets.UTF_8), new MessageProperties());
        Message processed = postProcessorCaptor.getValue().postProcessMessage(rabbitMessage);

        assertThat(processed.getMessageProperties().getDeliveryMode()).isEqualTo(MessageDeliveryMode.PERSISTENT);
        assertThat(processed.getMessageProperties().getContentType()).isEqualTo(MessageProperties.CONTENT_TYPE_JSON);
        assertThat(processed.getMessageProperties().getHeaders()).containsEntry("runtimeHandleId", message.runtimeHandleId().toString());
    }

    @Test
    void marksRuntimeHandleWhenCancelMessageIsUnroutable() throws Exception {
        RabbitTemplate rabbitTemplate = org.mockito.Mockito.mock(RabbitTemplate.class);
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
        TaskCancelQueueClient client = new TaskCancelQueueClient(rabbitTemplate, properties(), repository, objectMapper);
        ArgumentCaptor<RabbitTemplate.ReturnsCallback> callbackCaptor = ArgumentCaptor.forClass(RabbitTemplate.ReturnsCallback.class);
        client.configureReturns();
        verify(rabbitTemplate).setReturnsCallback(callbackCaptor.capture());

        TaskCancelQueueMessage payload = new TaskCancelQueueMessage(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "missing-worker",
                OffsetDateTime.now(),
                "USER_REQUESTED");
        MessageProperties messageProperties = new MessageProperties();
        messageProperties.setContentType(MessageProperties.CONTENT_TYPE_JSON);
        Message returnedMessage = new Message(objectMapper.writeValueAsBytes(payload), messageProperties);

        callbackCaptor.getValue().returnedMessage(new ReturnedMessage(
                returnedMessage,
                312,
                "NO_ROUTE",
                "rvport.tasks.cancel",
                "worker.cancel.missing-worker"));

        verify(repository).markError(
                payload.runtimeHandleId(),
                TaskRuntimeHandleStatus.CANCEL_ROUTE_UNAVAILABLE,
                "CANCEL_ROUTE_UNAVAILABLE",
                "取消消息无法路由到目标 worker");
    }

    private TaskCancelQueueProperties properties() {
        return new TaskCancelQueueProperties(
                "rvport.tasks.cancel",
                "rvport.tasks.cancel",
                "worker.cancel",
                "rvport.tasks.cancel.dlx",
                "rvport.tasks.cancel.dlq",
                "worker.cancel.dead",
                3,
                5);
    }
}
