package cn.rvport.backend.task;

public enum TaskStatus {
    PENDING,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    TIMEOUT
}
