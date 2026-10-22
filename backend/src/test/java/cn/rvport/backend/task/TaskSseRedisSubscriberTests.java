package cn.rvport.backend.task;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.TaskSseBroadcastProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.Message;

class TaskSseRedisSubscriberTests {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TaskSseBroadcastProperties properties = new TaskSseBroadcastProperties(
            true,
            "test:sse",
            "task-events",
            "task-log-events"
    );
    private final TaskSseBroadcastInstance instance = new TaskSseBroadcastInstance();

    @Test
    void projectSubscriberReadsPersistedEventAndPublishesBroker() throws Exception {
        TaskEventRepository repository = org.mockito.Mockito.mock(TaskEventRepository.class);
        TaskSseBroker broker = org.mockito.Mockito.mock(TaskSseBroker.class);
        TaskSseRedisSubscriber subscriber = new TaskSseRedisSubscriber(objectMapper, properties, instance, repository, broker);
        TaskEventView event = taskEvent(10L);
        String otherPublisher = UUID.randomUUID().toString();
        when(repository.findByProjectIdAndId(event.projectId(), event.id())).thenReturn(Optional.of(event));

        subscriber.onMessage(message(new TaskSseBroadcastMessage(event.id(), event.projectId(), otherPublisher)), null);

        verify(repository).findByProjectIdAndId(event.projectId(), event.id());
        verify(broker).publish(event);
    }

    @Test
    void projectSubscriberDropsSamePublisherToAvoidDuplicateLocalPush() throws Exception {
        TaskEventRepository repository = org.mockito.Mockito.mock(TaskEventRepository.class);
        TaskSseBroker broker = org.mockito.Mockito.mock(TaskSseBroker.class);
        TaskSseRedisSubscriber subscriber = new TaskSseRedisSubscriber(objectMapper, properties, instance, repository, broker);
        TaskEventView event = taskEvent(10L);

        subscriber.onMessage(message(new TaskSseBroadcastMessage(event.id(), event.projectId(), instance.publisherId())), null);

        verify(repository, never()).findByProjectIdAndId(event.projectId(), event.id());
        verify(broker, never()).publish(event);
    }

    @Test
    void projectSubscriberDropsInvalidPayload() {
        TaskEventRepository repository = org.mockito.Mockito.mock(TaskEventRepository.class);
        TaskSseBroker broker = org.mockito.Mockito.mock(TaskSseBroker.class);
        TaskSseRedisSubscriber subscriber = new TaskSseRedisSubscriber(objectMapper, properties, instance, repository, broker);

        subscriber.onMessage(messageBytes("not-json".getBytes()), null);

        verify(broker, never()).publish(org.mockito.Mockito.any());
    }

    @Test
    void taskLogSubscriberReadsPersistedEventAndPublishesBroker() throws Exception {
        TaskLogEventRepository repository = org.mockito.Mockito.mock(TaskLogEventRepository.class);
        TaskLogSseBroker broker = org.mockito.Mockito.mock(TaskLogSseBroker.class);
        TaskLogSseRedisSubscriber subscriber = new TaskLogSseRedisSubscriber(objectMapper, properties, instance, repository, broker);
        TaskLogEventView event = logEvent(12L);
        String otherPublisher = UUID.randomUUID().toString();
        when(repository.findByTaskIdAndId(event.taskId(), event.id())).thenReturn(Optional.of(event));

        subscriber.onMessage(message(new TaskLogSseBroadcastMessage(event.id(), event.taskId(), otherPublisher)), null);

        verify(repository).findByTaskIdAndId(event.taskId(), event.id());
        verify(broker).publish(event);
    }

    @Test
    void taskLogSubscriberDropsMissingEventWithoutBrokerPublish() throws Exception {
        TaskLogEventRepository repository = org.mockito.Mockito.mock(TaskLogEventRepository.class);
        TaskLogSseBroker broker = org.mockito.Mockito.mock(TaskLogSseBroker.class);
        TaskLogSseRedisSubscriber subscriber = new TaskLogSseRedisSubscriber(objectMapper, properties, instance, repository, broker);
        UUID taskId = UUID.randomUUID();
        when(repository.findByTaskIdAndId(taskId, 88L)).thenReturn(Optional.empty());

        subscriber.onMessage(message(new TaskLogSseBroadcastMessage(88L, taskId, UUID.randomUUID().toString())), null);

        verify(repository).findByTaskIdAndId(taskId, 88L);
        verify(broker, never()).publish(org.mockito.Mockito.any());
    }

    private Message message(Object payload) throws Exception {
        return messageBytes(objectMapper.writeValueAsBytes(payload));
    }

    private Message messageBytes(byte[] body) {
        Message message = org.mockito.Mockito.mock(Message.class);
        when(message.getBody()).thenReturn(body);
        return message;
    }

    private TaskEventView taskEvent(long eventId) {
        return new TaskEventView(
                eventId,
                "evt_" + UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                "SOURCE_GIT_SYNC",
                TaskEventType.PROGRESS.value(),
                TaskStatus.RUNNING,
                50,
                "running",
                null,
                null,
                "source",
                TaskEventResource.empty(),
                List.of(),
                OffsetDateTime.now()
        );
    }

    private TaskLogEventView logEvent(long eventId) {
        return new TaskLogEventView(
                eventId,
                UUID.randomUUID(),
                UUID.randomUUID(),
                TaskLogType.STDOUT,
                1L,
                "hello",
                OffsetDateTime.now()
        );
    }
}
