package cn.rvport.backend.task;

public enum TaskRuntimeHandleStatus {
    ACTIVE,
    CANCEL_REQUESTED,
    CANCELLING,
    CANCELLED,
    TERMINATED,
    FAILED,
    WORKER_LOST,
    CANCEL_ROUTE_UNAVAILABLE,
    CANCEL_UNKNOWN,
    CANCEL_FAILED
}
