package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.worker.TaskExecutionContext;
import java.nio.file.Path;
import java.time.Duration;

public record SshFileTransferRequest(
        SshConnectionTarget target,
        SshConnectionTarget jumpHost,
        Path localPath,
        String remotePath,
        long maxBytes,
        Duration connectTimeout,
        Duration transferTimeout,
        TaskExecutionContext executionContext
) {
    public SshFileTransferRequest {
        if (target == null || localPath == null || remotePath == null || remotePath.isBlank()) {
            throw new IllegalArgumentException("SSH 文件传输参数不完整");
        }
        if (maxBytes <= 0) {
            throw new IllegalArgumentException("SSH 文件传输大小上限必须大于 0");
        }
        connectTimeout = connectTimeout == null ? Duration.ofSeconds(30) : connectTimeout;
        transferTimeout = transferTimeout == null ? Duration.ofMinutes(30) : transferTimeout;
    }
}
