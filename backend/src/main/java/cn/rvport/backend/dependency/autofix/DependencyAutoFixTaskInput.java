package cn.rvport.backend.dependency.autofix;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record DependencyAutoFixTaskInput(
        UUID projectId,
        UUID autoFixRunId,
        UUID dependencyAnalysisRunId,
        UUID sourceRevisionId,
        UUID targetEnvironmentId,
        Long environmentConfigVersion,
        Boolean rerunDependencyAnalysis
) {
    public boolean shouldRerunDependencyAnalysis() {
        return rerunDependencyAnalysis == null || rerunDependencyAnalysis;
    }
}
