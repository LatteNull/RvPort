package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

class TaskLogSseBrokerTests {

    @Test
    void subscribeRegistersEmitterAndBuildsLogAndTerminalEvents() {
        TaskLogSseBroker broker = new TaskLogSseBroker();
        UUID taskId = UUID.randomUUID();

        SseEmitter emitter = broker.subscribe(taskId);

        assertThat(emitters(broker).get(taskId)).containsExactly(emitter);
        assertThat(broker.toSseEvent(logEvent(taskId))).isNotNull();
        assertThat(broker.toTerminalEvent(task(taskId, null))).isNotNull();
        assertThat(broker.toTerminalEvent(task(taskId, "done"))).isNotNull();
    }

    @Test
    void publishesOnlyToTaskSubscribers() throws Exception {
        TaskLogSseBroker broker = new TaskLogSseBroker();
        UUID taskId = UUID.randomUUID();
        SseEmitter emitter = mock(SseEmitter.class);
        put(broker, taskId, emitter);

        broker.publish(logEvent(UUID.randomUUID()));
        verify(emitter, never()).send(any(SseEmitter.SseEventBuilder.class));
        broker.publish(logEvent(taskId));
        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
    }

    @Test
    void terminalEventCompletesHealthyEmitter() throws Exception {
        TaskLogSseBroker broker = new TaskLogSseBroker();
        UUID taskId = UUID.randomUUID();
        SseEmitter emitter = mock(SseEmitter.class);
        put(broker, taskId, emitter);

        broker.publishTerminal(task(taskId, "finished"));

        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
        verify(emitter).complete();
        broker.publishTerminal(task(UUID.randomUUID(), null));
    }

    @Test
    void removesBrokenEmittersFromPublishTerminalAndHeartbeat() throws Exception {
        TaskLogSseBroker broker = new TaskLogSseBroker();
        UUID publishId = UUID.randomUUID();
        SseEmitter publishFailure = failing(new IOException("closed"));
        put(broker, publishId, publishFailure);
        broker.publish(logEvent(publishId));
        assertThat(emitters(broker)).doesNotContainKey(publishId);

        UUID terminalId = UUID.randomUUID();
        SseEmitter terminalFailure = failing(new IllegalStateException("completed"));
        put(broker, terminalId, terminalFailure);
        broker.publishTerminal(task(terminalId, null));
        assertThat(emitters(broker)).doesNotContainKey(terminalId);

        UUID heartbeatId = UUID.randomUUID();
        SseEmitter heartbeatFailure = failing(new IOException("closed"));
        put(broker, heartbeatId, heartbeatFailure);
        broker.heartbeat();
        assertThat(emitters(broker)).doesNotContainKey(heartbeatId);
    }

    @Test
    void heartbeatSendsToHealthyEmitterAndHandlesEmptyRegistry() throws Exception {
        TaskLogSseBroker broker = new TaskLogSseBroker();
        broker.heartbeat();
        SseEmitter emitter = mock(SseEmitter.class);
        put(broker, UUID.randomUUID(), emitter);

        broker.heartbeat();

        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
    }

    private static SseEmitter failing(Exception exception) throws Exception {
        SseEmitter emitter = mock(SseEmitter.class);
        doThrow(exception).when(emitter).send(any(SseEmitter.SseEventBuilder.class));
        return emitter;
    }

    private static TaskLogEventView logEvent(UUID taskId) {
        return new TaskLogEventView(7L, UUID.randomUUID(), taskId, TaskLogType.STDOUT, 2L,
                "line", OffsetDateTime.now());
    }

    private static TaskView task(UUID taskId, String message) {
        return new TaskView(taskId, UUID.randomUUID(), "KB_SCAN", TaskStatus.SUCCEEDED, 100, message,
                UUID.randomUUID(), OffsetDateTime.now(), null, null, OffsetDateTime.now(), 60, null, null, 0);
    }

    private static void put(TaskLogSseBroker broker, UUID taskId, SseEmitter emitter) {
        emitters(broker).put(taskId, ConcurrentHashMap.newKeySet());
        emitters(broker).get(taskId).add(emitter);
    }

    @SuppressWarnings("unchecked")
    private static ConcurrentHashMap<UUID, Set<SseEmitter>> emitters(TaskLogSseBroker broker) {
        return (ConcurrentHashMap<UUID, Set<SseEmitter>>) ReflectionTestUtils.getField(broker, "emitters");
    }
}
