package cn.rvport.backend.automatedtest;

import cn.rvport.backend.jooq.tables.records.TestRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record AutomatedTestRunView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID buildRunId,
        UUID sourceRevisionId,
        UUID environmentId,
        Long environmentConfigVersion,
        UUID testBatchId,
        TestBatchRole testBatchRole,
        String environmentName,
        String command,
        String workingDirectory,
        Integer timeoutSeconds,
        Integer exitCode,
        Integer passedCount,
        Integer failedCount,
        Integer skippedCount,
        TaskStatus status,
        UUID stdoutLogId,
        UUID stderrLogId,
        UUID combinedLogId,
        String outputSummary,
        List<Map<String, Object>> reportArtifacts,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
    public static AutomatedTestRunView from(TestRunsRecord record) {
        return new AutomatedTestRunView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getBuildRunId(),
                record.getSourceRevisionId(),
                record.getEnvironmentId(),
                record.getEnvironmentConfigVersion(),
                record.getTestBatchId(),
                record.getTestBatchRole() == null ? null : TestBatchRole.valueOf(record.getTestBatchRole()),
                null,
                record.getCommand(),
                record.getWorkingDirectory(),
                record.getTimeoutSeconds(),
                record.getExitCode(),
                record.getPassedCount(),
                record.getFailedCount(),
                record.getSkippedCount(),
                TaskStatus.valueOf(record.getStatus()),
                record.getStdoutLogId(),
                record.getStderrLogId(),
                record.getCombinedLogId(),
                null,
                List.of(),
                record.getStartedAt(),
                record.getFinishedAt()
        );
    }
}
