package cn.rvport.backend.environment.runtime;

import java.time.Duration;

public record SshCommandResult(
        int exitCode,
        String stdout,
        String stderr,
        Duration duration
) {
}
