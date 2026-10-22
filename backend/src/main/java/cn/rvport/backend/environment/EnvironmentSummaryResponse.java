package cn.rvport.backend.environment;

public record EnvironmentSummaryResponse(
        long total,
        long enabled,
        long sourceX86,
        long targetRiscv,
        long generalExecution
) {
    public static EnvironmentSummaryResponse empty() {
        return new EnvironmentSummaryResponse(0, 0, 0, 0, 0);
    }
}
