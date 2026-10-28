package cn.rvport.backend.kb;

import java.util.UUID;

/** 创建扫描时固定的构建身份；旧记录保持 null，不从历史摘要猜测。 */
public record KbExecutionContext(UUID sourceEnvironmentId, Long runtimeEnvironmentVersion, UUID buildRunId) {
    public boolean complete() {
        return sourceEnvironmentId != null && runtimeEnvironmentVersion != null
                && runtimeEnvironmentVersion >= 0 && buildRunId != null;
    }
}
