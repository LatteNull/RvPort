package cn.rvport.backend.worker;

public record WorkerCleanupResult(
        int markedOffline,
        int reconciledHandles,
        int failedTasks,
        int deletedWorkers
) {
    public static WorkerCleanupResult empty() {
        return new WorkerCleanupResult(0, 0, 0, 0);
    }
}
