package cn.rvport.backend.dependency;

public enum DependencyAnalysisStatus {
    PENDING,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    TIMEOUT
}
