package cn.rvport.backend.agentruntime;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class AgentRuntimeService {

    private final AgentRuntimeRepository repository;

    public AgentRuntimeService(AgentRuntimeRepository repository) {
        this.repository = repository;
    }

    public List<AgentRuntimeResponse> list() {
        return repository.list().stream()
                .map(AgentRuntimeResponse::from)
                .toList();
    }

    public AgentRuntimeResponse get(UUID runtimeId) {
        return AgentRuntimeResponse.from(require(runtimeId));
    }

    public AgentRuntimesRecord require(UUID runtimeId) {
        return repository.findById(runtimeId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "AGENT_RUNTIME_NOT_FOUND", "Agent runtime 不存在"));
    }

    public AgentRuntimesRecord requireEnabled(UUID runtimeId) {
        return repository.findEnabledById(runtimeId)
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "AGENT_RUNTIME_NOT_AVAILABLE", "Agent runtime 不存在或未启用"));
    }
}
