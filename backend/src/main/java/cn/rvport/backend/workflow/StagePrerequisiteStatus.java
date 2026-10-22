package cn.rvport.backend.workflow;

public enum StagePrerequisiteStatus {
    SATISFIED,
    MISSING,
    RUNNING,
    FAILED,
    STALE,
    UNAVAILABLE
}
