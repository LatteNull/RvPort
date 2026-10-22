package cn.rvport.backend.dependency.autofix;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.UUID;

public record DependencyAutoFixCreateRequest(
        @NotEmpty @Size(max = 200) List<UUID> resultItemIds,
        Boolean rerunDependencyAnalysis
) {
    public boolean shouldRerunDependencyAnalysis() {
        return rerunDependencyAnalysis == null || rerunDependencyAnalysis;
    }
}
