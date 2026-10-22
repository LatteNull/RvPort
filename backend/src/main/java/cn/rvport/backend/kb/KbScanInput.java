package cn.rvport.backend.kb;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record KbScanInput(
        UUID projectId,
        UUID scanRunId,
        UUID sourceRevisionId,
        String ruleVersion,
        String language,
        String targetArch,
        Map<String, Object> scanScope,
        List<String> excludePaths
) {
}
