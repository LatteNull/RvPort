package cn.rvport.backend.modelprofile;

import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import java.util.UUID;

public record AgentRuntimeSummaryResponse(
        UUID id,
        String agentType,
        String name,
        boolean enabled
) {
    public static AgentRuntimeSummaryResponse from(AgentRuntimesRecord record) {
        return new AgentRuntimeSummaryResponse(
                record.getId(),
                record.getAgentType(),
                record.getName(),
                Boolean.TRUE.equals(record.getEnabled())
        );
    }
}
