package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskLogResponse;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskView;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Supplier;

public interface TaskExecutionContext {

    TaskView task();

    <T> T input(Class<T> inputType);

    void progress(int progress, String message);

    Optional<TaskLogResponse> log(TaskLogType logType, String content);

    /** A short database-only publication; never wrap external execution or uploads. */
    default <T> T publish(Supplier<T> operation) {
        return operation.get();
    }

    default boolean isCancellationRequested() {
        return Thread.currentThread().isInterrupted();
    }

    default void throwIfCancellationRequested() {
        if (isCancellationRequested()) {
            throw new TaskCancelledException("任务已取消");
        }
    }

    default void registerLocalProcess(Process process, Duration gracePeriod) {
    }

    default void registerCancellableResource(CancellableResource resource) {
    }

    default void registerRemoteProcess(UUID environmentId, Long remotePid, Long remotePgid, String commandMarker) {
    }
}
