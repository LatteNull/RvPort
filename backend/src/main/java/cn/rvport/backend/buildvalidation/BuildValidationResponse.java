package cn.rvport.backend.buildvalidation;

import cn.rvport.backend.buildvalidation.bitcode.BitcodeManifest;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.deploy.SourceDeployEnvironmentSummary;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public record BuildValidationResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        UUID environmentId,
        BuildValidationScope buildScope,
        UUID sourceDeploymentId,
        Long environmentConfigVersion,
        long currentEnvironmentConfigVersion,
        boolean currentSourceRevision,
        boolean currentRuntimeEnvironment,
        List<String> staleReasons,
        String command,
        String commandSummary,
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
        Map<String, Object> compileDatabase,
        Map<String, Object> bitcode,
        SourceRevisionResponse sourceRevision,
        SourceDeployEnvironmentSummary environment
) {
    public static BuildValidationResponse from(
            BuildValidationRunView view,
            SourceRevisionResponse sourceRevision,
            SourceDeployEnvironmentSummary environment
    ) {
        return from(view, sourceRevision, environment, 0L);
    }

    public static BuildValidationResponse from(
            BuildValidationRunView view,
            SourceRevisionResponse sourceRevision,
            SourceDeployEnvironmentSummary environment,
            long currentEnvironmentConfigVersion
    ) {
        return from(view, sourceRevision, environment, currentEnvironmentConfigVersion, view.command(), view.command());
    }

    public static BuildValidationResponse from(
            BuildValidationRunView view,
            SourceRevisionResponse sourceRevision,
            SourceDeployEnvironmentSummary environment,
            long currentEnvironmentConfigVersion,
            String command,
            String commandSummary
    ) {
        boolean isCurrent = view.environmentConfigVersion() != null
                && Objects.equals(view.environmentConfigVersion(), currentEnvironmentConfigVersion);
        boolean currentSourceRevision = sourceRevision != null && sourceRevision.active();
        return new BuildValidationResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.sourceRevisionId(),
                view.environmentId(),
                view.buildScope(),
                view.sourceDeployRunId(),
                view.environmentConfigVersion(),
                currentEnvironmentConfigVersion,
                currentSourceRevision,
                isCurrent,
                staleReasons(currentSourceRevision, isCurrent),
                command,
                commandSummary,
                view.workingDirectory(),
                view.timeoutSeconds(),
                view.exitCode(),
                view.status(),
                view.failureCategory(),
                view.mergedLogId(),
                view.stdoutLogId(),
                view.stderrLogId(),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt(),
                view.environmentVariables(),
                compileDatabase(view.buildFacts()),
                bitcode(view.buildFacts()),
                sourceRevision,
                environment
        );
    }

    private static List<String> staleReasons(boolean currentSourceRevision, boolean currentRuntimeEnvironment) {
        List<String> reasons = new ArrayList<>();
        if (!currentSourceRevision) {
            reasons.add("SOURCE_REVISION_CHANGED");
        }
        if (!currentRuntimeEnvironment) {
            reasons.add("RUNTIME_ENVIRONMENT_CHANGED");
        }
        return List.copyOf(reasons);
    }

    private static Map<String, Object> compileDatabase(Map<String, Object> buildFacts) {
        if (buildFacts == null) {
            return Map.of("available", false);
        }
        Object value = buildFacts.get("compileDatabase");
        if (value instanceof Map<?, ?> map) {
            return map.entrySet().stream()
                    .collect(java.util.stream.Collectors.toMap(
                            entry -> String.valueOf(entry.getKey()),
                            Map.Entry::getValue,
                            (left, right) -> right,
                            java.util.LinkedHashMap::new
                    ));
        }
        return Map.of("available", false);
    }

    private static Map<String, Object> bitcode(Map<String, Object> buildFacts) {
        if (buildFacts != null && buildFacts.get("bitcode") instanceof Map<?, ?> map) {
            Map<String, Object> result = stringKeyMap(map);
            String schema = String.valueOf(result.getOrDefault("schemaVersion", ""));
            boolean legacy = !BitcodeManifest.SCHEMA_VERSION.equals(schema);
            result.putIfAbsent("legacy", legacy);
            result.putIfAbsent("sourceIdentityDigest", null);
            result.putIfAbsent("compileContextDigest", null);
            result.putIfAbsent("bundleSha256", null);
            return result;
        }
        return cn.rvport.backend.buildvalidation.bitcode.BitcodeSummary.unavailable(
                cn.rvport.backend.buildvalidation.bitcode.BitcodeStatus.NOT_ATTEMPTED,
                cn.rvport.backend.buildvalidation.bitcode.BitcodeReasonCode.LEGACY_RECORD
        ).toMap();
    }

    private static Map<String, Object> stringKeyMap(Map<?, ?> map) {
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        map.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }
}
