package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.WorkerCleanupProperties;
import cn.rvport.backend.config.WorkerProperties;
import cn.rvport.backend.task.TaskLogSseBroker;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentMatchers;
import org.mockito.Mockito;

class WorkerCleanupServiceTests {

    private final WorkerInstanceRepository workerRepository = Mockito.mock(WorkerInstanceRepository.class);
    private final WorkerCleanupItemService itemService = Mockito.mock(WorkerCleanupItemService.class);
    private final TaskLogSseBroker taskLogSseBroker = Mockito.mock(TaskLogSseBroker.class);

    @BeforeEach
    void resetMocks() {
        Mockito.reset(workerRepository, itemService, taskLogSseBroker);
    }

    @Test
    void aggregatesReconciliationAndDeletionResults() {
        WorkerCleanupService service = service(true);
        TaskView failed = failedTask();
        when(workerRepository.markOfflineBefore(ArgumentMatchers.any(), ArgumentMatchers.eq(100))).thenReturn(2);
        when(workerRepository.findInstanceIdsBefore(ArgumentMatchers.any(), ArgumentMatchers.eq(100)))
                .thenReturn(List.of("worker-1"), List.of("worker-1"));
        when(itemService.reconcile(ArgumentMatchers.eq("worker-1"), ArgumentMatchers.any()))
                .thenReturn(new WorkerCleanupItemResult(1, List.of(failed)));
        when(itemService.deleteIfRetired(ArgumentMatchers.eq("worker-1"), ArgumentMatchers.any())).thenReturn(1);

        WorkerCleanupResult result = service.cleanup();

        assertThat(result).isEqualTo(new WorkerCleanupResult(2, 1, 1, 1));
        verify(taskLogSseBroker).publishTerminal(failed);
    }

    @Test
    void continuesAfterOneWorkerFails() {
        WorkerCleanupService service = service(true);
        when(workerRepository.findInstanceIdsBefore(ArgumentMatchers.any(), ArgumentMatchers.eq(100)))
                .thenReturn(List.of("bad-worker", "good-worker"), List.of());
        when(itemService.reconcile(ArgumentMatchers.eq("bad-worker"), ArgumentMatchers.any()))
                .thenThrow(new IllegalStateException("database unavailable"));
        when(itemService.reconcile(ArgumentMatchers.eq("good-worker"), ArgumentMatchers.any()))
                .thenReturn(new WorkerCleanupItemResult(1, List.of()));

        WorkerCleanupResult result = service.cleanup();

        assertThat(result.reconciledHandles()).isEqualTo(1);
        verify(itemService).reconcile(ArgumentMatchers.eq("good-worker"), ArgumentMatchers.any());
    }

    @Test
    void disabledCleanupDoesNothing() {
        WorkerCleanupService service = service(false);

        assertThat(service.cleanup()).isEqualTo(WorkerCleanupResult.empty());
        verify(workerRepository, never()).markOfflineBefore(ArgumentMatchers.any(), ArgumentMatchers.anyInt());
    }

    private WorkerCleanupService service(boolean enabled) {
        WorkerCleanupProperties cleanup = new WorkerCleanupProperties(enabled, 300_000, 300, 24, 100);
        WorkerProperties worker = new WorkerProperties(true, "worker", RvPortAppMode.API, 1, 8, 10, 60);
        return new WorkerCleanupService(cleanup, worker, workerRepository, itemService, taskLogSseBroker);
    }

    private TaskView failedTask() {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskView(UUID.randomUUID(), UUID.randomUUID(), "TEST", TaskStatus.FAILED, 10,
                "worker lost", UUID.randomUUID(), now, now, now, now, 3600, "WORKER_LOST", "worker lost", 0);
    }
}
