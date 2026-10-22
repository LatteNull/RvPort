package cn.rvport.backend.worker;

import cn.rvport.backend.config.WorkerCleanupProperties;
import cn.rvport.backend.config.WorkerProperties;
import cn.rvport.backend.task.TaskLogSseBroker;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class WorkerCleanupService {

    private static final Logger log = LoggerFactory.getLogger(WorkerCleanupService.class);

    private final WorkerCleanupProperties cleanupProperties;
    private final WorkerProperties workerProperties;
    private final WorkerInstanceRepository workerInstanceRepository;
    private final WorkerCleanupItemService itemService;
    private final TaskLogSseBroker taskLogSseBroker;

    public WorkerCleanupService(
            WorkerCleanupProperties cleanupProperties,
            WorkerProperties workerProperties,
            WorkerInstanceRepository workerInstanceRepository,
            WorkerCleanupItemService itemService,
            TaskLogSseBroker taskLogSseBroker
    ) {
        cleanupProperties.validateAgainst(workerProperties);
        this.cleanupProperties = cleanupProperties;
        this.workerProperties = workerProperties;
        this.workerInstanceRepository = workerInstanceRepository;
        this.itemService = itemService;
        this.taskLogSseBroker = taskLogSseBroker;
    }

    public WorkerCleanupResult cleanup() {
        if (!cleanupProperties.enabled()) {
            return WorkerCleanupResult.empty();
        }
        OffsetDateTime now = OffsetDateTime.now();
        int markedOffline = workerInstanceRepository.markOfflineBefore(
                now.minusSeconds(workerProperties.offlineTimeoutSeconds()),
                cleanupProperties.batchSize()
        );

        int reconciledHandles = 0;
        int failedTasks = 0;
        OffsetDateTime lostCutoff = now.minusSeconds(cleanupProperties.lostTimeoutSeconds());
        List<String> lostCandidates = workerInstanceRepository.findInstanceIdsBefore(
                lostCutoff,
                cleanupProperties.batchSize()
        );
        for (String workerInstanceId : lostCandidates) {
            try {
                WorkerCleanupItemResult result = itemService.reconcile(workerInstanceId, lostCutoff);
                reconciledHandles += result.reconciledHandles();
                failedTasks += result.failedTasks().size();
                for (TaskView failedTask : result.failedTasks()) {
                    taskLogSseBroker.publishTerminal(failedTask);
                }
            } catch (RuntimeException ex) {
                log.warn("Stale worker reconciliation failed workerInstanceId={} error={}",
                        safeInstanceId(workerInstanceId), ex.toString());
            }
        }

        int deletedWorkers = 0;
        OffsetDateTime retentionCutoff = now.minusHours(cleanupProperties.retentionHours());
        List<String> deleteCandidates = workerInstanceRepository.findInstanceIdsBefore(
                retentionCutoff,
                cleanupProperties.batchSize()
        );
        for (String workerInstanceId : deleteCandidates) {
            try {
                deletedWorkers += itemService.deleteIfRetired(workerInstanceId, retentionCutoff);
            } catch (RuntimeException ex) {
                log.warn("Retired worker deletion failed workerInstanceId={} error={}",
                        safeInstanceId(workerInstanceId), ex.toString());
            }
        }
        return new WorkerCleanupResult(markedOffline, reconciledHandles, failedTasks, deletedWorkers);
    }

    private String safeInstanceId(String value) {
        if (value == null) {
            return "unknown";
        }
        String sanitized = value.replaceAll("[^A-Za-z0-9._-]", "_");
        return sanitized.length() > 128 ? sanitized.substring(0, 128) : sanitized;
    }
}
