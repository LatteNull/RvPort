package cn.rvport.backend.environment.runtime;

import java.time.Duration;

public record SshFileTransferResult(long sizeBytes, String sha256, Duration duration) {
}
