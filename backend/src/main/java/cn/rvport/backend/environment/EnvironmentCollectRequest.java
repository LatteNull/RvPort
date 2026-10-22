package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import java.util.List;

public record EnvironmentCollectRequest(
        @Size(max = 6) List<EnvironmentCollectScope> collectScopes,
        @Min(1) @Max(86400) Integer timeoutSeconds
) {
}
