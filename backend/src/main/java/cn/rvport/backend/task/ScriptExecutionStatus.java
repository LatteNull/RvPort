package cn.rvport.backend.task;

public enum ScriptExecutionStatus {
    RUNNING,
    SUCCEEDED,
    ERROR;

    static ScriptExecutionStatus fromTaskStatus(TaskStatus status) {
        if (status == TaskStatus.SUCCEEDED) {
            return SUCCEEDED;
        }
        if (status == TaskStatus.FAILED || status == TaskStatus.TIMEOUT || status == TaskStatus.CANCELLED) {
            return ERROR;
        }
        return RUNNING;
    }
}
