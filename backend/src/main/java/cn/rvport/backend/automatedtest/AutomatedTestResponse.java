package cn.rvport.backend.automatedtest;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import cn.rvport.backend.testcomparison.TestComparisonRunView;

public record AutomatedTestResponse(
        UUID id,
        UUID taskId,
        UUID projectId,
        UUID buildRunId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        UUID testBatchId,
        String testBatchRole,
        long currentEnvironmentConfigVersion,
        boolean currentRuntimeEnvironment,
        String environmentName,
        String command,
        String workingDirectory,
        Integer timeoutSeconds,
        Integer exitCode,
        Integer passedCount,
        Integer failedCount,
        Integer skippedCount,
        String status,
        UUID stdoutLogId,
        UUID stderrLogId,
        UUID combinedLogId,
        String outputSummary,
        List<Map<String, Object>> reportArtifacts,
        UUID comparisonId,
        String comparisonStatus,
        String comparisonUnavailableCode,
        String comparisonUnavailableMessage,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
    public static AutomatedTestResponse from(AutomatedTestRunView view) {
        return from(view, 0L);
    }

    public static AutomatedTestResponse from(AutomatedTestRunView view, long currentEnvironmentConfigVersion) {
        return from(view, currentEnvironmentConfigVersion, null);
    }

    public static AutomatedTestResponse from(AutomatedTestRunView view, long currentEnvironmentConfigVersion, TestComparisonRunView comparison) {
        boolean isCurrent = view.environmentConfigVersion() != null
                && view.environmentConfigVersion() == currentEnvironmentConfigVersion;
        return new AutomatedTestResponse(
                view.id(),
                view.taskId(),
                view.projectId(),
                view.buildRunId(),
                view.sourceRevisionId(),
                view.environmentId(),
                view.environmentConfigVersion(),
                view.testBatchId(),
                view.testBatchRole() == null ? null : view.testBatchRole().name(),
                currentEnvironmentConfigVersion,
                isCurrent,
                view.environmentName(),
                view.command(),
                view.workingDirectory(),
                view.timeoutSeconds(),
                view.exitCode(),
                view.passedCount(),
                view.failedCount(),
                view.skippedCount(),
                view.status().name(),
                view.stdoutLogId(),
                view.stderrLogId(),
                view.combinedLogId(),
                view.outputSummary(),
                view.reportArtifacts(),
                comparison == null ? null : comparison.id(),
                comparison == null ? null : comparison.status().name(),
                comparison == null ? null : comparison.unavailableCode(),
                comparison == null ? null : comparison.unavailableMessage(),
                view.startedAt(),
                view.finishedAt()
        );
    }
}
