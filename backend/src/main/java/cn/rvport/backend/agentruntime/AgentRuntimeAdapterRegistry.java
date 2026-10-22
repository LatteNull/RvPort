package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.AgentType;
import cn.rvport.backend.common.error.ApiException;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class AgentRuntimeAdapterRegistry {

    private final Map<AgentType, AgentRuntimeAdapter> adapters;

    public AgentRuntimeAdapterRegistry(List<AgentRuntimeAdapter> adapters) {
        Map<AgentType, AgentRuntimeAdapter> mapped = new EnumMap<>(AgentType.class);
        for (AgentRuntimeAdapter adapter : adapters) {
            mapped.put(adapter.type(), adapter);
        }
        this.adapters = Map.copyOf(mapped);
    }

    public AgentRuntimeAdapter get(String agentType) {
        AgentType type;
        try {
            type = AgentType.valueOf(agentType);
        } catch (IllegalArgumentException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "AGENT_RUNTIME_TYPE_UNSUPPORTED", "Agent runtime 类型不支持");
        }
        AgentRuntimeAdapter adapter = adapters.get(type);
        if (adapter == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "AGENT_RUNTIME_ADAPTER_MISSING", "Agent runtime adapter 未配置");
        }
        return adapter;
    }
}
