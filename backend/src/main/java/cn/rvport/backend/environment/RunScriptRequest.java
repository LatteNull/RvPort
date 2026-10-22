package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.Map;

public record RunScriptRequest(
        @NotNull EnvironmentScriptType scriptType,
        @Size(max = 12000) String script,
        @Min(1) @Max(86400) Integer timeoutSeconds,
        @Size(max = 1000) String workingDirectory,
        @Size(max = 20) Map<@Size(max = 80) String, @Size(max = 1000) String> parameters
) {
}
