package cn.rvport.backend.worker;

import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.WorkerProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "rvport.worker.cleanup", name = "enabled", havingValue = "true", matchIfMissing = true)
public class WorkerCleanupScheduler {

    private static final Logger log = LoggerFactory.getLogger(WorkerCleanupScheduler.class);

    private final WorkerCleanupService cleanupService;
    private final WorkerProperties workerProperties;

    public WorkerCleanupScheduler(WorkerCleanupService cleanupService, WorkerProperties workerProperties) {
        this.cleanupService = cleanupService;
        this.workerProperties = workerProperties;
    }

    @Scheduled(
            initialDelayString = "${rvport.worker.cleanup.interval-ms:300000}",
            fixedDelayString = "${rvport.worker.cleanup.interval-ms:300000}"
    )
    public void cleanup() {
        if (workerProperties.mode() == RvPortAppMode.WORKER) {
            return;
        }
        WorkerCleanupResult result = cleanupService.cleanup();
        if (result.markedOffline() > 0 || result.reconciledHandles() > 0
                || result.failedTasks() > 0 || result.deletedWorkers() > 0) {
            log.info("Stale worker cleanup completed markedOffline={} reconciledHandles={} failedTasks={} deletedWorkers={}",
                    result.markedOffline(), result.reconciledHandles(), result.failedTasks(), result.deletedWorkers());
        }
    }
}
