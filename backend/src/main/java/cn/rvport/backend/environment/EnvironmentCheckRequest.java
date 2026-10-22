package cn.rvport.backend.environment;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import java.util.List;

public record EnvironmentCheckRequest(
        @Size(max = 4) List<EnvironmentCheckItem> checkItems,
        @Size(max = 1000) String workingDirectory,
        @Min(1) @Max(86400) Integer timeoutSeconds
) {
}
