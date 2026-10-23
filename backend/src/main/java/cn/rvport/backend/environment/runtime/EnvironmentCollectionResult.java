package cn.rvport.backend.environment.runtime;

import java.util.Map;
import java.util.UUID;

public record EnvironmentCollectionResult(
        UUID snapshotId,
        UUID toolRunId,
        int exitCode,
        Map<String, Object> summary
) {
}
