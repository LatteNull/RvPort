package cn.rvport.backend.worker;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.TaskCancelQueueProperties;
import cn.rvport.backend.queue.TaskCancelQueueMessage;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import com.rabbitmq.client.Channel;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

@ExtendWith(MockitoExtension.class)
class TaskCancelWorkerListenerTests {

    @Mock
    private TaskExecutionRegistry taskExecutionRegistry;

    @Mock
    private TaskRuntimeHandleRepository runtimeHandleRepository;

    @Mock
    private Channel channel;

    @Test
    void acksAfterCancellingRegisteredTask() throws IOException {
        TaskCancelWorkerListener listener = listener(3);
        TaskCancelQueueMessage cancelMessage = message();
        when(taskExecutionRegistry.cancel(cancelMessage.taskId())).thenReturn(true);

        listener.onMessage(cancelMessage, amqpMessage(10L, Map.of()), channel);

        verify(runtimeHandleRepository).markCancelling(cancelMessage.runtimeHandleId());
        verify(taskExecutionRegistry).cancel(cancelMessage.taskId());
        verify(channel).basicAck(10L, false);
    }

    @Test
    void marksUnknownAndAcksWhenTaskHandleIsMissing() throws IOException {
        TaskCancelWorkerListener listener = listener(3);
        TaskCancelQueueMessage cancelMessage = message();
        when(taskExecutionRegistry.cancel(cancelMessage.taskId())).thenReturn(false);

        listener.onMessage(cancelMessage, amqpMessage(11L, Map.of()), channel);

        verify(runtimeHandleRepository).markError(
                cancelMessage.runtimeHandleId(),
                TaskRuntimeHandleStatus.CANCEL_UNKNOWN,
                "CANCEL_HANDLE_NOT_FOUND",
                "目标 worker 未找到运行中任务句柄"
        );
        verify(channel).basicAck(11L, false);
    }

    @Test
    void nacksWithRequeueBeforeMaxAttemptsAndWithoutRequeueAtMaxAttempts() throws IOException {
        TaskCancelWorkerListener listener = listener(3);
        TaskCancelQueueMessage cancelMessage = message();
        doThrow(new IllegalStateException("registry unavailable")).when(taskExecutionRegistry).cancel(any());

        listener.onMessage(cancelMessage, amqpMessage(12L, Map.of("x-delivery-count", 1)), channel);
        verify(channel).basicNack(12L, false, true);

        listener.onMessage(cancelMessage, amqpMessage(13L, Map.of("x-delivery-count", 2)), channel);
        verify(channel).basicNack(13L, false, false);
    }

    @Test
    void invalidStringDeliveryCountFallsBackToFirstAttempt() throws IOException {
        TaskCancelWorkerListener listener = listener(3);
        TaskCancelQueueMessage cancelMessage = message();
        doThrow(new IllegalStateException("registry unavailable")).when(taskExecutionRegistry).cancel(any());

        listener.onMessage(cancelMessage, amqpMessage(14L, Map.of("x-delivery-count", "invalid")), channel);

        verify(channel).basicNack(14L, false, true);
    }

    @Test
    void numericStringDeliveryCountIsParsed() throws IOException {
        TaskCancelWorkerListener listener = listener(3);
        TaskCancelQueueMessage cancelMessage = message();
        doThrow(new IllegalStateException("registry unavailable")).when(taskExecutionRegistry).cancel(any());

        listener.onMessage(cancelMessage, amqpMessage(15L, Map.of("x-delivery-count", "2")), channel);

        verify(channel).basicNack(15L, false, false);
    }

    private TaskCancelWorkerListener listener(int maxAttempts) {
        TaskCancelQueueProperties properties = new TaskCancelQueueProperties(
                "exchange",
                "queue",
                "routing",
                "dlx",
                "dlq",
                "dead",
                maxAttempts,
                5
        );
        return new TaskCancelWorkerListener(taskExecutionRegistry, runtimeHandleRepository, properties);
    }

    private TaskCancelQueueMessage message() {
        return new TaskCancelQueueMessage(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "worker-1",
                OffsetDateTime.now(),
                "USER_REQUESTED"
        );
    }

    private Message amqpMessage(long deliveryTag, Map<String, Object> headers) {
        MessageProperties properties = new MessageProperties();
        properties.setDeliveryTag(deliveryTag);
        headers.forEach(properties::setHeader);
        return new Message(new byte[0], properties);
    }
}
