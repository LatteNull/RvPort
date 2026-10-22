package cn.rvport.backend.buildvalidation.bitcode;

import cn.rvport.backend.environment.runtime.SshConnectionTarget;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.util.UUID;

public record BitcodeGenerationRequest(
        UUID projectId,
        UUID taskId,
        UUID buildRunId,
        UUID sourceRevisionId,
        String remoteSourcePath,
        SshConnectionTarget target,
        SshConnectionTarget jumpHost,
        TaskExecutionContext executionContext
) {
}
