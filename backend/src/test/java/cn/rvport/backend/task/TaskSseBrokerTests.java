package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

class TaskSseBrokerTests {

    @Test
    void subscribeRegistersEmitterAndBuildsJsonEvent() {
        TaskSseBroker broker = new TaskSseBroker();
        UUID projectId = UUID.randomUUID();

        SseEmitter emitter = broker.subscribe(projectId);

        assertThat(emitters(broker).get(projectId)).containsExactly(emitter);
        assertThat(broker.toSseEvent(event(projectId))).isNotNull();
    }

    @Test
    void publishesOnlyToProjectSubscribers() throws Exception {
        TaskSseBroker broker = new TaskSseBroker();
        UUID projectId = UUID.randomUUID();
        SseEmitter emitter = mock(SseEmitter.class);
        emitters(broker).put(projectId, ConcurrentHashMap.newKeySet());
        emitters(broker).get(projectId).add(emitter);

        broker.publish(event(UUID.randomUUID()));
        verify(emitter, never()).send(any(SseEmitter.SseEventBuilder.class));

        broker.publish(event(projectId));
        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
    }

    @Test
    void removesBrokenEmitterDuringPublishAndHeartbeat() throws Exception {
        TaskSseBroker broker = new TaskSseBroker();
        UUID firstProject = UUID.randomUUID();
        SseEmitter publishFailure = mock(SseEmitter.class);
        doThrow(new IOException("closed")).when(publishFailure).send(any(SseEmitter.SseEventBuilder.class));
        put(broker, firstProject, publishFailure);

        broker.publish(event(firstProject));
        assertThat(emitters(broker)).doesNotContainKey(firstProject);

        UUID secondProject = UUID.randomUUID();
        SseEmitter heartbeatFailure = mock(SseEmitter.class);
        doThrow(new IllegalStateException("completed")).when(heartbeatFailure)
                .send(any(SseEmitter.SseEventBuilder.class));
        put(broker, secondProject, heartbeatFailure);
        broker.heartbeat();
        assertThat(emitters(broker)).doesNotContainKey(secondProject);
    }

    @Test
    void heartbeatSendsToHealthyEmitterAndHandlesEmptyRegistry() throws Exception {
        TaskSseBroker broker = new TaskSseBroker();
        broker.heartbeat();
        SseEmitter emitter = mock(SseEmitter.class);
        put(broker, UUID.randomUUID(), emitter);

        broker.heartbeat();

        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
    }

    private static TaskEventView event(UUID projectId) {
        return new TaskEventView(12L, "12", projectId, UUID.randomUUID(), "KB_SCAN", "task.progress",
                TaskStatus.RUNNING, 50, "running", "INFO", null, "KB_SCAN", TaskEventResource.empty(),
                List.of("status"), OffsetDateTime.now());
    }

    private static void put(TaskSseBroker broker, UUID projectId, SseEmitter emitter) {
        emitters(broker).put(projectId, ConcurrentHashMap.newKeySet());
        emitters(broker).get(projectId).add(emitter);
    }

    @SuppressWarnings("unchecked")
    private static ConcurrentHashMap<UUID, Set<SseEmitter>> emitters(TaskSseBroker broker) {
        return (ConcurrentHashMap<UUID, Set<SseEmitter>>) ReflectionTestUtils.getField(broker, "emitters");
    }
}
