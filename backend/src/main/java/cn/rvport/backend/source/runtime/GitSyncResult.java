package cn.rvport.backend.source.runtime;

import java.time.Duration;

public record GitSyncResult(
        int exitCode,
        String stdout,
        String stderr,
        String actualCommit,
        Duration duration
) {
}
