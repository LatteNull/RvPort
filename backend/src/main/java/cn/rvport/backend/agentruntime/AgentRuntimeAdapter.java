package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.AgentType;
import cn.rvport.backend.codexprovider.CodexProcessResult;
import java.io.IOException;

public interface AgentRuntimeAdapter {
    AgentType type();

    CodexProcessResult run(AgentRuntimeExecutionRequest request) throws IOException, InterruptedException;
}
