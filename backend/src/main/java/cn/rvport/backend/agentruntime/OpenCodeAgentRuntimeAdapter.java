package cn.rvport.backend.agentruntime;

import cn.rvport.backend.codexprovider.AgentType;
import cn.rvport.backend.codexprovider.CodexProcessRunner;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class OpenCodeAgentRuntimeAdapter extends ConfigurableAgentRuntimeAdapter {

    private final ObjectMapper objectMapper;

    public OpenCodeAgentRuntimeAdapter(CodexProcessRunner processRunner, ObjectMapper objectMapper) {
        super(processRunner, objectMapper);
        this.objectMapper = objectMapper;
    }

    @Override
    public AgentType type() {
        return AgentType.OPENCODE;
    }

    @Override
    protected List<String> fallbackArgs(AgentRuntimeExecutionRequest request) throws IOException {
        writeConfig(request);
        return List.of(
                "run",
                "--auto",
                "--dir", request.workspace().toAbsolutePath().normalize().toString(),
                "--model", "rvport-openai-compatible/" + request.model().model()
        );
    }

    @Override
    protected Map<String, String> additionalEnvironment(AgentRuntimeExecutionRequest request) {
        return Map.of("OPENCODE_CONFIG", configPath(request).toString());
    }

    private void writeConfig(AgentRuntimeExecutionRequest request) throws IOException {
        Map<String, Object> model = new LinkedHashMap<>();
        model.put("name", request.model().model());

        Map<String, Object> options = new LinkedHashMap<>();
        options.put("apiKey", "{env:RVPORT_AGENT_API_KEY}");
        options.put("baseURL", request.model().baseUrl());

        Map<String, Object> provider = new LinkedHashMap<>();
        provider.put("npm", "@ai-sdk/openai-compatible");
        provider.put("name", "RvPort OpenAI Compatible");
        provider.put("options", options);
        provider.put("models", Map.of(request.model().model(), model));

        Map<String, Object> config = new LinkedHashMap<>();
        config.put("$schema", "https://opencode.ai/config.json");
        config.put("provider", Map.of("rvport-openai-compatible", provider));
        config.put("model", "rvport-openai-compatible/" + request.model().model());

        Files.writeString(
                configPath(request),
                objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(config),
                StandardCharsets.UTF_8
        );
    }

    private Path configPath(AgentRuntimeExecutionRequest request) {
        return request.workspace().toAbsolutePath().normalize().resolve("opencode.json");
    }
}
