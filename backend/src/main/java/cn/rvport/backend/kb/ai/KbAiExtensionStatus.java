package cn.rvport.backend.kb.ai;

public enum KbAiExtensionStatus {
    PENDING,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    PARTIAL_SUCCESS,
    FAILED,
    CANCELLED,
    TIMEOUT
}
