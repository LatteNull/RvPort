package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.CodexProviderResolvedConfig;
import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import cn.rvport.backend.jooq.tables.records.ModelProfilesRecord;

public record AgentModelRuntimeConfig(
        AgentRuntimesRecord runtime,
        ModelProfilesRecord modelProfile,
        CodexProviderResolvedConfig model
) {
}
