package cn.rvport.backend.worker;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.WorkerProperties;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class WorkerCleanupSchedulerTests {

    @Test
    void apiNodeRunsCleanup() {
        WorkerCleanupService service = Mockito.mock(WorkerCleanupService.class);
        when(service.cleanup()).thenReturn(WorkerCleanupResult.empty());
        WorkerCleanupScheduler scheduler = new WorkerCleanupScheduler(service, properties(RvPortAppMode.API));

        scheduler.cleanup();

        verify(service).cleanup();
    }

    @Test
    void workerOnlyNodeDoesNotRunCleanup() {
        WorkerCleanupService service = Mockito.mock(WorkerCleanupService.class);
        WorkerCleanupScheduler scheduler = new WorkerCleanupScheduler(service, properties(RvPortAppMode.WORKER));

        scheduler.cleanup();

        verify(service, never()).cleanup();
    }

    @Test
    void reportsEveryNonEmptyCleanupDimension() {
        WorkerCleanupService service = Mockito.mock(WorkerCleanupService.class);
        when(service.cleanup()).thenReturn(
                new WorkerCleanupResult(1, 0, 0, 0),
                new WorkerCleanupResult(0, 1, 0, 0),
                new WorkerCleanupResult(0, 0, 1, 0),
                new WorkerCleanupResult(0, 0, 0, 1)
        );
        WorkerCleanupScheduler scheduler = new WorkerCleanupScheduler(service, properties(RvPortAppMode.API));

        scheduler.cleanup();
        scheduler.cleanup();
        scheduler.cleanup();
        scheduler.cleanup();

        verify(service, Mockito.times(4)).cleanup();
    }

    private WorkerProperties properties(RvPortAppMode mode) {
        return new WorkerProperties(true, "worker", mode, 1, 8, 10, 60);
    }
}
