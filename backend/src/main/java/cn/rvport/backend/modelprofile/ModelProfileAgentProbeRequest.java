package cn.rvport.backend.modelprofile;

import java.util.List;
import java.util.UUID;

public record ModelProfileAgentProbeRequest(
        List<UUID> agentRuntimeIds
) {
}
