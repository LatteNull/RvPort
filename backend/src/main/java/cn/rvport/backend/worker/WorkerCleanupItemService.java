package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleView;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
class WorkerCleanupItemService {

    static final String WORKER_LOST_MESSAGE = "Worker 失联，任务执行结果未知";

    private final WorkerInstanceRepository workerInstanceRepository;
    private final TaskRuntimeHandleRepository runtimeHandleRepository;
    private final TaskRepository taskRepository;
    private final TaskEventService taskEventService;
    private final TaskSecretPayloadService taskSecretPayloadService;
    private final TaskDomainFinalizationService domainFinalization;

    WorkerCleanupItemService(
            WorkerInstanceRepository workerInstanceRepository,
            TaskRuntimeHandleRepository runtimeHandleRepository,
            TaskRepository taskRepository,
            TaskEventService taskEventService,
            TaskSecretPayloadService taskSecretPayloadService,
            TaskDomainFinalizationService domainFinalization
    ) {
        this.workerInstanceRepository = workerInstanceRepository;
        this.runtimeHandleRepository = runtimeHandleRepository;
        this.taskRepository = taskRepository;
        this.taskEventService = taskEventService;
        this.taskSecretPayloadService = taskSecretPayloadService;
        this.domainFinalization = domainFinalization;
    }

    @Transactional
    WorkerCleanupItemResult reconcile(String workerInstanceId, OffsetDateTime cutoff) {
        if (!workerInstanceRepository.lockIfStillStale(workerInstanceId, cutoff)) {
            return WorkerCleanupItemResult.skipped();
        }
        // All publishers and cleanup lock Task before touching its handle.
        for (UUID taskId : runtimeHandleRepository.findActiveTaskIdsByWorker(workerInstanceId)) {
            taskRepository.lockById(taskId);
        }
        List<TaskRuntimeHandleView> handles = runtimeHandleRepository.markWorkerLostByWorker(
                workerInstanceId,
                WORKER_LOST_MESSAGE
        );
        Set<UUID> taskIds = new LinkedHashSet<>();
        for (TaskRuntimeHandleView handle : handles) {
            taskIds.add(handle.taskId());
        }
        List<TaskView> failedTasks = new ArrayList<>();
        for (UUID taskId : taskIds) {
            TaskView failed = taskRepository.failRunningWorkerLost(taskId, WORKER_LOST_MESSAGE);
            if (failed == null) {
                continue;
            }
            domainFinalization.finish(failed);
            taskEventService.append(
                    failed.projectId(),
                    failed.id(),
                    TaskEventType.FAILED,
                    TaskStatus.FAILED,
                    failed.progress(),
                    failed.message()
            );
            taskSecretPayloadService.deleteByTaskId(failed.id());
            failedTasks.add(failed);
        }
        return new WorkerCleanupItemResult(handles.size(), List.copyOf(failedTasks));
    }

    @Transactional
    int deleteIfRetired(String workerInstanceId, OffsetDateTime cutoff) {
        if (!workerInstanceRepository.lockIfStillStale(workerInstanceId, cutoff)) {
            return 0;
        }
        return workerInstanceRepository.deleteIfRetired(workerInstanceId, cutoff);
    }
}
