package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;

public class RunningTaskHandle {

    private final UUID taskId;
    private final UUID runtimeHandleId;
    private final Thread ownerThread;
    private final TaskRuntimeHandleRepository runtimeHandleRepository;
    private final AtomicBoolean cancellationRequested = new AtomicBoolean(false);
    private final List<CancellableResource> resources = new CopyOnWriteArrayList<>();

    public RunningTaskHandle(
            UUID taskId,
            UUID runtimeHandleId,
            Thread ownerThread,
            TaskRuntimeHandleRepository runtimeHandleRepository
    ) {
        this.taskId = taskId;
        this.runtimeHandleId = runtimeHandleId;
        this.ownerThread = ownerThread;
        this.runtimeHandleRepository = runtimeHandleRepository;
    }

    public UUID taskId() {
        return taskId;
    }

    public UUID runtimeHandleId() {
        return runtimeHandleId;
    }

    public boolean isCancellationRequested() {
        return cancellationRequested.get();
    }

    public void addResource(CancellableResource resource) {
        if (resource != null) {
            resources.add(resource);
            if (isCancellationRequested()) {
                resource.cancel();
            }
        }
    }

    public void registerLocalProcess(Process process, java.time.Duration gracePeriod) {
        if (process == null) {
            return;
        }
        runtimeHandleRepository.registerLocalProcess(runtimeHandleId, process.pid());
        addResource(new LocalProcessCancellableResource(process, gracePeriod));
    }

    public void registerRemoteProcess(UUID environmentId, Long remotePid, Long remotePgid, String marker) {
        runtimeHandleRepository.registerRemoteProcess(runtimeHandleId, environmentId, remotePid, remotePgid, marker);
    }

    public void requestCancel() {
        if (!cancellationRequested.compareAndSet(false, true)) {
            return;
        }
        runtimeHandleRepository.markCancelling(runtimeHandleId);
        for (CancellableResource resource : resources) {
            resource.cancel();
        }
        ownerThread.interrupt();
    }

    public void throwIfCancellationRequested() {
        if (isCancellationRequested() || Thread.currentThread().isInterrupted()) {
            throw new TaskCancelledException("任务已取消");
        }
    }

    public void markTerminated(TaskRuntimeHandleStatus status) {
        runtimeHandleRepository.markTerminated(runtimeHandleId, status);
    }

    public void markError(TaskRuntimeHandleStatus status, String errorCode, String errorMessage) {
        runtimeHandleRepository.markError(runtimeHandleId, status, errorCode, errorMessage);
    }
}
