package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.CodexProviderResolvedConfig;
import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import java.nio.file.Path;
import java.time.Duration;

public record AgentRuntimeExecutionRequest(
        AgentRuntimesRecord runtime,
        CodexProviderResolvedConfig model,
        Path workspace,
        String prompt,
        Duration timeout
) {
}
