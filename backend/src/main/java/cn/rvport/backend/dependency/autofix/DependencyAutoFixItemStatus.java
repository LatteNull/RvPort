package cn.rvport.backend.dependency.autofix;

public enum DependencyAutoFixItemStatus {
    PENDING,
    RUNNING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    SKIPPED_ALREADY_SATISFIED,
    SKIPPED_UNAVAILABLE
}
