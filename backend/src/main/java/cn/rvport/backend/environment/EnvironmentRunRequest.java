package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record EnvironmentRunRequest(
        @Min(1) @Max(86400) Integer timeoutSeconds
) {
}
