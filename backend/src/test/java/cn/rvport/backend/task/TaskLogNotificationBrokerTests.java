package cn.rvport.backend.task;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.test.util.ReflectionTestUtils;

class TaskLogNotificationBrokerTests {

    private final TaskRepository taskRepository = org.mockito.Mockito.mock(TaskRepository.class);
    private final TaskLogEventRepository eventRepository = org.mockito.Mockito.mock(TaskLogEventRepository.class);
    private final TaskLogNotificationBroker broker = new TaskLogNotificationBroker(taskRepository, eventRepository);

    @Test
    void doesNotQueryWithoutSubscriptions() {
        broker.poll();

        verifyNoInteractions(taskRepository, eventRepository);
    }

    @Test
    void pollsEachSubscribedTaskOnceForMultipleConnections() {
        TaskView running = task(TaskStatus.RUNNING);
        when(taskRepository.findByIds(Set.of(running.id()))).thenReturn(Map.of(running.id(), running));
        when(eventRepository.latestEventIds(Set.of(running.id()))).thenReturn(Map.of(running.id(), 0L));
        broker.subscribe(running, 0, org.mockito.Mockito.mock(SseEmitter.class));
        broker.subscribe(running, 0, org.mockito.Mockito.mock(SseEmitter.class));
        clearInvocations(taskRepository, eventRepository);

        broker.poll();

        verify(taskRepository, times(1)).findByIds(Set.of(running.id()));
        verify(eventRepository, times(1)).latestEventIds(Set.of(running.id()));
    }

    @Test
    void sendsUpdateBeforeTerminalAndCompletes() throws IOException {
        TaskView terminal = task(TaskStatus.SUCCEEDED);
        SseEmitter emitter = org.mockito.Mockito.mock(SseEmitter.class);
        when(taskRepository.findByIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), terminal));
        when(eventRepository.latestEventIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), 7L));
        when(taskRepository.isTerminal(TaskStatus.SUCCEEDED)).thenReturn(true);

        broker.subscribe(terminal, 3, emitter);

        InOrder order = inOrder(emitter);
        order.verify(emitter, times(2)).send(any(SseEmitter.SseEventBuilder.class));
        order.verify(emitter).complete();
        verify(emitter, times(2)).send(any(SseEmitter.SseEventBuilder.class));
    }

    @Test
    void queuedRetryRemainsSubscribed() throws IOException {
        TaskView queued = task(TaskStatus.QUEUED);
        SseEmitter emitter = org.mockito.Mockito.mock(SseEmitter.class);
        when(taskRepository.findByIds(Set.of(queued.id()))).thenReturn(Map.of(queued.id(), queued));
        when(eventRepository.latestEventIds(Set.of(queued.id()))).thenReturn(Map.of(queued.id(), 0L));
        when(taskRepository.isTerminal(TaskStatus.QUEUED)).thenReturn(false);

        broker.subscribe(queued, 0, emitter);

        verify(emitter, never()).complete();
        verify(emitter, never()).send(any(SseEmitter.SseEventBuilder.class));
        org.assertj.core.api.Assertions.assertThat(broker.subscribedTaskCount()).isEqualTo(1);
    }

    @Test
    void terminalTaskWithoutLogsCompletesWithoutUpdate() throws IOException {
        TaskView terminal = task(TaskStatus.FAILED);
        SseEmitter emitter = org.mockito.Mockito.mock(SseEmitter.class);
        when(taskRepository.findByIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), terminal));
        when(eventRepository.latestEventIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), 0L));
        when(taskRepository.isTerminal(TaskStatus.FAILED)).thenReturn(true);

        broker.subscribe(terminal, 0, emitter);

        verify(emitter, times(1)).send(any(SseEmitter.SseEventBuilder.class));
        verify(emitter).complete();
        org.assertj.core.api.Assertions.assertThat(broker.subscribedTaskCount()).isZero();
    }

    @Test
    void heartbeatKeepsHealthySubscriptionAndRemovesBrokenOne() throws IOException {
        TaskView running = task(TaskStatus.RUNNING);
        when(taskRepository.findByIds(Set.of(running.id()))).thenReturn(Map.of(running.id(), running));
        when(eventRepository.latestEventIds(Set.of(running.id()))).thenReturn(Map.of());
        when(taskRepository.isTerminal(TaskStatus.RUNNING)).thenReturn(false);
        SseEmitter healthy = org.mockito.Mockito.mock(SseEmitter.class);
        broker.subscribe(running, 0, healthy);

        broker.heartbeat();
        verify(healthy).send(any(SseEmitter.SseEventBuilder.class));
        org.assertj.core.api.Assertions.assertThat(broker.subscribedTaskCount()).isEqualTo(1);

        SseEmitter broken = org.mockito.Mockito.mock(SseEmitter.class);
        org.mockito.Mockito.doThrow(new IOException("closed"))
                .when(broken).send(any(SseEmitter.SseEventBuilder.class));
        broker.subscribe(running, 0, broken);
        broker.heartbeat();
        org.assertj.core.api.Assertions.assertThat(broker.subscribedTaskCount()).isEqualTo(1);
    }

    @Test
    void missingTaskCompletesAndRemovesAllSubscriptions() {
        TaskView task = task(TaskStatus.RUNNING);
        SseEmitter emitter = org.mockito.Mockito.mock(SseEmitter.class);
        when(taskRepository.findByIds(Set.of(task.id()))).thenReturn(Map.of());
        when(eventRepository.latestEventIds(Set.of(task.id()))).thenReturn(Map.of());

        broker.subscribe(task, 0, emitter);

        verify(emitter).complete();
        org.assertj.core.api.Assertions.assertThat(broker.subscribedTaskCount()).isZero();
    }

    @Test
    void refreshAndInternalRemovalIgnoreMissingCollections() {
        UUID taskId = UUID.randomUUID();
        broker.refresh(null);
        broker.refresh(Set.of());
        ReflectionTestUtils.invokeMethod(broker, "notifySubscriptions", task(TaskStatus.RUNNING), 2L);
        ReflectionTestUtils.invokeMethod(broker, "completeMissing", taskId);
        ReflectionTestUtils.invokeMethod(broker, "remove", taskId, null);
        verifyNoInteractions(taskRepository, eventRepository);
    }

    @Test
    void terminalCompletedEventAcceptsNullTaskMessage() throws IOException {
        TaskView original = task(TaskStatus.SUCCEEDED);
        TaskView terminal = new TaskView(
                original.id(), original.projectId(), original.type(), original.status(), original.progress(), null,
                original.createdBy(), original.createdAt(), original.queuedAt(), original.startedAt(), original.finishedAt(),
                original.timeoutSeconds(), null, null, 0);
        SseEmitter emitter = org.mockito.Mockito.mock(SseEmitter.class);
        when(taskRepository.findByIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), terminal));
        when(eventRepository.latestEventIds(Set.of(terminal.id()))).thenReturn(Map.of(terminal.id(), 1L));
        when(taskRepository.isTerminal(TaskStatus.SUCCEEDED)).thenReturn(true);

        broker.subscribe(terminal, 1, emitter);

        verify(emitter).send(any(SseEmitter.SseEventBuilder.class));
        verify(emitter).complete();
    }

    private TaskView task(TaskStatus status) {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskView(
                UUID.randomUUID(), UUID.randomUUID(), RvPortTaskTypes.ENV_RUN_SCRIPT, status, 10, "message",
                UUID.randomUUID(), now, now, now, status == TaskStatus.RUNNING ? null : now,
                null, null, null, 0
        );
    }
}
