package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.AgentType;
import cn.rvport.backend.codexprovider.CodexProcessResult;
import cn.rvport.backend.codexprovider.CodexProcessRunner;
import java.io.IOException;
import org.springframework.stereotype.Component;

@Component
public class CodexAgentRuntimeAdapter implements AgentRuntimeAdapter {

    private final CodexProcessRunner processRunner;

    public CodexAgentRuntimeAdapter(CodexProcessRunner processRunner) {
        this.processRunner = processRunner;
    }

    @Override
    public AgentType type() {
        return AgentType.CODEX;
    }

    @Override
    public CodexProcessResult run(AgentRuntimeExecutionRequest request) throws IOException, InterruptedException {
        return processRunner.run(
                CodexAgentCommandFactory.command(request.runtime().getExecutablePath(), request.model(), request.workspace()),
                CodexAgentCommandFactory.environment(request.model()),
                request.prompt(),
                request.workspace(),
                request.timeout()
        );
    }
}
