package cn.rvport.backend.buildvalidation;

import cn.rvport.backend.jooq.tables.records.BuildRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record BuildValidationRunView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID environmentId,
        BuildValidationScope buildScope,
        UUID sourceDeployRunId,
        Long environmentConfigVersion,
        UUID scriptPayloadId,
        String scriptSha256,
        String command,
        String workingDirectory,
        Integer timeoutSeconds,
        Integer exitCode,
        TaskStatus status,
        String failureCategory,
        UUID mergedLogId,
        UUID stdoutLogId,
        UUID stderrLogId,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        Map<String, String> environmentVariables,
        Map<String, Object> buildFacts
) {
    public BuildValidationRunView(
            UUID id,
            UUID projectId,
            UUID taskId,
            UUID sourceRevisionId,
            UUID environmentId,
            UUID sourceDeployRunId,
            Long environmentConfigVersion,
            UUID scriptPayloadId,
            String scriptSha256,
            String command,
            String workingDirectory,
            Integer timeoutSeconds,
            Integer exitCode,
            TaskStatus status,
            String failureCategory,
            UUID mergedLogId,
            UUID stdoutLogId,
            UUID stderrLogId,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            OffsetDateTime createdAt,
            Map<String, String> environmentVariables
    ) {
        this(id, projectId, taskId, sourceRevisionId, environmentId, BuildValidationScope.BOTH, sourceDeployRunId,
                environmentConfigVersion, scriptPayloadId, scriptSha256, command, workingDirectory, timeoutSeconds,
                exitCode, status, failureCategory, mergedLogId, stdoutLogId, stderrLogId, startedAt, finishedAt,
                createdAt, environmentVariables, Map.of());
    }

    public BuildValidationRunView(
            UUID id,
            UUID projectId,
            UUID taskId,
            UUID sourceRevisionId,
            UUID environmentId,
            UUID sourceDeployRunId,
            UUID scriptPayloadId,
            String scriptSha256,
            String command,
            String workingDirectory,
            Integer timeoutSeconds,
            Integer exitCode,
            TaskStatus status,
            String failureCategory,
            UUID mergedLogId,
            UUID stdoutLogId,
            UUID stderrLogId,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            OffsetDateTime createdAt,
            Map<String, String> environmentVariables
    ) {
        this(id, projectId, taskId, sourceRevisionId, environmentId, BuildValidationScope.BOTH, sourceDeployRunId,
                null, scriptPayloadId, scriptSha256, command, workingDirectory, timeoutSeconds, exitCode, status,
                failureCategory, mergedLogId, stdoutLogId, stderrLogId, startedAt, finishedAt, createdAt,
                environmentVariables, Map.of());
    }

    public BuildValidationRunView(
            UUID id,
            UUID projectId,
            UUID taskId,
            UUID sourceRevisionId,
            UUID environmentId,
            BuildValidationScope buildScope,
            UUID sourceDeployRunId,
            UUID scriptPayloadId,
            String scriptSha256,
            String command,
            String workingDirectory,
            Integer timeoutSeconds,
            Integer exitCode,
            TaskStatus status,
            String failureCategory,
            UUID mergedLogId,
            UUID stdoutLogId,
            UUID stderrLogId,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            OffsetDateTime createdAt,
            Map<String, String> environmentVariables
    ) {
        this(id, projectId, taskId, sourceRevisionId, environmentId, buildScope, sourceDeployRunId, null, scriptPayloadId,
                scriptSha256, command, workingDirectory, timeoutSeconds, exitCode, status, failureCategory,
                mergedLogId, stdoutLogId, stderrLogId, startedAt, finishedAt, createdAt, environmentVariables,
                Map.of());
    }

    public static BuildValidationRunView from(BuildRunsRecord record) {
        return from(record, Map.of());
    }

    public static BuildValidationRunView from(BuildRunsRecord record, Map<String, String> environmentVariables) {
        return from(record, environmentVariables, BuildValidationScope.BOTH);
    }

    public static BuildValidationRunView from(BuildRunsRecord record, Map<String, String> environmentVariables, BuildValidationScope buildScope) {
        return from(record, environmentVariables, buildScope, Map.of());
    }

    public static BuildValidationRunView from(
            BuildRunsRecord record,
            Map<String, String> environmentVariables,
            BuildValidationScope buildScope,
            Map<String, Object> buildFacts
    ) {
        return new BuildValidationRunView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getSourceRevisionId(),
                record.getEnvironmentId(),
                buildScope == null ? BuildValidationScope.BOTH : buildScope,
                record.getSourceDeployRunId(),
                record.getEnvironmentConfigVersion(),
                record.getScriptPayloadId(),
                record.getScriptSha256(),
                record.getCommand(),
                record.getWorkingDirectory(),
                record.getTimeoutSeconds(),
                record.getExitCode(),
                TaskStatus.valueOf(record.getStatus()),
                record.getFailureCategory(),
                record.getCombinedLogId(),
                record.getStdoutLogId(),
                record.getStderrLogId(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getCreatedAt(),
                environmentVariables == null ? Map.of() : environmentVariables,
                buildFacts == null ? Map.of() : buildFacts
        );
    }

    public Map<String, Object> resource() {
        return Map.of("type", "BUILD_VALIDATION", "id", id);
    }
}
