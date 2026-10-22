package cn.rvport.backend.analysis;

public enum SpecializedAnalysisStatus {
    PENDING,
    QUEUED,
    RUNNING,
    COMPLETE,
    COMPLETE_WITH_RISK,
    PARTIAL,
    FAILED,
    CANCELLED,
    TIMEOUT;

    public boolean terminal() {
        return switch (this) {
            case COMPLETE, COMPLETE_WITH_RISK, PARTIAL, FAILED, CANCELLED, TIMEOUT -> true;
            default -> false;
        };
    }

    public boolean publishedResult() {
        return this == COMPLETE || this == COMPLETE_WITH_RISK || this == PARTIAL;
    }
}
