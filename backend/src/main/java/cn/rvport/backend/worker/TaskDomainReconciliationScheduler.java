package cn.rvport.backend.worker;

import cn.rvport.backend.config.WorkerCleanupProperties;
import cn.rvport.backend.config.WorkerProperties;
import cn.rvport.backend.config.RvPortAppMode;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class TaskDomainReconciliationScheduler {
    private static final Logger log = LoggerFactory.getLogger(TaskDomainReconciliationScheduler.class);
    private final WorkerCleanupProperties properties;
    private final TaskDomainFinalizationRepository repository;
    private final TaskDomainFinalizationService service;
    private final WorkerProperties workerProperties;
    private UUID cursor;

    public TaskDomainReconciliationScheduler(WorkerCleanupProperties properties,
            TaskDomainFinalizationRepository repository, TaskDomainFinalizationService service,
            WorkerProperties workerProperties) {
        this.properties = properties;
        this.repository = repository;
        this.service = service;
        this.workerProperties = workerProperties;
    }

    @Scheduled(initialDelayString = "${rvport.worker.cleanup.interval-ms:300000}",
            fixedDelayString = "${rvport.worker.cleanup.interval-ms:300000}")
    public synchronized void reconcile() {
        if (!properties.enabled() || workerProperties.mode() == RvPortAppMode.WORKER) {
            return;
        }
        var candidates = repository.candidates(cursor, properties.batchSize());
        int updated = 0;
        for (UUID id : candidates) {
            try {
                updated += service.reconcile(id);
            } catch (RuntimeException ex) {
                log.warn("Domain terminal reconciliation failed taskId={} errorType={}", id, ex.getClass().getSimpleName());
            }
            cursor = id;
        }
        if (candidates.size() < properties.batchSize()) {
            cursor = null;
        }
        if (updated > 0) {
            log.info("Domain terminal reconciliation updated={} candidates={}", updated, candidates.size());
        }
    }
}
