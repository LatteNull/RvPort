package cn.rvport.backend.task;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ExtendWith(MockitoExtension.class)
class TaskEventServiceTests {

    @Mock
    private TaskEventRepository taskEventRepository;

    @Mock
    private TaskSseBroker taskSseBroker;

    @Mock
    private TaskSseEventBroadcaster taskSseEventBroadcaster;

    @AfterEach
    void clearSynchronization() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    @Test
    void publishesImmediatelyWhenNoTransactionIsActive() {
        TaskEventService service = new TaskEventService(taskEventRepository, taskSseBroker, taskSseEventBroadcaster);
        TaskEventView event = contextEvent();
        when(taskEventRepository.appendProjectContextChanged(
                event.projectId(),
                event.stageId(),
                event.resource(),
                event.changedFields(),
                event.message()
        )).thenReturn(event);

        service.appendProjectContextChanged(event.projectId(), event.stageId(), event.resource(), event.changedFields(), event.message());

        verify(taskSseBroker).publish(event);
        verify(taskSseEventBroadcaster).publishTaskEvent(event);
    }

    @Test
    void publishesAfterTransactionCommitWhenSynchronizationIsActive() {
        TaskEventService service = new TaskEventService(taskEventRepository, taskSseBroker, taskSseEventBroadcaster);
        TaskEventView event = contextEvent();
        when(taskEventRepository.appendProjectContextChanged(
                event.projectId(),
                event.stageId(),
                event.resource(),
                event.changedFields(),
                event.message()
        )).thenReturn(event);

        TransactionSynchronizationManager.initSynchronization();
        service.appendProjectContextChanged(event.projectId(), event.stageId(), event.resource(), event.changedFields(), event.message());

        verify(taskSseBroker, never()).publish(event);
        verify(taskSseEventBroadcaster, never()).publishTaskEvent(event);
        TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit);
        verify(taskSseBroker).publish(event);
        verify(taskSseEventBroadcaster).publishTaskEvent(event);
    }

    private TaskEventView contextEvent() {
        UUID projectId = UUID.randomUUID();
        UUID resourceId = UUID.randomUUID();
        return new TaskEventView(
                10L,
                "evt_" + UUID.randomUUID(),
                projectId,
                null,
                null,
                TaskEventType.PROJECT_CONTEXT_CHANGED.value(),
                null,
                null,
                "项目上下文已更新",
                null,
                null,
                "context",
                TaskEventResource.of("source_revision", resourceId),
                List.of("activeSourceRevision"),
                OffsetDateTime.now()
        );
    }
}
