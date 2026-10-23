package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.worker.TaskExecutionContext;
import java.io.InputStream;
import java.time.Duration;

public record SshCommandRequest(
        SshConnectionTarget target,
        SshConnectionTarget jumpHost,
        String command,
        String stdin,
        InputStream stdinStream,
        boolean streamOutput,
        Duration connectTimeout,
        Duration commandTimeout,
        TaskExecutionContext executionContext
) {
    public SshCommandRequest(
            SshConnectionTarget target,
            SshConnectionTarget jumpHost,
            String command,
            Duration connectTimeout,
            Duration commandTimeout
    ) {
        this(target, jumpHost, command, null, null, false, connectTimeout, commandTimeout, null);
    }

    public SshCommandRequest(
            SshConnectionTarget target,
            SshConnectionTarget jumpHost,
            String command,
            String stdin,
            boolean streamOutput,
            Duration connectTimeout,
            Duration commandTimeout,
            TaskExecutionContext executionContext
    ) {
        this(target, jumpHost, command, stdin, null, streamOutput, connectTimeout, commandTimeout, executionContext);
    }
}
