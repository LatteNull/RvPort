package cn.rvport.backend.kb.ai;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

public record KbAiExtensionAgentResult(
        Path workspace,
        Path inputFile,
        Path outputFile,
        List<Map<String, Object>> rawRows,
        Map<String, Object> agentOutput
) {
}
