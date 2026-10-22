package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ExtendWith(MockitoExtension.class)
class TaskLogEventServiceTests {

    @Mock
    private TaskLogEventRepository repository;

    @Mock
    private TaskLogSseBroker sseBroker;

    @Mock
    private TaskSseEventBroadcaster taskSseEventBroadcaster;

    @Test
    void appendsSanitizedChunksAndPublishes() {
        TaskLogEventService service = new TaskLogEventService(repository, sseBroker, taskSseEventBroadcaster);
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        TaskLogEventView event = new TaskLogEventView(1, projectId, taskId, TaskLogType.STDOUT, 1, "token=****\n", OffsetDateTime.now());
        when(repository.append(eq(projectId), eq(taskId), eq(TaskLogType.STDOUT), any())).thenReturn(List.of(event));

        List<TaskLogEventView> events = service.append(projectId, taskId, TaskLogType.STDOUT, "token=abc123\n");

        assertThat(events).containsExactly(event);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<String>> chunksCaptor = ArgumentCaptor.forClass(List.class);
        verify(repository).append(eq(projectId), eq(taskId), eq(TaskLogType.STDOUT), chunksCaptor.capture());
        assertThat(chunksCaptor.getValue()).containsExactly("token=****\n");
        verify(sseBroker).publish(event);
        verify(taskSseEventBroadcaster).publishTaskLogEvent(event);
    }

    @Test
    void splitsLargeOutputAsEdgeCase() {
        TaskLogEventService service = new TaskLogEventService(repository, sseBroker, taskSseEventBroadcaster);
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(repository.append(eq(projectId), eq(taskId), eq(TaskLogType.STDERR), any())).thenReturn(List.of());

        service.append(projectId, taskId, TaskLogType.STDERR, "x".repeat(4001));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<String>> chunksCaptor = ArgumentCaptor.forClass(List.class);
        verify(repository).append(eq(projectId), eq(taskId), eq(TaskLogType.STDERR), chunksCaptor.capture());
        assertThat(chunksCaptor.getValue()).hasSize(2);
        assertThat(chunksCaptor.getValue().get(0)).hasSize(4000);
        assertThat(chunksCaptor.getValue().get(1)).hasSize(1);
    }

    @Test
    void ignoresMissingContentAndClampsListLimitsAndDelegatesCount() {
        TaskLogEventService service = new TaskLogEventService(repository, sseBroker, taskSseEventBroadcaster);
        UUID taskId = UUID.randomUUID();
        assertThat(service.append(UUID.randomUUID(), taskId, TaskLogType.STDOUT, null)).isEmpty();
        assertThat(service.append(UUID.randomUUID(), taskId, TaskLogType.STDOUT, "")).isEmpty();
        service.listAfter(taskId, 4, 0);
        service.listAfter(taskId, 4, 2000);
        when(repository.count(taskId)).thenReturn(9L);
        assertThat(service.count(taskId)).isEqualTo(9);
        verify(repository).listAfter(taskId, 4, 1);
        verify(repository).listAfter(taskId, 4, 1000);
        verify(repository, never()).append(any(), any(), any(), any());
    }

    @Test
    void defersPublicationUntilTransactionCommit() {
        TaskLogEventService service = new TaskLogEventService(repository, sseBroker, taskSseEventBroadcaster);
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        TaskLogEventView event = new TaskLogEventView(
                1, projectId, taskId, TaskLogType.STDOUT, 1, "line", OffsetDateTime.now());
        when(repository.append(eq(projectId), eq(taskId), eq(TaskLogType.STDOUT), any()))
                .thenReturn(List.of(event));
        TransactionSynchronizationManager.initSynchronization();
        try {
            service.append(projectId, taskId, TaskLogType.STDOUT, "line");
            verify(sseBroker, never()).publish(any());
            TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit);
            verify(sseBroker).publish(event);
            verify(taskSseEventBroadcaster).publishTaskLogEvent(event);
        } finally {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }
}
