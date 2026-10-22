package cn.rvport.backend.worker;

import java.util.List;

public record WorkerInstanceDetailResponse(
        WorkerInstanceResponse worker,
        List<WorkerTaskResponse> runningTasks
) {
}
