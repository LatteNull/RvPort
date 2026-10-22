package cn.rvport.backend.optimization;

public record OptimizationOverviewResponse(
        OptimizationCycleResponse currentCycle,
        long totalCycles
) {
}
