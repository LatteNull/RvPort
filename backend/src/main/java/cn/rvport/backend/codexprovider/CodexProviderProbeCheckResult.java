package cn.rvport.backend.codexprovider;

public record CodexProviderProbeCheckResult(
        String name,
        String status,
        String errorCode,
        String message,
        long durationMs
) {
    public static CodexProviderProbeCheckResult success(CodexProviderProbeName name, String message, long durationMs) {
        return new CodexProviderProbeCheckResult(name.name(), CodexProviderTestStatus.SUCCESS.name(), null, message, durationMs);
    }

    public static CodexProviderProbeCheckResult failure(CodexProviderProbeName name, String errorCode, String message, long durationMs) {
        return new CodexProviderProbeCheckResult(name.name(), CodexProviderTestStatus.FAILED.name(), errorCode, message, durationMs);
    }

    public boolean succeeded() {
        return CodexProviderTestStatus.SUCCESS.name().equals(status);
    }
}
