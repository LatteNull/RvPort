package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import cn.rvport.backend.config.TaskSseBroadcastProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.redis.core.StringRedisTemplate;

class TaskSseEventBroadcasterTests {

    private final StringRedisTemplate redisTemplate = org.mockito.Mockito.mock(StringRedisTemplate.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TaskSseBroadcastProperties properties = new TaskSseBroadcastProperties(
            true,
            "test:sse",
            "task-events",
            "task-log-events"
    );
    private final TaskSseBroadcastInstance instance = new TaskSseBroadcastInstance();
    private final TaskSseEventBroadcaster broadcaster = new TaskSseEventBroadcaster(
            redisTemplate,
            objectMapper,
            properties,
            instance
    );

    @Test
    void taskEventPayloadContainsOnlyMinimalReferences() {
        TaskEventView event = new TaskEventView(
                42L,
                "evt_" + UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                "SOURCE_GIT_SYNC",
                TaskEventType.LOG.value(),
                TaskStatus.RUNNING,
                10,
                "secret log message",
                "INFO",
                "/srv/secret/path token=abc",
                "source",
                TaskEventResource.of("source_revision", UUID.randomUUID()),
                List.of("activeSourceRevision"),
                OffsetDateTime.now()
        );

        broadcaster.publishTaskEvent(event);

        ArgumentCaptor<String> payload = ArgumentCaptor.forClass(String.class);
        verify(redisTemplate).convertAndSend(org.mockito.Mockito.eq("test:sse:task-events"), payload.capture());
        assertThat(payload.getValue()).contains("\"eventId\":42");
        assertThat(payload.getValue()).contains(event.projectId().toString());
        assertThat(payload.getValue()).contains(instance.publisherId());
        assertThat(payload.getValue()).doesNotContain("secret log message", "/srv/secret/path", "token", "SOURCE_GIT_SYNC");
    }

    @Test
    void taskLogPayloadContainsOnlyMinimalReferences() {
        TaskLogEventView event = new TaskLogEventView(
                99L,
                UUID.randomUUID(),
                UUID.randomUUID(),
                TaskLogType.STDERR,
                1L,
                "/srv/secret/path token=abc",
                OffsetDateTime.now()
        );

        broadcaster.publishTaskLogEvent(event);

        ArgumentCaptor<String> payload = ArgumentCaptor.forClass(String.class);
        verify(redisTemplate).convertAndSend(org.mockito.Mockito.eq("test:sse:task-log-events"), payload.capture());
        assertThat(payload.getValue()).contains("\"eventId\":99");
        assertThat(payload.getValue()).contains(event.taskId().toString());
        assertThat(payload.getValue()).contains(instance.publisherId());
        assertThat(payload.getValue()).doesNotContain("/srv/secret/path", "token", "STDERR");
    }

    @Test
    void redisPublishFailureIsSwallowed() {
        TaskEventView event = new TaskEventView(
                7L,
                "evt_" + UUID.randomUUID(),
                UUID.randomUUID(),
                null,
                null,
                TaskEventType.CREATED.value(),
                TaskStatus.PENDING,
                null,
                "created",
                null,
                null,
                null,
                TaskEventResource.empty(),
                List.of(),
                OffsetDateTime.now()
        );
        doThrow(new IllegalStateException("redis down"))
                .when(redisTemplate)
                .convertAndSend(org.mockito.Mockito.eq("test:sse:task-events"), org.mockito.Mockito.anyString());

        broadcaster.publishTaskEvent(event);
    }

    @Test
    void disabledBroadcastSkipsTaskAndLogEvents() {
        TaskSseEventBroadcaster disabled = new TaskSseEventBroadcaster(
                redisTemplate,
                objectMapper,
                new TaskSseBroadcastProperties(false, "test:sse", "task-events", "task-log-events"),
                instance);
        TaskEventView taskEvent = new TaskEventView(
                1L, "event", UUID.randomUUID(), UUID.randomUUID(), "KB_SCAN",
                TaskEventType.CREATED.value(), TaskStatus.PENDING, 0, "created", null, null,
                null, TaskEventResource.empty(), List.of(), OffsetDateTime.now());
        TaskLogEventView logEvent = new TaskLogEventView(
                2L, UUID.randomUUID(), UUID.randomUUID(), TaskLogType.STDOUT, 0L, "line", OffsetDateTime.now());

        disabled.publishTaskEvent(taskEvent);
        disabled.publishTaskLogEvent(logEvent);

        verifyNoInteractions(redisTemplate);
    }
}
