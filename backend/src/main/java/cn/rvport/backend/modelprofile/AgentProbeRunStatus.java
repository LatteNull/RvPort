package cn.rvport.backend.modelprofile;

public enum AgentProbeRunStatus {
    PENDING,
    RUNNING,
    SUCCESS,
    PARTIAL_SUCCESS,
    FAILED,
    TIMEOUT;

    public boolean terminal() {
        return this == SUCCESS || this == PARTIAL_SUCCESS || this == FAILED || this == TIMEOUT;
    }
}
