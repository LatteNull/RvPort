package cn.rvport.backend.dependency.autofix;

public enum DependencyAutoFixRunStatus {
    PENDING,
    RUNNING,
    SUCCEEDED,
    PARTIALLY_SUCCEEDED,
    FAILED,
    CANCELLED,
    TIMEOUT,
    SUCCEEDED_WITH_REANALYSIS_FAILED
}
