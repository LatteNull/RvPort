package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskView;
import java.util.List;

record WorkerCleanupItemResult(int reconciledHandles, List<TaskView> failedTasks) {
    static WorkerCleanupItemResult skipped() {
        return new WorkerCleanupItemResult(0, List.of());
    }
}
