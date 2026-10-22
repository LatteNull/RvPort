package cn.rvport.backend.source.deploy;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.UUID;

public record SourceDeployCreateRequest(
        @NotNull UUID sourceRevisionId,
        List<@NotNull UUID> environmentIds,
        Boolean force,
        @Min(10) @Max(86400) Integer timeoutSeconds
) {
    public boolean forceValue() {
        return Boolean.TRUE.equals(force);
    }
}
