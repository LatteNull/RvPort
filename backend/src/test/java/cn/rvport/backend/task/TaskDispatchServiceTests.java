package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.queue.TaskQueueClient;
import cn.rvport.backend.queue.TaskQueueMessage;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class TaskDispatchServiceTests {

    private final TaskQueueClient queueClient = mock(TaskQueueClient.class);
    private final TaskRepository repository = mock(TaskRepository.class);
    private final TaskEventService eventService = mock(TaskEventService.class);
    private final TaskDispatchService service = new TaskDispatchService(queueClient, repository, eventService);

    @Test
    void publishesMessageMarksTaskQueuedAndAppendsEvent() {
        TaskView pending = task(TaskStatus.PENDING, 0);
        TaskView queued = task(TaskStatus.QUEUED, 0);
        when(repository.markQueued(pending.id())).thenReturn(queued);

        service.publishAndMarkQueued(pending);

        ArgumentCaptor<TaskQueueMessage> message = ArgumentCaptor.forClass(TaskQueueMessage.class);
        verify(queueClient).publish(message.capture());
        assertThat(message.getValue().taskId()).isEqualTo(pending.id());
        assertThat(message.getValue().taskType()).isEqualTo(pending.type());
        assertThat(message.getValue().projectId()).isEqualTo(pending.projectId());
        assertThat(message.getValue().createdAt()).isNotNull();
        verify(eventService).append(queued.projectId(), queued.id(), TaskEventType.QUEUED,
                TaskStatus.QUEUED, 0, "任务已投递队列");
    }

    @Test
    void doesNotAppendEventWhenQueuedUpdateReturnsNull() {
        TaskView pending = task(TaskStatus.PENDING, null);
        when(repository.markQueued(pending.id())).thenReturn(null);

        service.publishAndMarkQueued(pending);

        verify(queueClient).publish(any(TaskQueueMessage.class));
        verify(eventService, never()).append(any(), any(), any(), any(), any(), any());
    }

    @Test
    void requiresExistingTaskAndRejectsMissingTask() {
        TaskView task = task(TaskStatus.RUNNING, 40);
        when(repository.findById(task.id())).thenReturn(Optional.of(task));
        assertThat(service.requireTask(task.id())).isSameAs(task);

        UUID missing = UUID.randomUUID();
        when(repository.findById(missing)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.requireTask(missing))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务不存在");
    }

    private static TaskView task(TaskStatus status, Integer progress) {
        return new TaskView(UUID.randomUUID(), UUID.randomUUID(), "SOURCE_GIT_SYNC", status, progress,
                null, UUID.randomUUID(), OffsetDateTime.now(), null, null, null, 60, null, null, 0);
    }
}
