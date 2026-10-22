package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import cn.rvport.backend.task.TaskRuntimeHandleType;
import cn.rvport.backend.task.TaskRuntimeHandleView;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class WorkerCleanupItemServiceTests {

    private final WorkerInstanceRepository workerRepository = Mockito.mock(WorkerInstanceRepository.class);
    private final TaskRuntimeHandleRepository handleRepository = Mockito.mock(TaskRuntimeHandleRepository.class);
    private final TaskRepository taskRepository = Mockito.mock(TaskRepository.class);
    private final TaskEventService eventService = Mockito.mock(TaskEventService.class);
    private final TaskSecretPayloadService secretService = Mockito.mock(TaskSecretPayloadService.class);
    private final TaskDomainFinalizationService domainService = Mockito.mock(TaskDomainFinalizationService.class);
    private WorkerCleanupItemService service;

    @BeforeEach
    void setUp() {
        service = new WorkerCleanupItemService(workerRepository, handleRepository, taskRepository, eventService, secretService, domainService);
    }

    @Test
    void reconcilesHandlesAndFailsEachRunningTaskOnce() {
        OffsetDateTime cutoff = OffsetDateTime.now().minusMinutes(5);
        UUID taskId = UUID.randomUUID();
        TaskRuntimeHandleView first = handle(taskId);
        TaskRuntimeHandleView second = handle(taskId);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        when(workerRepository.lockIfStillStale("worker-1", cutoff)).thenReturn(true);
        when(handleRepository.findActiveTaskIdsByWorker("worker-1")).thenReturn(List.of(taskId));
        when(handleRepository.markWorkerLostByWorker("worker-1", WorkerCleanupItemService.WORKER_LOST_MESSAGE))
                .thenReturn(List.of(first, second));
        when(taskRepository.failRunningWorkerLost(taskId, WorkerCleanupItemService.WORKER_LOST_MESSAGE))
                .thenReturn(failed);

        WorkerCleanupItemResult result = service.reconcile("worker-1", cutoff);

        assertThat(result.reconciledHandles()).isEqualTo(2);
        assertThat(result.failedTasks()).containsExactly(failed);
        verify(taskRepository).failRunningWorkerLost(taskId, WorkerCleanupItemService.WORKER_LOST_MESSAGE);
        verify(eventService).append(failed.projectId(), taskId, TaskEventType.FAILED, TaskStatus.FAILED,
                failed.progress(), failed.message());
        verify(secretService).deleteByTaskId(taskId);
        verify(domainService).finish(failed);
        var order = Mockito.inOrder(taskRepository, handleRepository);
        order.verify(handleRepository).findActiveTaskIdsByWorker("worker-1");
        order.verify(taskRepository).lockById(taskId);
        order.verify(handleRepository).markWorkerLostByWorker("worker-1", WorkerCleanupItemService.WORKER_LOST_MESSAGE);
    }

    @Test
    void skipsWorkerThatRecoveredBeforeLock() {
        OffsetDateTime cutoff = OffsetDateTime.now().minusMinutes(5);
        when(workerRepository.lockIfStillStale("worker-1", cutoff)).thenReturn(false);

        WorkerCleanupItemResult result = service.reconcile("worker-1", cutoff);

        assertThat(result).isEqualTo(WorkerCleanupItemResult.skipped());
        verify(handleRepository, never()).markWorkerLostByWorker(Mockito.anyString(), Mockito.anyString());
    }

    @Test
    void leavesAlreadyTerminalTaskUntouched() {
        OffsetDateTime cutoff = OffsetDateTime.now().minusMinutes(5);
        UUID taskId = UUID.randomUUID();
        when(workerRepository.lockIfStillStale("worker-1", cutoff)).thenReturn(true);
        when(handleRepository.markWorkerLostByWorker("worker-1", WorkerCleanupItemService.WORKER_LOST_MESSAGE))
                .thenReturn(List.of(handle(taskId)));
        when(taskRepository.failRunningWorkerLost(taskId, WorkerCleanupItemService.WORKER_LOST_MESSAGE))
                .thenReturn(null);

        WorkerCleanupItemResult result = service.reconcile("worker-1", cutoff);

        assertThat(result.reconciledHandles()).isEqualTo(1);
        assertThat(result.failedTasks()).isEmpty();
        verify(eventService, never()).append(Mockito.any(), Mockito.any(), Mockito.any(), Mockito.any(),
                Mockito.any(), Mockito.any());
        verify(secretService, never()).deleteByTaskId(taskId);
    }

    @Test
    void deletesOnlyAfterFreshStalenessCheck() {
        OffsetDateTime cutoff = OffsetDateTime.now().minusHours(24);
        when(workerRepository.lockIfStillStale("worker-1", cutoff)).thenReturn(true);
        when(workerRepository.deleteIfRetired("worker-1", cutoff)).thenReturn(1);

        assertThat(service.deleteIfRetired("worker-1", cutoff)).isEqualTo(1);
        verify(workerRepository).deleteIfRetired("worker-1", cutoff);
    }

    private TaskRuntimeHandleView handle(UUID taskId) {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskRuntimeHandleView(UUID.randomUUID(), taskId, UUID.randomUUID(), "worker-1",
                TaskRuntimeHandleType.TASK, TaskRuntimeHandleStatus.WORKER_LOST, null, null, null, null,
                null, null, now.minusMinutes(10), now, now, "WORKER_LOST", "lost");
    }

    private TaskView task(UUID taskId, TaskStatus status) {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskView(taskId, UUID.randomUUID(), "TEST", status, 20,
                WorkerCleanupItemService.WORKER_LOST_MESSAGE, UUID.randomUUID(), now.minusMinutes(10),
                now.minusMinutes(9), now.minusMinutes(8), now, 3600, "WORKER_LOST",
                WorkerCleanupItemService.WORKER_LOST_MESSAGE, 0);
    }
}
